"""Contract tests for the SQL script result model."""

from __future__ import annotations

from pintos_utils.database.models import SqlScriptResult


def test_sql_script_result_defaults_to_an_empty_execution() -> None:
    result = SqlScriptResult()

    assert result.statements_executed == 0
    assert result.rows == []
    assert result.affected_rows == 0


def test_sql_script_result_exposes_the_public_fields() -> None:
    rows = [{"sku": "A-1", "quantity": 4}]
    result = SqlScriptResult(statements_executed=2, rows=rows, affected_rows=4)

    assert result.statements_executed == 2
    assert result.rows == rows
    assert result.affected_rows == 4


def test_sql_script_result_default_rows_are_independent() -> None:
    first = SqlScriptResult()
    second = SqlScriptResult()

    first.rows.append({"value": 1})

    assert second.rows == []
