"""Tests for the stage-2 cross-sectional research spike."""

import math

import numpy as np
import pandas as pd
import pytest

from spike.research import (
    cross_sectional_zscore,
    daily_ic_rankic,
    quintile_forward_returns,
    summarize_ic,
)


def _golden_panel() -> pd.DataFrame:
    """Create ten same-date stocks whose factor and label have the same order."""
    return pd.DataFrame(
        {
            "date": pd.Timestamp("2024-01-02"),
            "code": [f"S{i:02d}" for i in range(1, 11)],
            "alpha": np.arange(1.0, 11.0),
            "forward_return_20": np.arange(1.0, 11.0) / 100.0,
        }
    )


def _row(result: pd.DataFrame, date: pd.Timestamp, code: str, column: str) -> float:
    """Read a cross-sectional result by explicit keys."""
    return result.loc[(result["date"] == date) & (result["code"] == code), column].iloc[0]


def test_golden_ordered_data_has_rankic_one_and_rising_quintiles() -> None:
    panel = _golden_panel()
    daily = daily_ic_rankic(panel, factor_col="alpha")
    quintiles = quintile_forward_returns(panel, factor_col="alpha")

    assert np.isclose(daily.loc[0, "ic"], 1.0)
    assert np.isclose(daily.loc[0, "rank_ic"], 1.0)
    assert quintiles.skipped.empty
    assert quintiles.returns["quintile"].tolist() == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert np.allclose(
        quintiles.returns["mean_forward_return"], [0.015, 0.035, 0.055, 0.075, 0.095]
    )
    assert np.all(np.diff(quintiles.returns["mean_forward_return"]) > 0.0)


def test_cross_date_zscore_isolation() -> None:
    first = _golden_panel().assign(date=pd.Timestamp("2024-01-02"))
    second = _golden_panel().assign(date=pd.Timestamp("2024-01-03"), alpha=lambda x: x.alpha * 100)
    panel = pd.concat([first, second], ignore_index=True)
    before = cross_sectional_zscore(panel, factor_col="alpha")
    changed = panel.copy()
    changed.loc[changed["date"] == pd.Timestamp("2024-01-03"), "alpha"] *= 99
    after = cross_sectional_zscore(changed, factor_col="alpha")

    for code in first["code"]:
        assert _row(before, pd.Timestamp("2024-01-02"), code, "factor_zscore") == _row(
            after, pd.Timestamp("2024-01-02"), code, "factor_zscore"
        )


def test_pairwise_null_filtering_uses_only_complete_observations() -> None:
    panel = pd.DataFrame(
        {
            "date": pd.Timestamp("2024-01-02"),
            "code": list("ABCDEF"),
            "signal": [1.0, 2.0, np.nan, 4.0, 5.0, 6.0],
            "forward_return_20": [0.01, 0.02, 0.03, np.nan, 0.05, 0.06],
        }
    )
    daily = daily_ic_rankic(panel, factor_col="signal")

    assert daily.loc[0, "n_pairs"] == 4
    assert np.isclose(daily.loc[0, "ic"], 1.0)
    assert np.isclose(daily.loc[0, "rank_ic"], 1.0)


def test_extreme_value_is_clipped_at_independent_percentile() -> None:
    panel = pd.DataFrame(
        {
            "date": pd.Timestamp("2024-01-02"),
            "code": [f"S{i}" for i in range(10)],
            "signal": [*range(9), 1000.0],
        }
    )
    result = cross_sectional_zscore(panel, factor_col="signal")

    assert np.isclose(_row(result, pd.Timestamp("2024-01-02"), "S9", "factor_winsorized"), 910.72)
    assert np.isclose(_row(result, pd.Timestamp("2024-01-02"), "S0", "factor_winsorized"), 0.09)


def test_constant_values_return_nan_and_record_group_failure() -> None:
    panel = _golden_panel().assign(alpha=7.0, forward_return_20=0.01)
    zscore = cross_sectional_zscore(panel, factor_col="alpha")
    daily = daily_ic_rankic(panel, factor_col="alpha")
    quintiles = quintile_forward_returns(panel, factor_col="alpha")

    assert zscore["factor_zscore"].isna().all()
    assert daily.loc[0, "invalid_reason"] == "constant_factor"
    assert quintiles.returns.empty
    assert quintiles.skipped.loc[0, "reason"] == "fewer_than_five_distinct_factor_values"


