"""Future-return research labels."""

import pandas as pd

from ._panel import restore_keyed_values, sorted_price_panel


def calculate_forward_returns(
    panel: pd.DataFrame, horizon: int = 20, output_col: str | None = None
) -> pd.DataFrame:
    """Calculate per-code ``close_(t+horizon) / close_t - 1`` labels by keys."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be an integer at least 1")
    column = output_col or f"forward_return_{horizon}"
    if not isinstance(column, str) or not column:
        raise ValueError("output_col must be a non-empty string")
    ordered, input_keys = sorted_price_panel(panel)
    ordered[column] = ordered.groupby("code", sort=False)["close"].transform(
        lambda close: close.shift(-horizon) / close - 1.0
    )
    return restore_keyed_values(input_keys, ordered, column)
