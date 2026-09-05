"""Formal momentum API tests using stage-1 hand-calculated invariants."""

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from single_factor_quant.factors.momentum import calculate_momentum
from spike.alignment import trailing_momentum_252


def _prices() -> pd.DataFrame:
    """Create the two-stock deterministic panel retained from the alignment spike."""
    dates = pd.bdate_range("2021-01-04", periods=300)
    return pd.concat([
        pd.DataFrame({"date": dates, "code": "AAA", "close": 100.0 + np.arange(300)}),
        pd.DataFrame({"date": dates, "code": "BBB", "close": 1000.0 + 2.0 * np.arange(300)}),
    ], ignore_index=True)


def _key_sorted(frame: pd.DataFrame) -> pd.DataFrame:
    """Make output order irrelevant while retaining explicit key comparisons."""
    return frame.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def test_formal_momentum_matches_hand_calculation_and_spike() -> None:
    prices = _prices().sample(frac=1, random_state=7).reset_index(drop=True)
    actual = calculate_momentum(prices)
    pdt.assert_frame_equal(_key_sorted(actual), _key_sorted(trailing_momentum_252(prices)))
    date = pd.Timestamp("2021-12-22")
    assert actual.loc[(actual.date == date) & (actual.code == "AAA"), "momentum_252"].iloc[0] == 2.52
    assert _key_sorted(actual).groupby("code").momentum_252.head(252).isna().all()


def test_formal_momentum_is_key_safe_immutable_and_custom_named() -> None:
    prices = _prices()
    third_date = prices.date.iloc[2]
    prices.index = [4] * len(prices)
    original = prices.copy(deep=True)
    result = calculate_momentum(prices, window=2, output_col="my_factor")
    assert result.columns.tolist() == ["date", "code", "my_factor"]
    assert np.isclose(result.loc[(result.code == "BBB") & (result.date == third_date), "my_factor"].iloc[0], 4 / 1000)
    pdt.assert_frame_equal(prices, original)
    with pytest.raises(ValueError, match="window"):
        calculate_momentum(prices, window=0)
