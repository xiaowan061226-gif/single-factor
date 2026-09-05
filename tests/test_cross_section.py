"""Formal cross-sectional preprocessing tests retained from the golden spike."""

import math

import numpy as np
import pandas as pd
import pandas.testing as pdt

from single_factor_quant.preprocess.cross_section import cross_sectional_zscore
from spike.research import cross_sectional_zscore as spike_zscore


def _golden_panel() -> pd.DataFrame:
    """Create ten dated stocks with a known population standard deviation."""
    return pd.DataFrame({"date": pd.Timestamp("2024-01-02"),
                         "code": [f"S{i:02d}" for i in range(1, 11)],
                         "alpha": np.arange(1.0, 11.0)})


def _key_sorted(frame: pd.DataFrame) -> pd.DataFrame:
    """Order preprocessed results by the durable panel key for comparison."""
    return frame.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def test_formal_zscore_matches_golden_values_and_spike() -> None:
    panel = _golden_panel().sample(frac=1, random_state=4).reset_index(drop=True)
    actual = cross_sectional_zscore(panel, "alpha", winsor_lower=0, winsor_upper=1)
    expected = spike_zscore(panel, "alpha", winsor_lower=0, winsor_upper=1)
    pdt.assert_frame_equal(_key_sorted(actual), _key_sorted(expected))
    assert np.isclose(_key_sorted(actual).factor_zscore.iloc[0], -4.5 / math.sqrt(8.25))
    assert np.isclose(actual.factor_zscore.std(ddof=0), 1)


def test_formal_zscore_is_date_local_and_does_not_modify_input() -> None:
    first = _golden_panel()
    panel = pd.concat([first, first.assign(date=pd.Timestamp("2024-01-03"), alpha=lambda x: x.alpha * 100)])
    original = panel.copy(deep=True)
    before = cross_sectional_zscore(panel, "alpha")
    changed = panel.copy()
    changed.loc[changed.date == pd.Timestamp("2024-01-03"), "alpha"] *= 99
    after = cross_sectional_zscore(changed, "alpha")
    pdt.assert_frame_equal(
        _key_sorted(before.loc[before.date == pd.Timestamp("2024-01-02")]),
        _key_sorted(after.loc[after.date == pd.Timestamp("2024-01-02")]),
    )
    pdt.assert_frame_equal(panel, original)
