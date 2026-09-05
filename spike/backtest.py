"""Stage-3 data and compatibility exports for the formal simple backtest."""

import numpy as np
import pandas as pd

from single_factor_quant.backtest.simple_backtest import BacktestResult, run_top_quantile_backtest


def make_backtest_demo_panel(periods: int = 42) -> pd.DataFrame:
    """Create the deterministic five-stock hand-calculation panel retained for tests."""
    if periods < 22:
        raise ValueError("periods must be at least 22")
    dates = pd.bdate_range("2024-01-02", periods=periods)
    frames = []
    for code, rank in zip("ABCDE", range(5, 0, -1), strict=True):
        close = np.full(periods, 100.0)
        if code == "A" and periods > 2:
            close[2:] = 110.0
        if code == "B" and periods > 22:
            close[22:] = 120.0
        alpha = np.full(periods, float(rank))
        if periods > 20:
            alpha[20:] = {"A": 4.0, "B": 5.0, "C": 3.0, "D": 2.0, "E": 1.0}[code]
        frames.append(pd.DataFrame({"date": dates, "code": code, "close": close, "alpha": alpha}))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    """Run the historical stage-3 demo through the formal backtest API."""
    result = run_top_quantile_backtest(make_backtest_demo_panel(), "alpha")
    assert np.isclose(result.daily.nav.iloc[1], .999)
    assert np.isclose(result.daily.nav.iloc[2], 1.0989)
    zero_cost = run_top_quantile_backtest(make_backtest_demo_panel(), "alpha", cost_rate=0)
    assert np.isclose(zero_cost.daily.nav.iloc[-1], 1.32)
    assert np.isclose(result.daily.nav.iloc[-1], 1.31604264)
    print(f"zero_cost_nav={zero_cost.daily.nav.iloc[-1]:.8f}; cost_nav={result.daily.nav.iloc[-1]:.8f}")
    print("PASS")


if __name__ == "__main__":
    main()
