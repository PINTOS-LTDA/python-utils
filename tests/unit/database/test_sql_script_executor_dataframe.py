"""Offline acceptance tests for DataFrame-returning script execution."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import (
    DataFrameDatabaseError,
    SqlScriptError,
    SqlScriptExecutor,
    SqlScriptResult,
)


def test_execute_dataframe_returns_last_result_even_with_later_non_result_statement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(
        results=[
            FakeStatementResult(rows=[{"id": 1}], columns=["id"], rowcount=0),
            FakeStatementResult(
                rows=[{"id": 2, "label": "two"}], columns=["label", "id"]
            ),
            FakeStatementResult(rows=None, rowcount=1),
        ]
    )
    from pintos_utils.database import sql_script_executor as executor_module

    convert = executor_module.sql_script_result_to_dataframe

    def record_conversion(result: SqlScriptResult) -> pl.DataFrame:
        connection.events.append("convert")
        return convert(result)

    monkeypatch.setattr(
        executor_module, "sql_script_result_to_dataframe", record_conversion
    )

    frame = SqlScriptExecutor(connection).execute_dataframe(
        "SELECT id FROM items WHERE id = :first_id; "
        "SELECT label, id FROM items WHERE id = :last_id; "
        "UPDATE items SET viewed = 1",
        {"first_id": 1, "last_id": 2},
        commit=True,
    )

    assert frame.columns == ["label", "id"]
    assert frame.to_dicts() == [{"label": "two", "id": 2}]
    assert connection.created_cursors[0].calls[:2] == [
        ("SELECT id FROM items WHERE id = %(first_id)s;", {"first_id": 1}),
        ("SELECT label, id FROM items WHERE id = %(last_id)s;", {"last_id": 2}),
    ]
    assert connection.events.index("cursor.close") < connection.events.index("convert")
    assert connection.events.index("convert") < connection.events.index("commit")
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_execute_dataframe_preserves_empty_final_result_columns() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[], columns=["second", "first"])]
    )

    frame = SqlScriptExecutor(connection).execute_dataframe(
        "SELECT second, first FROM t WHERE 0"
    )

    assert frame.shape == (0, 2)
    assert frame.columns == ["second", "first"]


def test_execute_dataframe_without_result_returns_zero_by_zero_frame() -> None:
    connection = FakeConnection(results=[FakeStatementResult(rows=None, rowcount=1)])

    frame = SqlScriptExecutor(connection).execute_dataframe(
        "UPDATE items SET active = 1"
    )

    assert frame.shape == (0, 0)


def test_execute_dataframe_empty_script_is_a_transaction_no_op() -> None:
    connection = FakeConnection(in_transaction=True)

    frame = SqlScriptExecutor(connection).execute_dataframe(
        "-- only a comment", commit=True
    )

    assert frame.shape == (0, 0)
    assert connection.created_cursors == []
    assert connection.commits == 0
    assert connection.rollbacks == 0


def test_execute_file_dataframe_uses_encoding_and_bound_parameters(
    tmp_path: Path,
) -> None:
    sql_file = tmp_path / "select.sql"
    sql_file.write_bytes("SELECT :label AS label /* café */".encode("latin-1"))
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"label": "café"}], columns=["label"])]
    )

    frame = SqlScriptExecutor(connection).execute_file_dataframe(
        sql_file,
        params={"label": "café"},
        encoding="latin-1",
    )

    assert frame.to_dicts() == [{"label": "café"}]
    assert connection.created_cursors[0].calls == [
        ("SELECT %(label)s AS label /* café */", {"label": "café"})
    ]


def test_conversion_failure_rolls_back_only_when_commit_was_requested() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"value": object()}])]
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        SqlScriptExecutor(connection).execute_dataframe(
            "SELECT unsupported_value", commit=True
        )

    assert captured.value.operation == "convert"
    assert connection.rollbacks == 1
    assert connection.commits == 0
    assert connection.events[-1] == "rollback"


def test_conversion_failure_without_commit_does_not_change_transaction() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"value": object()}])]
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        SqlScriptExecutor(connection).execute_dataframe("SELECT unsupported_value")

    assert captured.value.operation == "convert"
    assert connection.rollbacks == 0
    assert connection.commits == 0


def test_rollback_failure_is_retained_as_conversion_cleanup_context() -> None:
    rollback_error = RuntimeError("rollback failed")
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"value": object()}])],
        rollback_error=rollback_error,
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        SqlScriptExecutor(connection).execute_dataframe(
            "SELECT unsupported_value", commit=True
        )

    assert captured.value.operation == "convert"
    assert captured.value.cleanup_exception is rollback_error
    assert captured.value.original_exception is not rollback_error


@pytest.mark.parametrize(
    "result,close_error",
    [
        (FakeStatementResult(execute_error=RuntimeError("SQL failed")), None),
        (
            FakeStatementResult(
                rows=[{"id": 1}],
                columns=["id"],
                fetch_error=RuntimeError("fetch failed"),
            ),
            None,
        ),
        (
            FakeStatementResult(rows=[{"id": 1}], columns=["id"]),
            RuntimeError("close failed"),
        ),
    ],
)
def test_sql_fetch_and_cursor_close_failures_do_not_add_rollback(
    result: FakeStatementResult,
    close_error: BaseException | None,
) -> None:
    connection = FakeConnection(results=[result], cursor_close_error=close_error)

    with pytest.raises(SqlScriptError):
        SqlScriptExecutor(connection).execute_dataframe(
            "SELECT id FROM items", commit=True
        )

    assert connection.rollbacks == 0
    assert connection.commits == 0


def test_execute_dataframe_rejects_an_existing_transaction_before_cursor_creation() -> (
    None
):
    connection = FakeConnection(in_transaction=True)

    with pytest.raises(SqlScriptError, match="transaction is active"):
        SqlScriptExecutor(connection).execute_dataframe("SELECT 1", commit=True)

    assert connection.created_cursors == []


def test_existing_execute_still_returns_sql_script_result_with_columns() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"id": 3}], columns=["id"])]
    )

    result = SqlScriptExecutor(connection).execute("SELECT id FROM items")

    assert isinstance(result, SqlScriptResult)
    assert result.rows == [{"id": 3}]
    assert result.columns == ["id"]
