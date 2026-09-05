"""End-to-end tests for the formal synthetic-data research pipeline and CLI."""

import numpy as np
import pandas as pd
import pandas.testing as pdt

from single_factor_quant.__main__ import main
from single_factor_quant.pipeline import make_demo_price_panel, run_research_pipeline


def test_demo_pipeline_produces_ordered_key_safe_finite_outputs() -> None:
    prices = make_demo_price_panel()
    original = prices.copy(deep=True)
    result = run_research_pipeline(prices)
    assert not result.factor_data.empty
    assert not result.factor_data.duplicated(["date", "code"]).any()
    assert result.factor_data.date.is_monotonic_increasing
    assert result.daily_ic.date.is_monotonic_increasing
    assert result.backtest.daily.date.is_monotonic_increasing
    assert not result.quintiles.returns.empty
    assert (result.backtest.rebalances.status == "executed").any()
    assert result.backtest.daily.nav.iloc[0] == 1.0
    assert np.isfinite(result.backtest.daily.nav).all()
    pdt.assert_frame_equal(prices, original)


def test_cli_accepts_demo_and_local_csv(tmp_path, capsys) -> None:
    assert main(["--demo"]) == 0
    assert "initial_nav=1.000000" in capsys.readouterr().out
    path = tmp_path / "demo_prices.csv"
    make_demo_price_panel().to_csv(path, index=False)
    assert main(["--input", str(path)]) == 0
    assert "final_nav=" in capsys.readouterr().out
