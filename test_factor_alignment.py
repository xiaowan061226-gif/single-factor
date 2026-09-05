"""Tests for the stage-1 time-alignment spike."""

import numpy as np
import pandas as pd
import pandas.testing as pdt

from factor_alignment import forward_return_20, make_synthetic_panel, trailing_momentum_252


def _panel() -> pd.DataFrame:
    """Build independent, simple prices with deliberately different stock scales."""
    dates = pd.bdate_range("2021-01-04", periods=300)
    return pd.concat(
        [
            pd.DataFrame({"date": dates, "code": "AAA", "close": 100.0 + np.arange(300)}),
            pd.DataFrame({"date": dates, "code": "BBB", "close": 1000.0 + 2.0 * np.arange(300)}),
        ],
        ignore_index=True,
    )


def _value_at(result: pd.DataFrame, date: pd.Timestamp, code: str, column: str) -> float:
    """Read one calculated value by its explicit panel key."""
    return result.loc[(result["date"] == date) & (result["code"] == code), column].iloc[0]


def test_two_stocks_never_cross_groups() -> None:
    panel = _panel()
    result = trailing_momentum_252(panel)
    date = panel.loc[252, "date"]

    assert _value_at(result, date, "AAA", "momentum_252") == (352.0 / 100.0 - 1.0)
    assert _value_at(result, date, "BBB", "momentum_252") == (1504.0 / 1000.0 - 1.0)


def test_window_boundaries_are_nan_per_stock() -> None:
    panel = _panel()
    momentum = trailing_momentum_252(panel)
    future = forward_return_20(panel)

    for code in ("AAA", "BBB"):
        code_momentum = momentum.loc[momentum["code"] == code, "momentum_252"]
        code_future = future.loc[future["code"] == code, "forward_return_20"]
        assert code_momentum.iloc[:252].isna().all()
        assert code_future.iloc[-20:].isna().all()


def test_scrambled_input_has_identical_key_aligned_results() -> None:
    panel = _panel()
    scrambled = panel.sample(frac=1.0, random_state=7).reset_index(drop=True)

    expected = trailing_momentum_252(panel).sort_values(["date", "code"]).reset_index(drop=True)
    actual = trailing_momentum_252(scrambled).sort_values(["date", "code"]).reset_index(drop=True)
    pdt.assert_frame_equal(actual, expected)

    expected_future = forward_return_20(panel).sort_values(["date", "code"]).reset_index(drop=True)
    actual_future = forward_return_20(scrambled).sort_values(["date", "code"]).reset_index(drop=True)
    pdt.assert_frame_equal(actual_future, expected_future)


def test_price_after_t_does_not_change_t_momentum() -> None:
    panel = _panel()
    t = 260
    before = trailing_momentum_252(panel)
    changed = panel.copy()
    changed.loc[(changed["code"] == "AAA") & (changed["date"] == panel.loc[t + 1, "date"]), "close"] *= 9
    after = trailing_momentum_252(changed)
    date = panel.loc[t, "date"]

    expected = panel.loc[t, "close"] / panel.loc[t - 252, "close"] - 1.0
    assert _value_at(before, date, "AAA", "momentum_252") == expected
    assert _value_at(after, date, "AAA", "momentum_252") == expected


def test_price_at_t_plus_20_changes_t_future_label() -> None:
    panel = _panel()
    t = 260
    date = panel.loc[t, "date"]
    before = forward_return_20(panel)
    changed = panel.copy()
    target_date = panel.loc[t + 20, "date"]
    changed.loc[(changed["code"] == "AAA") & (changed["date"] == target_date), "close"] *= 2
    after = forward_return_20(changed)

    expected_before = panel.loc[t + 20, "close"] / panel.loc[t, "close"] - 1.0
    expected_after = (panel.loc[t + 20, "close"] * 2) / panel.loc[t, "close"] - 1.0
    assert _value_at(before, date, "AAA", "forward_return_20") == expected_before
    assert _value_at(after, date, "AAA", "forward_return_20") == expected_after
    assert expected_after != expected_before


def test_synthetic_panel_is_deterministic() -> None:
    pdt.assert_frame_equal(make_synthetic_panel(), make_synthetic_panel())
