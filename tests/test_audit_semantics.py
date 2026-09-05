"""Adversarial tests for time, cross-section, and backtest semantics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt

from single_factor_quant.backtest.simple_backtest import run_top_quantile_backtest
from single_factor_quant.config import ResearchConfig
from single_factor_quant.factors.momentum import calculate_momentum
from single_factor_quant.pipeline import make_demo_price_panel, run_research_pipeline
from single_factor_quant.research.forward_return import calculate_forward_returns
from single_factor_quant.research.grouping import quintile_forward_returns
from single_factor_quant.research.ic import daily_ic_rankic


def _interleaved_prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=7, freq="B")
    rows: list[dict[str, object]] = []
    for date, aaa, bbb in zip(
        dates,
        [100.0, 105.0, 110.0, 120.0, 130.0, 140.0, 150.0],
        [1000.0, 950.0, 800.0, 850.0, 900.0, 920.0, 940.0],
    ):
        rows.extend(
            [
                {"date": date, "code": "BBB", "close": bbb},
                {"date": date, "code": "AAA", "close": aaa},
            ]
        )
    return pd.DataFrame(rows)


def _keyed(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def test_per_code_shifts_have_hand_calculated_direction_and_no_future_factor_leakage() -> None:
    """Interleaved stocks expose a missing groupby or a reversed forward shift."""
    prices = _interleaved_prices()
    dates = sorted(prices["date"].unique())

    momentum = calculate_momentum(prices, window=2, output_col="momentum")
    labels = calculate_forward_returns(prices, horizon=2, output_col="forward_return_2")
    aaa_momentum = momentum.query("code == 'AAA' and date == @dates[2]").iloc[0]
    bbb_momentum = momentum.query("code == 'BBB' and date == @dates[2]").iloc[0]
    aaa_label = labels.query("code == 'AAA' and date == @dates[0]").iloc[0]

    assert np.isclose(aaa_momentum["momentum"], 0.10)  # 110 / 100 - 1
    assert np.isclose(bbb_momentum["momentum"], -0.20)  # 800 / 1000 - 1
    assert np.isclose(aaa_label["forward_return_2"], 0.10)  # 110 / 100 - 1

    changed = prices.copy()
    changed.loc[(changed["code"] == "AAA") & (changed["date"] == dates[3]), "close"] = 240.0
    changed_momentum = calculate_momentum(changed, window=2, output_col="momentum")
    changed_labels = calculate_forward_returns(changed, horizon=2, output_col="forward_return_2")
    original_at_one = labels.query("code == 'AAA' and date == @dates[1]").iloc[0]
    changed_at_one = changed_labels.query("code == 'AAA' and date == @dates[1]").iloc[0]
    original_at_two = momentum.query("code == 'AAA' and date == @dates[2]").iloc[0]
    changed_at_two = changed_momentum.query("code == 'AAA' and date == @dates[2]").iloc[0]

    assert np.isclose(changed_at_one["forward_return_2"], 240.0 / 105.0 - 1.0)
    assert changed_at_one["forward_return_2"] != original_at_one["forward_return_2"]
    assert changed_at_two["momentum"] == original_at_two["momentum"]


def test_adding_or_deleting_another_stock_cannot_change_a_stock_time_series() -> None:
    """A stock's shifts must remain isolated when the panel membership changes."""
    prices = _interleaved_prices()
    aaa_only = prices.loc[prices["code"] == "AAA"].copy()
    copied = aaa_only.assign(code="CCC", close=lambda frame: frame["close"] * 3.0)
    expanded = pd.concat([prices, copied], ignore_index=True).sample(frac=1.0, random_state=7)

    for calculator, kwargs, column in [
        (calculate_momentum, {"window": 2, "output_col": "momentum"}, "momentum"),
        (
            calculate_forward_returns,
            {"horizon": 2, "output_col": "forward_return_2"},
            "forward_return_2",
        ),
    ]:
        baseline = calculator(aaa_only, **kwargs)
        observed = calculator(expanded, **kwargs).query("code == 'AAA'")
        pdt.assert_frame_equal(_keyed(baseline), _keyed(observed), check_like=False)
        assert baseline[column].notna().sum() > 0


