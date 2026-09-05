"""Tests for strict, non-repairing CSV price-panel loading."""

import numpy as np
import pandas as pd
import pytest

from single_factor_quant.data.loader import load_price_csv


def _write_csv(tmp_path, rows: list[dict[str, object]], columns: list[str] | None = None):
    """Write test data exactly as CSV text while retaining code zeroes."""
    path = tmp_path / "prices.csv"
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return path


def test_loads_unsorted_rows_with_datetime_close_and_leading_zero_codes(tmp_path) -> None:
    path = _write_csv(
        tmp_path,
        [
            {"date": "2024-01-03", "code": "000002", "close": "12.5", "extra": "x"},
            {"date": "2024-01-02", "code": "000001", "close": "10", "extra": "y"},
            {"date": "2024-01-01", "code": "000002", "close": "11", "extra": "z"},
        ],
    )
    loaded = load_price_csv(path)

    assert loaded.columns.tolist() == ["date", "code", "close"]
    assert loaded["code"].tolist() == ["000001", "000002", "000002"]
    assert loaded["date"].tolist() == list(pd.to_datetime(["2024-01-02", "2024-01-01", "2024-01-03"]))
    assert loaded["close"].tolist() == [10.0, 11.0, 12.5]
    assert pd.api.types.is_datetime64_any_dtype(loaded["date"])
    assert "not verified" in loaded.attrs["price_adjustment_warning"]


def test_missing_required_column_reports_count_and_example(tmp_path) -> None:
    path = _write_csv(tmp_path, [{"date": "2024-01-02", "code": "000001"}])

    with pytest.raises(ValueError, match=r"missing required columns: count=1.*close"):
        load_price_csv(path)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("date", None, r"date missing values: count=1.*examples"),
        ("code", None, r"code missing values: count=1.*examples"),
        ("code", "   ", r"code empty string values: count=1.*examples"),
        ("close", None, r"close missing values: count=1.*examples"),
    ],
)
def test_missing_required_values_report_count_and_example(tmp_path, column, value, message) -> None:
    row = {"date": "2024-01-02", "code": "000001", "close": "10"}
    row[column] = value
    path = _write_csv(tmp_path, [row])

    with pytest.raises(ValueError, match=message):
        load_price_csv(path)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("date", "not-a-date", r"date invalid datetime values: count=1.*not-a-date"),
        ("close", "not-a-number", r"close non-numeric values: count=1.*not-a-number"),
    ],
)
def test_conversion_errors_report_count_and_example(tmp_path, column, value, message) -> None:
    row = {"date": "2024-01-02", "code": "000001", "close": "10"}
    row[column] = value
    path = _write_csv(tmp_path, [row])

    with pytest.raises(ValueError, match=message):
        load_price_csv(path)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("inf", r"close non-finite values: count=1.*inf"),
        ("-inf", r"close non-finite values: count=1.*inf"),
        ("0", r"close non-positive values: count=1.*0"),
        ("-1", r"close non-positive values: count=1.*-1"),
    ],
)
def test_illegal_prices_report_count_and_example(tmp_path, value, message) -> None:
    path = _write_csv(tmp_path, [{"date": "2024-01-02", "code": "000001", "close": value}])

    with pytest.raises(ValueError, match=message):
        load_price_csv(path)


def test_duplicate_keys_report_all_duplicate_rows_with_sample(tmp_path) -> None:
    path = _write_csv(
        tmp_path,
        [
            {"date": "2024-01-02", "code": "000001", "close": "10"},
            {"date": "2024-01-02", "code": "000001", "close": "11"},
            {"date": "2024-01-03", "code": "000002", "close": "12"},
        ],
    )

    with pytest.raises(ValueError, match=r"duplicate \(date, code\) keys: count=2.*000001"):
        load_price_csv(path)


def test_literal_na_code_is_preserved(tmp_path) -> None:
    path = _write_csv(tmp_path, [{"date": "2024-01-02", "code": "NA", "close": "10"}])
    assert load_price_csv(path).code.tolist() == ["NA"]


@pytest.mark.parametrize("content", ["", "date,code,close\n"])
def test_empty_csv_reports_count_and_examples(tmp_path, content) -> None:
    path = tmp_path / "empty.csv"
    path.write_text(content)
    with pytest.raises(ValueError, match=r"empty.*count=0.*examples"):
        load_price_csv(path)


def test_trimmed_code_duplicate_is_rejected(tmp_path) -> None:
    path = tmp_path / "duplicates.csv"
    path.write_text("date,code,close\n2024-01-02,000001,10\n2024-01-02, 000001 ,11\n")
    with pytest.raises(ValueError, match=r"duplicate.*count=2.*000001"):
        load_price_csv(path)


@pytest.mark.parametrize("row", ["extra,2024-01-02,000001,10", "2024-01-02,000001"])
def test_malformed_row_is_not_silently_truncated(tmp_path, row) -> None:
    path = tmp_path / "malformed.csv"
    path.write_text("date,code,close\n" + row + "\n")
    with pytest.raises(ValueError, match=r"CSV row width.*count=1.*examples"):
        load_price_csv(path)
