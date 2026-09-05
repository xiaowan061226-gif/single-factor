"""Formal future-label API tests using stage-1 hand-calculated invariants."""

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from single_factor_quant.research.forward_return import calculate_forward_returns
from spike.alignment import forward_return_20


def _prices() -> pd.DataFrame:
    """Build independent price paths whose future labels are hand-checkable."""
    dates = pd.bdate_range("2021-01-04", periods=300)
    return pd.concat([
        pd.DataFrame({"date": dates, "code": "AAA", "close": 100.0 + np.arange(300)}),
        pd.DataFrame({"date": dates, "code": "BBB", "close": 1000.0 + 2.0 * np.arange(300)}),
    ], ignore_index=True)


def _key_sorted(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare labels by their durable panel keys rather than input order."""
    return frame.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def test_formal_forward_return_matches_hand_calculation_and_spike() -> None:
    prices = _prices().sample(frac=1, random_state=8).reset_index(drop=True)
    actual = calculate_forward_returns(prices)
    pdt.assert_frame_equal(_key_sorted(actual), _key_sorted(forward_return_20(prices)))
    date = pd.Timestamp("2021-01-04")
    assert np.isclose(actual.loc[(actual.date == date) & (actual.code == "AAA"), "forward_return_20"].iloc[0], .2)
    assert _key_sorted(actual).groupby("code").forward_return_20.tail(20).isna().all()


def test_formal_forward_return_is_immutable_and_responds_only_to_its_horizon() -> None:
    prices = _prices()
    original = prices.copy(deep=True)
    before = calculate_forward_returns(prices, horizon=2, output_col="label")
    changed = prices.copy()
    changed.loc[(changed.code == "AAA") & (changed.date == prices.date.iloc[2]), "close"] *= 2
    after = calculate_forward_returns(changed, horizon=2, output_col="label")
    assert np.isclose(before.loc[(before.code == "AAA") & (before.date == prices.date.iloc[0]), "label"].iloc[0], .02)
    assert np.isclose(after.loc[(after.code == "AAA") & (after.date == prices.date.iloc[0]), "label"].iloc[0], 1.04)
    pdt.assert_frame_equal(prices, original)
    with pytest.raises(ValueError, match="horizon"):
        calculate_forward_returns(prices, horizon=True)
