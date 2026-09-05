"""Strict CSV loading for the project-wide price panel contract."""

import csv
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_PRICE_COLUMNS = ("date", "code", "close")


def load_price_csv(path: str | Path) -> pd.DataFrame:
    """Load, validate, and key-sort a date/code/close CSV without repairing it.

    Codes are read as strings from the outset so values such as ``000001`` keep
    their leading zeroes.  Any missing, invalid, or duplicate input is rejected
    with a count and a small row/value sample; no rows are filled, aggregated,
    or dropped.
    """
    _validate_csv_shape(path)
    try:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("empty CSV: count=0, examples=[]") from exc
    missing_columns = [column for column in REQUIRED_PRICE_COLUMNS if column not in raw]
    if missing_columns:
        raise ValueError(
            "missing required columns: "
            f"count={len(missing_columns)}, examples={missing_columns[:3]}"
        )

    if raw.empty:
        raise ValueError("empty price rows: count=0, examples=[]")
    _raise_if_missing(raw, "date")
    _raise_if_missing(raw, "code")
    _raise_if_missing(raw, "close")
    dates = _parse_dates(raw["date"])
    codes = _normalize_codes(raw["code"])
    closes = _parse_closes(raw["close"])
    clean = pd.DataFrame({"date": dates, "code": codes, "close": closes})
    _raise_if_duplicate_keys(clean)
    clean = clean.sort_values(["code", "date"], kind="stable").reset_index(drop=True).copy()
    clean.attrs["price_adjustment_warning"] = (
        "close must be adjusted for corporate actions; adjustment is not verified or applied."
    )
    return clean


def _raise_if_missing(raw: pd.DataFrame, column: str) -> None:
    """Raise a sampled error when a required CSV field is empty or absent."""
    missing = raw[column].isna() | raw[column].eq("")
    if missing.any():
        _raise_value_error(column, "missing values", raw.loc[missing, column])


def _validate_csv_shape(path: str | Path) -> None:
    """Reject ragged CSV records before pandas can infer and discard an index."""
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        try:
            header = next(reader, [])
            if len(set(header)) != len(header):
                raise ValueError(f"duplicate CSV columns: count={len(header) - len(set(header))}, examples={header[:3]}")
            count, examples = 0, []
            for row in reader:
                if len(row) != len(header):
                    count += 1
                    if len(examples) < 3:
                        examples.append((reader.line_num, row))
            if count:
                raise ValueError(f"CSV row width mismatch: count={count}, examples={examples}")
        except csv.Error as exc:
            raise ValueError(f"invalid CSV syntax: count=1, examples=[line {reader.line_num}: {exc}]") from exc


def _parse_dates(values: pd.Series) -> pd.Series:
    """Convert every non-missing date value to datetime or raise with examples."""
    parsed = pd.to_datetime(values, errors="coerce")
    invalid = parsed.isna()
    if invalid.any():
        _raise_value_error("date", "invalid datetime values", values.loc[invalid])
    return parsed


def _normalize_codes(values: pd.Series) -> pd.Series:
    """Trim code whitespace while preserving the original non-empty character data."""
    normalized = values.astype(str).str.strip()
    empty = normalized.eq("")
    if empty.any():
        _raise_value_error("code", "empty string values", values.loc[empty])
    return normalized


def _parse_closes(values: pd.Series) -> pd.Series:
    """Convert close values and reject non-numeric, non-finite, or non-positive data."""
    parsed = pd.to_numeric(values, errors="coerce")
    invalid = parsed.isna()
    if invalid.any():
        _raise_value_error("close", "non-numeric values", values.loc[invalid])
    nonfinite = ~np.isfinite(parsed)
    if nonfinite.any():
        _raise_value_error("close", "non-finite values", values.loc[nonfinite])
    nonpositive = parsed.le(0)
    if nonpositive.any():
        _raise_value_error("close", "non-positive values", values.loc[nonpositive])
    return parsed.astype(float)


def _raise_if_duplicate_keys(clean: pd.DataFrame) -> None:
    """Reject every row participating in a duplicate date/code key."""
    duplicate = clean.duplicated(["date", "code"], keep=False)
    if duplicate.any():
        examples = clean.loc[duplicate, ["date", "code"]].head(3).to_dict("records")
        raise ValueError(f"duplicate (date, code) keys: count={int(duplicate.sum())}, examples={examples}")


def _raise_value_error(column: str, issue: str, values: pd.Series) -> None:
    """Produce one consistent, count-and-sample validation message."""
    examples = [(int(index), value) for index, value in values.head(3).items()]
    raise ValueError(f"{column} {issue}: count={len(values)}, examples={examples}")