def test_pipeline_is_key_stable_when_source_rows_are_randomized() -> None:
    """The full research output must align by date/code instead of input row position."""
    config = ResearchConfig(momentum_window=30, forward_horizon=10, rebalance_interval=15)
    prices = make_demo_price_panel()
    randomized = prices.sample(frac=1.0, random_state=20260905).reset_index(drop=True)

    expected = run_research_pipeline(prices, config=config)
    observed = run_research_pipeline(randomized, config=config)

    pdt.assert_frame_equal(_keyed(expected.factor_data), _keyed(observed.factor_data))
    pdt.assert_frame_equal(expected.daily_ic, observed.daily_ic)
    pdt.assert_frame_equal(expected.quintiles.returns, observed.quintiles.returns)
    pdt.assert_frame_equal(expected.backtest.daily, observed.backtest.daily)
    pdt.assert_frame_equal(expected.backtest.rebalances, observed.backtest.rebalances)


def test_group_direction_and_invalid_cross_sections_do_not_make_statistics() -> None:
    """Q1 is low factor, Q5 high factor; degenerate inputs are explicitly invalid."""
    date = pd.Timestamp("2024-02-01")
    ordered = pd.DataFrame(
        {
            "date": [date] * 10,
            "code": [f"S{number:02d}" for number in range(10)],
            "factor": np.arange(1.0, 11.0),
            "forward_return_20": np.arange(0.01, 0.11, 0.01),
        }
    )
    quintiles = quintile_forward_returns(ordered, factor_col="factor")
    means = quintiles.mean_returns
    mean_by_quintile = means.set_index("quintile")["mean_forward_return"]
    assert np.isclose(mean_by_quintile.loc["Q1"], 0.015)
    assert np.isclose(mean_by_quintile.loc["Q5"], 0.095)
    assert mean_by_quintile.loc["Q1"] < mean_by_quintile.loc["Q5"]

    constant = ordered.assign(factor=1.0)
    ic = daily_ic_rankic(constant, factor_col="factor")
    skipped = quintile_forward_returns(constant, factor_col="factor")
    assert pd.isna(ic.loc[0, "ic"])
    assert ic.loc[0, "invalid_reason"] == "constant_factor"
    assert skipped.returns.empty
    assert skipped.skipped.loc[0, "reason"] == "fewer_than_five_distinct_factor_values"

    too_small_ic = ordered.iloc[:2].copy()
    too_small_groups = ordered.iloc[:4].copy()
    small_ic = daily_ic_rankic(too_small_ic, factor_col="factor")
    small_groups = quintile_forward_returns(too_small_groups, factor_col="factor")
    assert pd.isna(small_ic.loc[0, "ic"])
    assert small_ic.loc[0, "invalid_reason"] == "fewer_than_three_valid_pairs"
    assert small_groups.returns.empty
    assert small_groups.skipped.loc[0, "reason"] == "fewer_than_five_valid_stocks"


def test_backtest_executes_next_day_drifts_weights_and_charges_only_actual_trades() -> None:
    """Signal dates stay in cash, holdings drift between rebalances, and costs are trade-only."""
    dates = pd.date_range("2024-01-02", periods=5, freq="B")
    rows: list[dict[str, object]] = []
    for date, aaa, bbb in zip(
        dates,
        [100.0, 110.0, 121.0, 133.1, 146.41],
        [100.0, 100.0, 100.0, 100.0, 100.0],
    ):
        rows.extend(
            [
                {"date": date, "code": "AAA", "close": aaa, "factor": 2.0},
                {"date": date, "code": "BBB", "close": bbb, "factor": 1.0},
            ]
        )
    result = run_top_quantile_backtest(
        pd.DataFrame(rows), factor_col="factor", rebalance_every=4, top_fraction=1.0, cost_rate=0.01
    )
    daily = result.daily.set_index("date")
    aaa_holdings = result.holdings.query("code == 'AAA'").set_index("date")

    assert result.rebalances.loc[0, "signal_date"] == dates[0]
    assert result.rebalances.loc[0, "execution_date"] == dates[1]
    assert daily.loc[dates[0], "net_return"] == 0.0
    assert daily.loc[dates[0], "transaction_cost"] == 0.0
    assert daily.loc[dates[1], "transaction_cost"] == 0.01
    assert (daily.loc[dates[2]:dates[4], "transaction_cost"] == 0.0).all()
    assert aaa_holdings.loc[dates[1], "shares"] == aaa_holdings.loc[dates[2], "shares"]
    assert aaa_holdings.loc[dates[2], "weight"] > aaa_holdings.loc[dates[1], "weight"]
