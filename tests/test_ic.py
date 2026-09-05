"""Formal IC API tests retained from the stage-2 golden research sample."""

import math

import numpy as np
import pandas as pd
import pandas.testing as pdt

from single_factor_quant.research.ic import daily_ic_rankic, summarize_ic
from spike.research import daily_ic_rankic as spike_daily_ic_rankic


def _golden_panel() -> pd.DataFrame:
    """Build ten same-date stocks with factor and future label in the same order."""
    return pd.DataFrame({"date": pd.Timestamp("2024-01-02"),
                         "code": [f"S{i:02d}" for i in range(1, 11)],
                         "alpha": np.arange(1.0, 11.0),
                         "forward_return_20": np.arange(1.0, 11.0) / 100})


def test_formal_ic_matches_golden_values_and_spike() -> None:
    panel = _golden_panel().sample(frac=1, random_state=12).reset_index(drop=True)
    actual = daily_ic_rankic(panel, factor_col="alpha")
    pdt.assert_frame_equal(actual, spike_daily_ic_rankic(panel, factor_col="alpha"))
    assert np.allclose(actual.loc[0, ["ic", "rank_ic"]].astype(float), [1, 1])
    summary = summarize_ic(pd.DataFrame({"ic": [.1, .3], "rank_ic": [.2, .4]}))
    assert np.isclose(summary.ic_std.iloc[0], math.sqrt(.02))
    assert np.isclose(summary.icir.iloc[0], math.sqrt(2))


def test_formal_ic_pairwise_null_filtering_and_input_immutability() -> None:
    panel = _golden_panel().assign(alpha=[1, 2, np.nan, 4, 5, 6, 7, 8, 9, 10],
                                   forward_return_20=[.01, .02, .03, np.nan, .05, .06, .07, .08, .09, .1])
    original = panel.copy(deep=True)
    actual = daily_ic_rankic(panel, "alpha")
    assert actual.n_pairs.iloc[0] == 8
    assert actual.ic.iloc[0] == 1
    pdt.assert_frame_equal(panel, original)
    assert daily_ic_rankic(panel.assign(alpha=1), "alpha").invalid_reason.iloc[0] == "constant_factor"
