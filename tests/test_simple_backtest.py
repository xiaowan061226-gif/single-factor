"""Independent hand-calculated tests for the formal simple backtest."""

import numpy as np
import pandas as pd
import pytest

from single_factor_quant.backtest.simple_backtest import run_top_quantile_backtest
from spike.backtest import make_backtest_demo_panel


def _golden_panel(periods: int = 42) -> pd.DataFrame:
    """Build five stocks: A rises 10%, then B rises 20% after the swap."""
    dates = pd.bdate_range("2024-01-02", periods=periods)
    frames = []
    for code, initial_rank in zip(list("ABCDE"), range(5, 0, -1), strict=True):
        close = np.full(periods, 100.0)
        if code == "A" and periods > 2:
            close[2:] = 110.0
        if code == "B" and periods > 22:
            close[22:] = 120.0
        alpha = np.full(periods, float(initial_rank))
        if periods > 20:
            alpha[20:] = {"A": 4.0, "B": 5.0, "C": 3.0, "D": 2.0, "E": 1.0}[code]
        frames.append(pd.DataFrame({"date": dates, "code": code, "close": close, "alpha": alpha}))
    return pd.concat(frames, ignore_index=True)


def test_next_close_execution_has_no_lookahead_lag() -> None:
    result = run_top_quantile_backtest(_golden_panel(), factor_col="alpha", cost_rate=0.0)

    assert result.rebalances.loc[0, "signal_date"] == pd.Timestamp("2024-01-02")
    assert result.rebalances.loc[0, "execution_date"] == pd.Timestamp("2024-01-03")
    assert result.rebalances.loc[0, "selected_codes"] == "A"
    assert np.isclose(result.daily.loc[1, "net_return"], 0.0)
    assert np.isclose(result.daily.loc[2, "gross_return"], 0.10)


def test_zero_cost_nav_matches_hand_calculated_path() -> None:
    result = run_top_quantile_backtest(_golden_panel(), factor_col="alpha", cost_rate=0.0)

    assert np.isclose(result.daily.loc[2, "nav"], 1.10)
    assert np.isclose(result.daily.loc[22, "nav"], 1.32)
    assert np.isclose(result.daily.iloc[-1]["nav"], 1.32)
    assert np.isclose(result.cumulative_return, 0.32)


def test_first_build_charges_one_side_of_turnover() -> None:
    result = run_top_quantile_backtest(_golden_panel(), factor_col="alpha", cost_rate=0.001)
    first = result.rebalances.loc[0]

    assert np.isclose(first["gross_turnover"], 1.0)
    assert np.isclose(first["transaction_cost"], 0.001)
    assert np.isclose(result.daily.loc[1, "nav"], 0.999)
    assert np.isclose(result.daily.loc[1, "net_return"], -0.001)


def test_full_swap_charges_both_sell_and_buy_sides() -> None:
    result = run_top_quantile_backtest(_golden_panel(), factor_col="alpha", cost_rate=0.001)
    swap = result.rebalances.loc[1]

    assert swap["selected_codes"] == "B"
    assert np.isclose(swap["gross_turnover"], 2.0)
    assert np.isclose(swap["transaction_cost"], 0.002)
    assert np.isclose(result.daily.loc[21, "nav"], 1.0967022)


def test_two_holdings_drift_without_share_changes_between_rebalances() -> None:
    result = run_top_quantile_backtest(
        _golden_panel(), factor_col="alpha", top_fraction=0.40, cost_rate=0.0
    )
    day_one = result.holdings.loc[result.holdings["date"] == pd.Timestamp("2024-01-03")]
    day_two = result.holdings.loc[result.holdings["date"] == pd.Timestamp("2024-01-04")]

    assert np.isclose(day_one.loc[day_one["code"] == "A", "shares"].iloc[0], 0.005)
    assert np.isclose(day_two.loc[day_two["code"] == "A", "shares"].iloc[0], 0.005)
    assert np.isclose(day_two.loc[day_two["code"] == "A", "weight"].iloc[0], 11 / 21)
    assert np.isclose(day_two.loc[day_two["code"] == "B", "weight"].iloc[0], 10 / 21)


def test_final_signal_without_next_day_is_recorded_and_not_traded() -> None:
    result = run_top_quantile_backtest(_golden_panel(periods=41), factor_col="alpha", cost_rate=0.0)
    final = result.rebalances.iloc[-1]

    assert final["status"] == "skipped"
    assert final["reason"] == "skipped_no_next_trading_day"
    assert final["signal_date"] == pd.Timestamp("2024-02-27")
    assert pd.isna(final["execution_date"])
    assert np.isclose(result.daily.iloc[-1]["nav"], 1.32)


def test_demo_panel_is_deterministic() -> None:
    assert make_backtest_demo_panel().equals(make_backtest_demo_panel())


def test_new_holding_cannot_earn_signal_or_execution_day_return() -> None:
    panel = _golden_panel()
    dates = sorted(panel.date.unique())
    for position, price in [(20, 200.), (21, 400.), (22, 800.)]:
        panel.loc[(panel.code == "B") & (panel.date >= dates[position]), "close"] = price
    result = run_top_quantile_backtest(panel, "alpha", cost_rate=0)
    assert np.allclose(result.daily.nav.iloc[[20, 21, 22]], [1.1, 1.1, 2.2])


def test_default_fraction_rounds_up_and_ties_use_code() -> None:
    panel = _golden_panel().assign(alpha=1.)
    extra = panel.loc[panel.code == "E"].assign(code="F")
    panel = pd.concat([panel, extra]).sample(frac=1, random_state=9)
    original = panel.copy(deep=True)
    result = run_top_quantile_backtest(panel, "alpha", cost_rate=0)
    assert result.rebalances.n_selected.tolist() == [2, 2, 2]
    assert result.rebalances.selected_codes.tolist() == ["A,B", "A,B", "A,B"]
    assert np.isclose(result.rebalances.gross_turnover.iloc[1], 1 / 21)
    pd.testing.assert_frame_equal(panel, original)


def test_cost_compounding_metrics_and_no_trade_no_fee() -> None:
    result = run_top_quantile_backtest(_golden_panel(), "alpha")
    assert np.isclose(result.daily.nav.iloc[-1], 1.31604264)
    assert np.isclose(result.gross_turnover, 3.)
    assert np.isclose(result.annualized_return_252, 1.31604264 ** 6 - 1)
    assert np.isclose(result.max_drawdown, -.002)
    assert np.allclose((1 + result.daily.net_return).cumprod(), result.daily.nav)
    assert result.daily.transaction_cost.iloc[41] == 0
    assert (result.daily.loc[~result.daily.rebalanced, "transaction_cost"] == 0).all()


@pytest.mark.parametrize("value", [True, 1.5, float("nan")])
def test_rebalance_interval_requires_integer(value) -> None:
    with pytest.raises(ValueError, match="rebalance_every"):
        run_top_quantile_backtest(_golden_panel(), "alpha", rebalance_every=value)


def test_no_factor_and_single_date_boundaries_remain_in_cash() -> None:
    empty_signal = run_top_quantile_backtest(_golden_panel().assign(alpha=np.nan), "alpha")
    assert (empty_signal.daily.nav == 1).all()
    assert empty_signal.gross_turnover == 0
    assert set(empty_signal.rebalances.reason) == {"skipped_no_valid_factor"}
    single = run_top_quantile_backtest(_golden_panel(periods=1), "alpha")
    assert single.daily.nav.tolist() == [1.]
    assert single.rebalances.reason.tolist() == ["skipped_no_next_trading_day"]
