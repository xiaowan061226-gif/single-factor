"""Small validation helpers shared by formal research modules."""

from collections.abc import Iterable

import numpy as np
import pandas as pd


def keyed_numeric_copy(
    panel: pd.DataFrame, value_columns: Iterable[str], *, require_positive: bool = False
) -> pd.DataFrame:
    """Return validated date/code/value columns without mutating ``panel``.

    Values may be missing when they are research inputs such as an unavailable
    factor or future-return label.  Present values must be finite; prices can
    additionally be required to be positive.
    """
    if not isinstance(panel, pd.DataFrame):
        raise TypeError("panel must be a pandas DataFrame")
    values = tuple(value_columns)
    required = {"date", "code", *values}
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"panel is missing required columns: {sorted(missing)}")
    working = panel.loc[:, ["date", "code", *values]].copy()
    if working[["date", "code"]].isna().any().any():
        raise ValueError("date and code must not contain missing values")
    if working.duplicated(["date", "code"]).any():
        raise ValueError("(date, code) must uniquely identify each panel row")
    for column in values:
        working[column] = pd.to_numeric(working[column], errors="raise")
        present = working.loc[working[column].notna(), column].to_numpy()
        if not np.isfinite(present).all():
            raise ValueError(f"{column} must contain only finite values or NaN")
        if require_positive and (working[column] <= 0).any():
            raise ValueError(f"{column} must contain only positive values")
    return working


def sorted_price_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate price keys and return sorted calculation data plus input keys."""
    working = keyed_numeric_copy(panel, ("close",), require_positive=True)
    keys = working.loc[:, ["date", "code"]].copy()
    return working.sort_values(["code", "date"], kind="stable").reset_index(drop=True), keys


def restore_keyed_values(
    input_keys: pd.DataFrame, calculated: pd.DataFrame, value_column: str
) -> pd.DataFrame:
    """Attach a calculated column to original keys through a validated merge."""
    values = calculated.loc[:, ["date", "code", value_column]]
    return input_keys.merge(
        values, on=["date", "code"], how="left", sort=False, validate="one_to_one"
    )
