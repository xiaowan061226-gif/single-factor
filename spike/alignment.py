"""Stage-1 synthetic data and compatibility wrappers for formal research code."""

import numpy as np
import pandas as pd

from single_factor_quant.factors.momentum import calculate_momentum
from single_factor_quant.research.forward_return import calculate_forward_returns


def make_synthetic_panel(periods: int = 300) -> pd.DataFrame:
    """Create deterministic two-stock daily prices retained for alignment tests."""
    if periods < 280:
        raise ValueError("periods must be at least 280 for the demo windows")
    dates = pd.bdate_range("2020-01-02", periods=periods)
    steps = np.arange(periods, dtype=float)
    return pd.concat([
        pd.DataFrame({"date": dates, "code": code, "close": base + slope * steps})
        for code, base, slope in (("AAA", 100.0, 1.0), ("BBB", 1000.0, 2.0))
    ], ignore_index=True)


def trailing_momentum_252(panel: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper for formal 252-observation momentum."""
    return calculate_momentum(panel, window=252)


def forward_return_20(panel: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper for formal 20-observation future-return labels."""
    return calculate_forward_returns(panel, horizon=20)


def main() -> None:
    """Print compact stage-1 boundary checks using the formal module APIs."""
    panel = make_synthetic_panel()
    result = trailing_momentum_252(panel).merge(
        forward_return_20(panel), on=["date", "code"], validate="one_to_one"
    )
    first_eligible = panel.loc[252, "date"]
    assert np.isclose(result.loc[(result.date == first_eligible) & (result.code == "AAA"), "momentum_252"].iloc[0], 2.52)
    assert result.loc[result.code == "BBB", "momentum_252"].iloc[:252].isna().all()
    changed = panel.copy()
    changed.loc[changed.date > first_eligible, "close"] *= 7
    pd.testing.assert_frame_equal(
        trailing_momentum_252(panel).loc[panel.date <= first_eligible],
        trailing_momentum_252(changed).loc[panel.date <= first_eligible],
    )
    print("cross_code_guard=PASS")
    print("lookahead_guard=PASS")


if __name__ == "__main__":
    main()
