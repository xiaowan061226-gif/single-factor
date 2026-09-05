"""Integration tests for local CSV diagnostics and actionable research failures."""

from pathlib import Path

import numpy as np
import pandas.testing as pdt
import pytest

from single_factor_quant.__main__ import main
from single_factor_quant.data.loader import load_price_csv
from single_factor_quant.pipeline import make_demo_price_panel, run_research_pipeline


def test_local_csv_pipeline_reports_expected_data_diagnostics(tmp_path, capsys) -> None:
    """Use a temporary local CSV to verify profile fields and the input CLI path."""
    path = tmp_path / "prices.csv"
    make_demo_price_panel().to_csv(path, index=False)
    prices = load_price_csv(path)
    original = prices.copy(deep=True)
    result = run_research_pipeline(prices)
    diagnostics = result.diagnostics
    assert diagnostics.date_start == prices.date.min()
    assert diagnostics.date_end == prices.date.max()
    assert diagnostics.stock_count == 10
    assert diagnostics.observations_per_stock.tolist() == [300] * 10
    assert diagnostics.stocks_with_momentum_history == 10
    assert diagnostics.duplicate_key_count == diagnostics.missing_required_value_count == diagnostics.illegal_close_count == 0
    assert np.isclose(diagnostics.factor_coverage_all, 48 / 300)
    assert diagnostics.factor_coverage_eligible == 1.0
    assert np.isclose(diagnostics.forward_label_coverage, 280 / 300)
    assert diagnostics.valid_ic_dates == 28
    assert diagnostics.skipped_group_dates == 272
    assert diagnostics.executed_rebalances == 2
    pdt.assert_frame_equal(prices, original)
    assert main(["--input", str(path)]) == 0
    output = capsys.readouterr().out
    assert "date_range=" in output and "factor_coverage_eligible=1.0000" in output
    assert "warning: close should be adjusted" in output


def test_sample_csv_is_committed_and_runs_the_complete_local_workflow() -> None:
    """Keep the user-facing sample CSV large enough for all default stages."""
    path = Path("examples/sample_prices.csv")
    prices = load_price_csv(path)
    result = run_research_pipeline(prices)
    assert len(prices) == 3000
    assert prices.code.nunique() == 10
    assert prices.date.nunique() == 300
    assert not result.quintiles.returns.empty
    assert result.diagnostics.executed_rebalances >= 1


def test_history_and_cross_section_fail_with_actionable_messages(tmp_path, capsys) -> None:
    """Reject empty-research inputs instead of emitting an empty result table."""
    prices = make_demo_price_panel()
    short_history = prices.loc[prices.date.isin(sorted(prices.date.unique())[:252])]
    with pytest.raises(ValueError, match=r"insufficient history.*253 rows per stock"):
        run_research_pipeline(short_history)
    small_cross_section = prices.loc[prices.code.isin(["S01", "S02", "S03", "S04"])]
    with pytest.raises(ValueError, match=r"insufficient cross-section.*5 stocks"):
        run_research_pipeline(small_cross_section)
    path = tmp_path / "short.csv"
    short_history.to_csv(path, index=False)
    with pytest.raises(SystemExit) as exit_info:
        main(["--input", str(path)])
    assert exit_info.value.code == 2
    assert "insufficient history" in capsys.readouterr().err
