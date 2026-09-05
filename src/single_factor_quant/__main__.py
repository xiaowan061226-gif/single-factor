"""Command-line entry point for the formal research workflow."""

import argparse
from collections.abc import Sequence

from .data.loader import load_price_csv
from .pipeline import make_demo_price_panel, run_research_pipeline


def main(argv: Sequence[str] | None = None) -> int:
    """Run the demo or a validated local price CSV and print compact results."""
    parser = argparse.ArgumentParser(description="Run the single-factor research workflow.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run deterministic synthetic prices")
    source.add_argument("--input", metavar="PATH", help="read a local date/code/close CSV")
    args = parser.parse_args(argv)
    prices = make_demo_price_panel() if args.demo else load_price_csv(args.input)
    try:
        result = run_research_pipeline(prices)
    except ValueError as exc:
        parser.error(str(exc))
    diagnostics = result.diagnostics
    counts = diagnostics.observations_per_stock
    print(f"date_range={diagnostics.date_start.date()}..{diagnostics.date_end.date()}; stocks={diagnostics.stock_count}; rows={diagnostics.row_count}")
    print(f"observations_per_stock=min:{counts.min()}; median:{counts.median():.1f}; max:{counts.max()}; stocks_with_{252}_history={diagnostics.stocks_with_momentum_history}")
    print(f"quality=duplicate_keys:{diagnostics.duplicate_key_count}; missing_required:{diagnostics.missing_required_value_count}; illegal_close:{diagnostics.illegal_close_count}")
    print(f"factor_coverage_all={diagnostics.factor_coverage_all:.4f}; factor_coverage_eligible={_coverage_text(diagnostics.factor_coverage_eligible)}; forward_label_coverage={diagnostics.forward_label_coverage:.4f}")
    print(f"valid_ic_dates={diagnostics.valid_ic_dates}; skipped_group_dates={diagnostics.skipped_group_dates}; rebalances={diagnostics.executed_rebalances}")
    print(f"initial_nav={result.backtest.daily.nav.iloc[0]:.6f}; final_nav={result.backtest.daily.nav.iloc[-1]:.6f}")
    print("warning: close should be adjusted for corporate actions; no adjustment was inferred or applied.")
    return 0


def _coverage_text(value: float | None) -> str:
    """Format an unavailable denominator without turning it into a false zero."""
    return "n/a" if value is None else f"{value:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
