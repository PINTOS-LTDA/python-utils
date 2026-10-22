"""Tests for SQL script errors, cleanup, and diagnostic logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import SqlScriptError, SqlScriptExecutor


def test_statement_failure_has_one_based_context_and_original_cause() -> None:
    driver_error = RuntimeError("driver failure")
    connection = FakeConnection(
        results=[
            FakeStatementResult(),
            FakeStatementResult(execute_error=driver_error),
            FakeStatementResult(),
        ]
    )

    with pytest.raises(SqlScriptError) as raised:
        SqlScriptExecutor(connection).execute("SELECT 1; UPDATE t SET v = 2; SELECT 3;")

    error = raised.value
    assert error.statement_index == 2
    assert error.statement == "UPDATE t SET v = 2;"
    assert error.original_exception is driver_error
    assert error.__cause__ is driver_error
    assert len(connection.created_cursors[0].calls) == 2
    assert connection.created_cursors[0].closed is True
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_cursor_creation_failure_is_chained_as_sql_script_error() -> None:
    driver_error = RuntimeError("cursor failure")
    connection = FakeConnection(cursor_error=driver_error)

    with pytest.raises(SqlScriptError) as raised:
        SqlScriptExecutor(connection).execute("SELECT 1;")

    assert raised.value.original_exception is driver_error
    assert raised.value.__cause__ is driver_error
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_result_consumption_failure_has_statement_context_and_closes_cursor() -> None:
    driver_error = RuntimeError("fetch failure")
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[], fetch_error=driver_error)]
    )

    with pytest.raises(SqlScriptError) as raised:
        SqlScriptExecutor(connection).execute("SELECT 1;")

    assert raised.value.statement_index == 1
    assert raised.value.statement == "SELECT 1;"
    assert raised.value.__cause__ is driver_error
    assert connection.created_cursors[0].closed is True
    assert connection.rollbacks == 0


def test_file_read_and_decode_failures_are_wrapped_with_the_original_cause(
    tmp_path: Path,
) -> None:
    executor = SqlScriptExecutor(FakeConnection())

    with pytest.raises(SqlScriptError) as missing_file:
        executor.execute_file(tmp_path / "missing.sql")
    assert isinstance(missing_file.value.__cause__, OSError)

    invalid_file = tmp_path / "invalid.sql"
    invalid_file.write_bytes(b"SELECT '\xff';")
    with pytest.raises(SqlScriptError) as invalid_encoding:
        executor.execute_file(invalid_file, encoding="utf-8")
    assert isinstance(invalid_encoding.value.__cause__, UnicodeDecodeError)


def test_commit_failure_is_wrapped_without_rollback() -> None:
    driver_error = RuntimeError("commit failure")
    connection = FakeConnection(commit_error=driver_error)

    with pytest.raises(SqlScriptError) as raised:
        SqlScriptExecutor(connection).execute("UPDATE t SET v = 1;", commit=True)

    assert raised.value.original_exception is driver_error
    assert raised.value.__cause__ is driver_error
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_cursor_close_failure_is_wrapped_and_connection_remains_open() -> None:
    close_error = RuntimeError("close failure")
    connection = FakeConnection(cursor_close_error=close_error)

    with pytest.raises(SqlScriptError) as raised:
        SqlScriptExecutor(connection).execute("SELECT 1;")

    assert raised.value.original_exception is close_error
    assert raised.value.__cause__ is close_error
    assert connection.created_cursors[0].closed is True
    assert connection.closes == 0


def test_debug_logs_never_include_bound_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_value = "private-customer-4821"
    connection = FakeConnection()
    caplog.set_level(logging.DEBUG, logger="pintos_utils.database.sql_script_executor")

    SqlScriptExecutor(connection).execute(
        "SELECT :customer_id;", params={"customer_id": sensitive_value}
    )

    assert sensitive_value not in caplog.text
    assert ":customer_id" not in caplog.text
    assert "SELECT" not in caplog.text
