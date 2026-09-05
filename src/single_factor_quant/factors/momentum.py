"""Time-series momentum factor."""

import pandas as pd

from ..research._panel import restore_keyed_values, sorted_price_panel


def calculate_momentum(
    panel: pd.DataFrame, window: int = 252, output_col: str | None = None
) -> pd.DataFrame:
    """Calculate per-code ``close_t / close_(t-window) - 1`` by explicit keys."""
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError("window must be an integer at least 1")
    column = output_col or f"momentum_{window}"
    if not isinstance(column, str) or not column:
        raise ValueError("output_col must be a non-empty string")
    ordered, input_keys = sorted_price_panel(panel)
    ordered[column] = ordered.groupby("code", sort=False)["close"].transform(
        lambda close: close / close.shift(window) - 1.0
    )
    return restore_keyed_values(input_keys, ordered, column)
