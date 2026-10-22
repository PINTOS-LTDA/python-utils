"""Contract tests for SQL script errors."""

from __future__ import annotations

from pintos_utils.database.exceptions import SqlScriptError


def test_sql_script_error_supports_context_when_known() -> None:
    original = RuntimeError("driver failed")
    error = SqlScriptError(
        "SQL statement failed",
        statement_index=2,
        statement="SELECT :value",
        original_exception=original,
    )

    assert str(error) == "SQL statement failed"
    assert error.statement_index == 2
    assert error.statement == "SELECT :value"
    assert error.original_exception is original


def test_sql_script_error_allows_context_to_be_unknown() -> None:
    error = SqlScriptError("A transaction is already active")

    assert error.statement_index is None
    assert error.statement is None
    assert error.original_exception is None