def test_insufficient_samples_return_nan_and_skip_quintiles() -> None:
    panel = pd.DataFrame(
        {
            "date": pd.Timestamp("2024-01-02"),
            "code": list("ABCD"),
            "signal": [1.0, np.nan, np.nan, np.nan],
            "forward_return_20": [0.01, 0.02, 0.03, 0.04],
        }
    )
    zscore = cross_sectional_zscore(panel, factor_col="signal")
    daily = daily_ic_rankic(panel, factor_col="signal")
    quintiles = quintile_forward_returns(panel, factor_col="signal")

    assert zscore["factor_zscore"].isna().all()
    assert daily.loc[0, "n_pairs"] == 1
    assert daily.loc[0, "invalid_reason"] == "fewer_than_three_valid_pairs"
    assert quintiles.skipped.loc[0, "reason"] == "fewer_than_five_valid_stocks"


def test_ic_summary_uses_sample_standard_deviation() -> None:
    daily = pd.DataFrame({"ic": [0.1, 0.3], "rank_ic": [0.2, 0.4]})
    summary = summarize_ic(daily)

    assert np.isclose(summary.loc[0, "mean_ic"], 0.2)
    assert np.isclose(summary.loc[0, "mean_rank_ic"], 0.3)
    assert np.isclose(summary.loc[0, "ic_std"], math.sqrt(0.02))
    assert np.isclose(summary.loc[0, "icir"], math.sqrt(2.0))


def test_mean_quintile_returns_weight_dates_equally() -> None:
    first = _golden_panel()
    second = first.assign(date=pd.Timestamp("2024-01-03"), forward_return_20=first.alpha / 50)
    result = quintile_forward_returns(pd.concat([first, second]), "alpha")
    assert np.allclose(result.mean_returns["mean_forward_return"], [.0225, .0525, .0825, .1125, .1425])


def test_configurable_winsorization_and_population_std() -> None:
    panel = _golden_panel()
    result = cross_sectional_zscore(panel, "alpha", winsor_lower=0, winsor_upper=1)
    assert np.isclose(result.factor_zscore.iloc[0], -4.5 / math.sqrt(8.25))
    assert np.isclose(result.factor_zscore.std(ddof=0), 1)
    with pytest.raises(ValueError, match="winsor"):
        cross_sectional_zscore(panel, "alpha", winsor_lower=.9, winsor_upper=.1)


def test_tied_ranks_and_collapsed_quantile_edges() -> None:
    panel = _golden_panel().iloc[:3].assign(alpha=[1, 1, 2], forward_return_20=[1, 2, 3])
    assert np.isclose(daily_ic_rankic(panel, "alpha").rank_ic.iloc[0], math.sqrt(3) / 2)
    collapsed = _golden_panel().assign(alpha=[1, 1, 1, 1, 1, 1, 2, 3, 4, 5])
    result = quintile_forward_returns(collapsed, "alpha")
    assert result.returns.empty
    assert result.skipped.reason.tolist() == ["cannot_form_five_groups"]
    constant = summarize_ic(pd.DataFrame({"ic": [1., 1.], "rank_ic": [1., 1.]}))
    assert np.isnan(constant.icir.iloc[0])


def test_research_key_alignment_immutability_and_constant_label() -> None:
    panel = pd.concat([_golden_panel(), _golden_panel().assign(date=pd.Timestamp("2024-01-03"))])
    panel = panel.sample(frac=1, random_state=3)
    panel.index = [8] * len(panel)
    original = panel.copy(deep=True)
    result = cross_sectional_zscore(panel, "alpha")
    assert np.allclose(result.groupby("date").factor_zscore.std(ddof=0), 1)
    assert np.allclose(daily_ic_rankic(panel, "alpha").ic, 1)
    assert len(quintile_forward_returns(panel, "alpha").returns) == 10
    pd.testing.assert_frame_equal(panel, original)
    constant = daily_ic_rankic(panel.assign(forward_return_20=1.), "alpha")
    assert constant.ic.isna().all()
    assert set(constant.invalid_reason) == {"constant_forward_return"}
    missing = _golden_panel()
    missing.loc[[0, 2, 4, 6, 8, 9], "forward_return_20"] = np.nan
    skipped = quintile_forward_returns(missing, "alpha")
    assert skipped.returns.empty
    assert skipped.skipped.reason.tolist() == ["fewer_than_five_valid_stocks"]
