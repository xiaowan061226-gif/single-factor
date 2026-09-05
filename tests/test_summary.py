"""Regression tests for field-oriented, read-only research summaries."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pandas.testing as pdt

from single_factor_quant.__main__ import main
from single_factor_quant.pipeline import make_demo_price_panel, run_research_pipeline
from single_factor_quant.reports.summary import build_research_summary, format_research_summary


def test_summary_contains_required_demo_metrics_without_mutating_results() -> None:
    """Assert stable metric fields and known demo invariants, not full text layout."""
    result = run_research_pipeline(make_demo_price_panel())
    original_daily = result.backtest.daily.copy(deep=True)
    summary = build_research_summary(result)
    required = {
        "data_date_start", "data_date_end", "stock_count", "factor_coverage_all",
        "factor_coverage_eligible", "mean_ic", "mean_rank_ic", "ic_std", "icir",
        "top_20_cumulative_return", "annualized_return", "max_drawdown",
        "average_gross_turnover", "valid_ic_dates", "skipped_group_dates", "executed_rebalances",
        "adjusted_close_warning", "unavailable",
        *(f"q{number}_mean_forward_return" for number in range(1, 6)),
    }
    assert required.issubset(summary)
    assert summary["data_date_start"] == "2020-01-02"
    assert summary["data_date_end"] == "2021-02-24"
    assert summary["stock_count"] == 10
    assert np.isclose(summary["factor_coverage_all"], .16)
    assert summary["factor_coverage_eligible"] == 1.0
    assert summary["valid_ic_dates"] == 28
    assert summary["skipped_group_dates"] == 272
    assert summary["executed_rebalances"] == 2
    assert all(summary[f"q{number}_mean_forward_return"] is not None for number in range(1, 6))
    assert summary["unavailable"] == {}
    pdt.assert_frame_equal(result.backtest.daily, original_daily)


def test_summary_explains_nan_metrics_and_formatter_exposes_reason() -> None:
    """A missing value must remain visible with its reason rather than become zero."""
    result = run_research_pipeline(make_demo_price_panel())
    nan_ic_summary = pd.DataFrame([{"mean_ic": np.nan, "mean_rank_ic": np.nan, "ic_std": np.nan, "icir": np.nan}])
    summary = build_research_summary(replace(result, ic_summary=nan_ic_summary))
    assert summary["mean_ic"] is None
    assert summary["unavailable"]["mean_ic"] == "no valid IC dates"
    assert "mean_ic=n/a (no valid IC dates)" in format_research_summary(summary)


def test_cli_summary_contains_key_metrics_and_warning(capsys) -> None:
    """Protect meaningful CLI fields while allowing harmless whitespace changes."""
    assert main(["--demo"]) == 0
    output = capsys.readouterr().out
    for field in ("mean_rank_ic=", "quintile_mean_forward_returns=", "average_gross_turnover=", "unavailable=", "warning:"):
        assert field in output
