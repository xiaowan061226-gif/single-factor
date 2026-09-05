"""Compact summaries that consume completed research results without recalculation."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..pipeline import ResearchPipelineResult


def build_research_summary(result: "ResearchPipelineResult") -> dict[str, object]:
    """Build a field-oriented summary from completed pipeline outputs only."""
    if result.ic_summary.empty:
        raise ValueError("pipeline result must include IC summary statistics")
    metrics = result.ic_summary.iloc[0]
    notes: dict[str, str] = {}
    summary: dict[str, object] = {
        "data_date_start": _date_text(result.diagnostics.date_start),
        "data_date_end": _date_text(result.diagnostics.date_end),
        "stock_count": result.diagnostics.stock_count,
        "factor_coverage_all": result.diagnostics.factor_coverage_all,
        "factor_coverage_eligible": result.diagnostics.factor_coverage_eligible,
        "mean_ic": _number(metrics["mean_ic"]),
        "mean_rank_ic": _number(metrics["mean_rank_ic"]),
        "ic_std": _number(metrics["ic_std"]),
        "icir": _number(metrics["icir"]),
        "top_20_cumulative_return": _number(result.backtest.cumulative_return),
        "annualized_return": _number(result.backtest.annualized_return_252),
        "max_drawdown": _number(result.backtest.max_drawdown),
        "average_gross_turnover": _number(result.backtest.daily.gross_turnover.mean()),
        "valid_ic_dates": result.diagnostics.valid_ic_dates,
        "skipped_group_dates": result.diagnostics.skipped_group_dates,
        "executed_rebalances": result.diagnostics.executed_rebalances,
        "adjusted_close_warning": "close should be adjusted for corporate actions; no adjustment was inferred or applied.",
    }
    quintiles = result.quintile_mean_returns.set_index("quintile")["mean_forward_return"]
    for number in range(1, 6):
        key = f"q{number}_mean_forward_return"
        summary[key] = _number(quintiles.get(f"Q{number}"))
    reasons = {
        "mean_ic": "no valid IC dates", "mean_rank_ic": "no valid RankIC dates",
        "ic_std": "fewer than two valid IC dates", "icir": "IC standard deviation is zero or unavailable",
        "top_20_cumulative_return": "backtest return unavailable", "annualized_return": "annualized return unavailable",
        "max_drawdown": "maximum drawdown unavailable", "average_gross_turnover": "no daily turnover rows",
    }
    reasons.update({f"q{number}_mean_forward_return": "no valid observations for this quantile" for number in range(1, 6)})
    notes.update({key: reason for key, reason in reasons.items() if summary[key] is None})
    if summary["factor_coverage_eligible"] is None:
        notes["factor_coverage_eligible"] = "no row has the configured momentum history"
    summary["unavailable"] = notes
    return summary


def format_research_summary(summary: Mapping[str, object]) -> str:
    """Format stable, field-level CLI output without running any research logic."""
    lines = [
        f"date_range={summary['data_date_start']}..{summary['data_date_end']}; stocks={summary['stock_count']}",
        f"factor_coverage_all={_text(summary, 'factor_coverage_all')}; factor_coverage_eligible={_text(summary, 'factor_coverage_eligible')}",
        f"mean_ic={_text(summary, 'mean_ic')}; mean_rank_ic={_text(summary, 'mean_rank_ic')}; ic_std={_text(summary, 'ic_std')}; icir={_text(summary, 'icir')}",
        "quintile_mean_forward_returns=" + "; ".join(
            f"Q{number}:{_text(summary, f'q{number}_mean_forward_return')}" for number in range(1, 6)
        ),
        f"top_20_cumulative_return={_text(summary, 'top_20_cumulative_return')}; annualized_return={_text(summary, 'annualized_return')}; max_drawdown={_text(summary, 'max_drawdown')}; average_gross_turnover={_text(summary, 'average_gross_turnover')}",
        f"valid_ic_dates={summary['valid_ic_dates']}; skipped_group_dates={summary['skipped_group_dates']}; rebalances={summary['executed_rebalances']}",
        f"warning: {summary['adjusted_close_warning']}",
    ]
    unavailable = summary["unavailable"]
    lines.append("unavailable=none" if not unavailable else f"unavailable={unavailable}")
    return "\n".join(lines)


def _number(value: object) -> float | None:
    """Keep a present scalar numeric and represent NaN as unavailable."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _text(summary: Mapping[str, object], key: str) -> str:
    """Format one numeric field, including its unavailable reason when needed."""
    value = summary[key]
    if value is not None:
        return f"{float(value):.6f}"
    reason = summary["unavailable"].get(key, "unavailable")
    return f"n/a ({reason})"


def _date_text(value: object) -> str:
    """Render a date-like diagnostic value without requiring a datetime subtype."""
    return value.date().isoformat() if hasattr(value, "date") else str(value)
