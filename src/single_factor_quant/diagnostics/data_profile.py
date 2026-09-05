"""Read-only diagnostics for validated local price panels and research results."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest.simple_backtest import BacktestResult
from ..config import ResearchConfig
from ..research.grouping import QuintileResult


@dataclass(frozen=True)
class DataDiagnostics:
    """Data quality, coverage, and research availability measurements."""

    date_start: object
    date_end: object
    stock_count: int
    row_count: int
    observations_per_stock: pd.Series
    stocks_with_momentum_history: int
    duplicate_key_count: int
    missing_required_value_count: int
    illegal_close_count: int
    factor_coverage_all: float
    factor_coverage_eligible: float | None
    standardized_factor_coverage: float
    forward_label_coverage: float
    valid_ic_dates: int
    skipped_group_dates: int
    grouped_dates: int
    executed_rebalances: int


def build_data_diagnostics(
    prices: pd.DataFrame,
    factor_data: pd.DataFrame,
    daily_ic: pd.DataFrame,
    quintiles: QuintileResult,
    backtest: BacktestResult,
    config: ResearchConfig,
) -> DataDiagnostics:
    """Profile clean local prices and quantify usable research output without mutation."""
    counts = prices.groupby("code", sort=True).size()
    ordered = prices.loc[:, ["date", "code"]].sort_values(["code", "date"], kind="stable").copy()
    ordered["has_history"] = ordered.groupby("code", sort=False).cumcount() >= config.momentum_window
    history = factor_data.loc[:, ["date", "code", f"momentum_{config.momentum_window}"]].merge(
        ordered, on=["date", "code"], how="left", validate="one_to_one"
    )
    eligible = history.loc[history.has_history]
    close = pd.to_numeric(prices["close"], errors="coerce")
    return DataDiagnostics(
        date_start=prices.date.min(), date_end=prices.date.max(), stock_count=int(counts.size), row_count=len(prices),
        observations_per_stock=counts, stocks_with_momentum_history=int(ordered.groupby("code").has_history.any().sum()),
        duplicate_key_count=int(prices.duplicated(["date", "code"]).sum()),
        missing_required_value_count=int(prices[["date", "code", "close"]].isna().any(axis=1).sum()),
        illegal_close_count=int((~np.isfinite(close) | close.le(0)).sum()),
        factor_coverage_all=_coverage(factor_data[f"momentum_{config.momentum_window}"]),
        factor_coverage_eligible=_coverage(eligible[f"momentum_{config.momentum_window}"]) if len(eligible) else None,
        standardized_factor_coverage=_coverage(factor_data["factor_zscore"]),
        forward_label_coverage=_coverage(factor_data[f"forward_return_{config.forward_horizon}"]),
        valid_ic_dates=int(daily_ic.ic.notna().sum()), skipped_group_dates=len(quintiles.skipped),
        grouped_dates=int(quintiles.returns.date.nunique()),
        executed_rebalances=int((backtest.rebalances.status == "executed").sum()),
    )


def require_usable_research(diagnostics: DataDiagnostics, config: ResearchConfig) -> None:
    """Raise actionable errors instead of returning an empty research result."""
    if diagnostics.factor_coverage_all == 0.0:
        raise ValueError(
            f"insufficient history: no row has {config.momentum_window} prior observations; "
            f"provide at least {config.momentum_window + 1} rows per stock"
        )
    if diagnostics.standardized_factor_coverage == 0.0:
        raise ValueError("insufficient cross-section: need at least two non-constant factor values on a date")
    if diagnostics.grouped_dates == 0:
        raise ValueError(
            f"insufficient cross-section: need at least {config.quantiles} stocks with both factor and "
            "future-return label on one date to form quantile groups"
        )
    if diagnostics.executed_rebalances == 0:
        raise ValueError("no executable rebalance: provide a scheduled date after usable factor observations")


def _coverage(values: pd.Series) -> float:
    """Return the non-missing share of a non-empty research series."""
    return float(values.notna().mean()) if len(values) else 0.0
