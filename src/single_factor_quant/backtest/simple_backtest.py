"""Close-to-close top-factor portfolio backtest."""

from dataclasses import dataclass
from math import ceil

import numpy as np
import pandas as pd

from ..research._panel import keyed_numeric_copy


@dataclass(frozen=True)
class BacktestResult:
    """Daily portfolio path, holdings, rebalance audit trail, and metrics."""

    daily: pd.DataFrame
    holdings: pd.DataFrame
    rebalances: pd.DataFrame
    gross_turnover: float
    cumulative_return: float
    annualized_return_252: float
    max_drawdown: float


def run_top_quantile_backtest(
    panel: pd.DataFrame,
    factor_col: str,
    rebalance_every: int = 20,
    top_fraction: float = 0.20,
    cost_rate: float = 0.001,
    annualization_days: int = 252,
) -> BacktestResult:
    """Run top-factor trading with next-close execution and drifting weights.

    A signal formed after date ``t`` close is executed at the next market close.
    Shares remain unchanged until the next execution, so portfolio weights drift
    with prices. Costs equal ``cost_rate * sum(abs(target - prior_weight))``.
    """
    _validate_parameters(rebalance_every, top_fraction, cost_rate, annualization_days)
    working = _validate_panel(panel, factor_col)
    prices = working.pivot(index="date", columns="code", values="close").sort_index()
    factors = working.pivot(index="date", columns="code", values=factor_col).reindex_like(prices)
    orders, rebalances = _signal_orders(prices.index, prices.columns, factors, factor_col, rebalance_every, top_fraction)
    shares = pd.Series(0.0, index=prices.columns)
    nav, invested = 1.0, False
    daily_rows: list[dict[str, object]] = []
    holding_rows: list[dict[str, object]] = []
    for date, price in prices.iterrows():
        nav_before_trade = float((shares * price).sum()) if invested else nav
        gross_return = nav_before_trade / nav - 1.0 if invested else 0.0
        turnover, cost_fraction, rebalanced = 0.0, 0.0, False
        if date in orders:
            order = orders[date]
            prior_weights = (shares * price / nav_before_trade) if invested else shares.copy()
            target_weights = pd.Series(0.0, index=prices.columns)
            target_weights.loc[order["selected_codes"]] = 1.0 / order["n_selected"]
            turnover = float((target_weights - prior_weights).abs().sum())
            cost_fraction = cost_rate * turnover
            nav = nav_before_trade * (1.0 - cost_fraction)
            shares = target_weights * nav / price
            invested, rebalanced = True, True
            rebalances.append(_executed_record(order, date, turnover, cost_fraction))
        else:
            nav = nav_before_trade
        prior_nav = daily_rows[-1]["nav"] if daily_rows else 1.0
        weights = (shares * price / nav) if invested else shares.copy()
        daily_rows.append({"date": date, "gross_return": gross_return, "net_return": nav / prior_nav - 1.0,
                           "nav": nav, "gross_turnover": turnover, "transaction_cost": cost_fraction,
                           "rebalanced": rebalanced})
        holding_rows.extend({"date": date, "code": code, "shares": shares.loc[code], "weight": weights.loc[code]}
                            for code in prices.columns)
    daily = pd.DataFrame(daily_rows)
    rebalances_frame = pd.DataFrame(rebalances, columns=_REBALANCE_COLUMNS).sort_values(
        "signal_date", kind="stable", ignore_index=True
    )
    nav_series = daily["nav"]
    return BacktestResult(
        daily=daily, holdings=pd.DataFrame(holding_rows), rebalances=rebalances_frame,
        gross_turnover=float(daily.gross_turnover.sum()), cumulative_return=float(nav_series.iloc[-1] - 1.0),
        annualized_return_252=float(nav_series.iloc[-1] ** (annualization_days / len(daily)) - 1.0),
        max_drawdown=float((nav_series / nav_series.cummax() - 1.0).min()),
    )


_REBALANCE_COLUMNS = [
    "signal_date", "execution_date", "status", "reason", "n_eligible", "n_selected",
    "selected_codes", "gross_turnover", "transaction_cost",
]


def _signal_orders(
    dates: pd.Index, codes: pd.Index, factors: pd.DataFrame, factor_col: str,
    rebalance_every: int, top_fraction: float,
) -> tuple[dict[object, dict[str, object]], list[dict[str, object]]]:
    """Turn every eligible signal date into an order for the next market close."""
    orders: dict[object, dict[str, object]] = {}
    records: list[dict[str, object]] = []
    for position in range(0, len(dates), rebalance_every):
        signal_date = dates[position]
        execution_date = dates[position + 1] if position + 1 < len(dates) else None
        if execution_date is None:
            records.append(_skipped_record(signal_date, None, "skipped_no_next_trading_day"))
            continue
        eligible = pd.DataFrame({"code": codes, factor_col: factors.loc[signal_date].to_numpy()}).dropna()
        if eligible.empty:
            records.append(_skipped_record(signal_date, execution_date, "skipped_no_valid_factor"))
            continue
        selected = eligible.sort_values([factor_col, "code"], ascending=[False, True], kind="stable").head(
            ceil(len(eligible) * top_fraction)
        )
        orders[execution_date] = {"signal_date": signal_date, "n_eligible": len(eligible),
                                  "n_selected": len(selected), "selected_codes": selected.code.tolist()}
    return orders, records


def _skipped_record(signal_date: object, execution_date: object, reason: str) -> dict[str, object]:
    """Build the audit record for a signal that cannot be executed."""
    return {"signal_date": signal_date, "execution_date": execution_date, "status": "skipped", "reason": reason,
            "n_eligible": 0, "n_selected": 0, "selected_codes": "", "gross_turnover": 0.0, "transaction_cost": 0.0}


def _executed_record(
    order: dict[str, object], execution_date: object, turnover: float, cost_fraction: float
) -> dict[str, object]:
    """Build the audit record for a completed next-close rebalance."""
    return {"signal_date": order["signal_date"], "execution_date": execution_date, "status": "executed", "reason": None,
            "n_eligible": order["n_eligible"], "n_selected": order["n_selected"],
            "selected_codes": ",".join(order["selected_codes"]), "gross_turnover": turnover,
            "transaction_cost": cost_fraction}


def _validate_panel(panel: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """Validate a complete date-by-code price panel and an optionally missing factor."""
    working = keyed_numeric_copy(panel, ("close", factor_col))
    if working.empty:
        raise ValueError("panel must contain at least one date and one code")
    if (working.close <= 0).any():
        raise ValueError("close must contain only positive values")
    if len(working) != working.date.nunique() * working.code.nunique():
        raise ValueError("simple backtest requires a complete date-by-code close panel")
    return working


def _validate_parameters(rebalance_every: int, top_fraction: float, cost_rate: float, annualization_days: int) -> None:
    """Reject parameter values that make the portfolio calculation undefined."""
    if isinstance(rebalance_every, bool) or not isinstance(rebalance_every, int) or rebalance_every < 1:
        raise ValueError("rebalance_every must be an integer at least 1")
    if not 0.0 < top_fraction <= 1.0:
        raise ValueError("top_fraction must be in (0, 1]")
    if not 0.0 <= cost_rate < 0.5:
        raise ValueError("cost_rate must be in [0, 0.5)")
    if isinstance(annualization_days, bool) or not isinstance(annualization_days, int) or annualization_days < 1:
        raise ValueError("annualization_days must be an integer at least 1")
