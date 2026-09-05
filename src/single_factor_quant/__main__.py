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
    result = run_research_pipeline(prices)
    executed = int((result.backtest.rebalances.status == "executed").sum())
    valid_ic = int(result.daily_ic.ic.notna().sum())
    print(f"rows={len(result.factor_data)}; valid_ic_dates={valid_ic}; quintile_rows={len(result.quintiles.returns)}")
    print(f"initial_nav={result.backtest.daily.nav.iloc[0]:.6f}; final_nav={result.backtest.daily.nav.iloc[-1]:.6f}; rebalances={executed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
