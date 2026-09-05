"""Generate the deterministic local CSV used by the stage-7 input example."""

from pathlib import Path

from single_factor_quant.pipeline import make_demo_price_panel


def main() -> None:
    """Write the 10-stock, 300-session sample without downloading any data."""
    target = Path(__file__).with_name("sample_prices.csv")
    make_demo_price_panel().to_csv(target, index=False)
    print(target)


if __name__ == "__main__":
    main()
