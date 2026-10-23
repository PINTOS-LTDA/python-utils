"""Offline tests for converting materialized SQL script results to Polars."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from math import isnan

import polars as pl
import pytest

from pintos_utils.database import (
    DataFrameDatabaseError,
    SqlScriptResult,
    sql_script_result_to_dataframe,
)


def test_conversion_preserves_rows_and_metadata_column_order() -> None:
    result = SqlScriptResult(
        rows=[{"alpha": 1, "beta": "one"}, {"alpha": 2, "beta": "two"}],
        columns=["beta", "alpha"],
    )

    frame = sql_script_result_to_dataframe(result)

    assert isinstance(frame, pl.DataFrame)
    assert frame.columns == ["beta", "alpha"]
    assert frame.to_dicts() == [
        {"beta": "one", "alpha": 1},
        {"beta": "two", "alpha": 2},
    ]


def test_conversion_preserves_known_empty_schema() -> None:
    frame = sql_script_result_to_dataframe(SqlScriptResult(columns=["second", "first"]))

    assert frame.shape == (0, 2)
    assert frame.columns == ["second", "first"]


def test_conversion_of_unknown_empty_result_is_zero_by_zero() -> None:
    frame = sql_script_result_to_dataframe(SqlScriptResult())

    assert frame.shape == (0, 0)
    assert frame.columns == []


def test_conversion_uses_first_row_key_order_when_metadata_is_absent() -> None:
    result = SqlScriptResult(rows=[{"z": 3, "a": 1}, {"z": 4, "a": 2}])

    frame = sql_script_result_to_dataframe(result)

    assert frame.columns == ["z", "a"]
    assert frame.rows() == [(3, 1), (4, 2)]


@pytest.mark.parametrize(
    "rows",
    [
        [{"id": 1, "label": "safe"}, {"id": 2}],
        [{"id": 1}, {"id": 2, "extra": "secret-value"}],
    ],
)
def test_conversion_rejects_inconsistent_row_keys(
    rows: list[dict[str, object]],
) -> None:
    with pytest.raises(DataFrameDatabaseError) as captured:
        sql_script_result_to_dataframe(
            SqlScriptResult(rows=rows, columns=["id", "label"])
        )

    assert captured.value.operation == "convert"


def test_conversion_rejects_duplicate_metadata_columns() -> None:
    with pytest.raises(DataFrameDatabaseError, match="Unable to convert") as captured:
        sql_script_result_to_dataframe(
            SqlScriptResult(rows=[{"id": 1}], columns=["id", "id"])
        )

    assert captured.value.operation == "convert"


def test_conversion_preserves_representative_sql_scalar_values() -> None:
    values: list[object] = [
        None,
        True,
        42,
        1.25,
        float("nan"),
        "text",
        Decimal("12.30"),
        date(2024, 2, 29),
        datetime(2024, 2, 29, 12, 30, 45, 123456),
        time(12, 30, 45, 123456),
        timedelta(hours=-27, minutes=3, microseconds=120),
        b"bytes",
    ]
    names = [f"c{index}" for index in range(len(values))]

    frame = sql_script_result_to_dataframe(
        SqlScriptResult(rows=[dict(zip(names, values, strict=True))], columns=names)
    )

    actual = frame.row(0)
    for source, converted in zip(values, actual, strict=True):
        if isinstance(source, float) and isnan(source):
            assert isinstance(converted, float) and isnan(converted)
        elif isinstance(source, (bytes, bytearray, memoryview)):
            assert bytes(source) == bytes(converted)
        else:
            assert type(converted) is type(source)
            assert converted == source


@pytest.mark.parametrize("value", [object(), datetime(2024, 1, 1, tzinfo=UTC)])
def test_conversion_rejects_unsupported_values(value: object) -> None:
    with pytest.raises(DataFrameDatabaseError) as captured:
        sql_script_result_to_dataframe(SqlScriptResult(rows=[{"value": value}]))

    assert captured.value.operation == "convert"


def test_conversion_rejects_polars_coercion_of_heterogeneous_values() -> None:
    with pytest.raises(DataFrameDatabaseError) as captured:
        sql_script_result_to_dataframe(
            SqlScriptResult(rows=[{"value": 7}, {"value": "private"}])
        )

    assert captured.value.operation == "convert"


def test_conversion_failure_does_not_log_or_expose_row_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    secret = "sensitive-row-content"

    with pytest.raises(DataFrameDatabaseError) as captured:
        sql_script_result_to_dataframe(
            SqlScriptResult(rows=[{"value": secret}], columns=["other"])
        )

    assert secret not in str(captured.value)
    assert secret not in caplog.text
    assert "Unable to convert SQL script result to a DataFrame" in str(captured.value)
