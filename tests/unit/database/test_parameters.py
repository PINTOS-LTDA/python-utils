"""Tests for named SQL value binding."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from database.fakes import FakeConnection
from pintos_utils.database import SqlScriptError, SqlScriptExecutor


def test_named_parameters_are_bound_with_connector_mapping_style() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)
    sensitive_value = "18' OR 1=1 --"

    result = executor.execute(
        "SELECT * FROM inventory WHERE store_id = :store_id;",
        params={"store_id": sensitive_value},
    )

    sql, parameters = connection.created_cursors[0].calls[0]
    assert result.statements_executed == 1
    assert "%(store_id)s" in sql
    assert sensitive_value not in sql
    assert parameters == {"store_id": sensitive_value}


def test_repeated_and_grammatical_parameter_names_are_supported() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    executor.execute(
        "SELECT :_private, :item2, :_private;",
        params={"_private": "same", "item2": 2},
    )

    sql, parameters = connection.created_cursors[0].calls[0]
    assert sql == "SELECT %(_private)s, %(item2)s, %(_private)s;"
    assert parameters == {"_private": "same", "item2": 2}


def test_missing_parameter_in_later_statement_fails_before_any_sql() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    with pytest.raises(SqlScriptError, match="missing_param"):
        executor.execute(
            "SELECT 1; SELECT :missing_param;",
            params={},
        )

    assert connection.created_cursors == []


def test_unreferenced_parameter_keys_are_ignored() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    executor.execute("SELECT :used;", params={"used": 3, "unused": "secret"})

    assert connection.created_cursors[0].calls[0][1] == {"used": 3}


def test_marker_like_text_inside_literals_comments_and_identifiers_is_unchanged() -> (
    None
):
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)
    script = (
        "SELECT ':in_string', `:in_identifier`, :bound_value "
        "/* :in_block_comment */ -- :in_line_comment\n"
    )

    executor.execute(script, params={"bound_value": 9})

    sql, parameters = connection.created_cursors[0].calls[0]
    assert "':in_string'" in sql
    assert "`:in_identifier`" in sql
    assert ":in_block_comment" in sql
    assert ":in_line_comment" in sql
    assert "%(bound_value)s" in sql
    assert parameters == {"bound_value": 9}


def test_python_value_types_are_passed_unchanged_to_the_driver() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)
    values = {
        "text": "á",
        "number": 17,
        "ratio": 2.5,
        "price": Decimal("12.30"),
        "day": date(2026, 10, 1),
        "timestamp": datetime(2026, 10, 1, 12, 30),
        "missing": None,
    }
    markers = ", ".join(f":{name}" for name in values)

    executor.execute(f"SELECT {markers};", params=values)

    sql, parameters = connection.created_cursors[0].calls[0]
    assert all(f"%({name})s" in sql for name in values)
    assert parameters == values
    assert all(type(parameters[name]) is type(value) for name, value in values.items())
