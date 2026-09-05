"""Formal quantile grouping tests retained from the stage-2 golden sample."""

import numpy as np
import pandas as pd
import pandas.testing as pdt

from single_factor_quant.research.grouping import quintile_forward_returns
from spike.research import quintile_forward_returns as spike_quintile_forward_returns


def _golden_panel() -> pd.DataFrame:
    """Build ten same-date stocks with strictly rising factor and label values."""
    return pd.DataFrame({"date": pd.Timestamp("2024-01-02"),
                         "code": [f"S{i:02d}" for i in range(1, 11)],
                         "alpha": np.arange(1.0, 11.0),
                         "forward_return_20": np.arange(1.0, 11.0) / 100})


def test_formal_grouping_matches_golden_values_and_spike() -> None:
    panel = _golden_panel().sample(frac=1, random_state=13).reset_index(drop=True)
    actual = quintile_forward_returns(panel, "alpha")
    expected = spike_quintile_forward_returns(panel, "alpha")
    pdt.assert_frame_equal(actual.returns, expected.returns)
    pdt.assert_frame_equal(actual.skipped, expected.skipped)
    assert actual.returns.quintile.tolist() == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert np.allclose(actual.returns.mean_forward_return, [.015, .035, .055, .075, .095])


def test_formal_grouping_supports_custom_factor_and_preserves_input() -> None:
    panel = _golden_panel().rename(columns={"alpha": "alternative_factor"})
    original = panel.copy(deep=True)
    actual = quintile_forward_returns(panel, "alternative_factor")
    assert actual.skipped.empty
    assert np.all(np.diff(actual.returns.mean_forward_return) > 0)
    pdt.assert_frame_equal(panel, original)
    skipped = quintile_forward_returns(panel.assign(alternative_factor=1), "alternative_factor")
    assert skipped.skipped.reason.iloc[0] == "fewer_than_five_distinct_factor_values"
