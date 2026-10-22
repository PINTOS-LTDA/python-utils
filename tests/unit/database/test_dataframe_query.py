"""Offline acceptance tests for SQL-to-Polars query operations."""

from __future__ import annotations

import logging

import polars as pl
import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import DataFrameDatabaseError, query_dataframe


def test_query_returns_polars_frame_and_commits_after_materialization() -> None:
    connection = FakeConnection(
        results=[
            FakeStatementResult(rows=[(1, "one"), (2, "two")], columns=["id", "label"])
        ]
    )

    result = query_dataframe(
        connection, "SELECT id, label FROM items WHERE id = :item_id", {"item_id": 2}
    )

    assert isinstance(result, pl.DataFrame)
    assert result.to_dicts() == [{"id": 1, "label": "one"}, {"id": 2, "label": "two"}]
    cursor = connection.created_cursors[0]
    assert cursor.calls == [
        ("SELECT id, label FROM items WHERE id = %(item_id)s", {"item_id": 2})
    ]
    assert connection.events == [
        "start_transaction",
        "cursor.create",
        "execute:SELECT id, label FROM items WHERE id = %(item_id)s",
        "cursor.close",
        "commit",
    ]
    assert connection.closes == 0


def test_query_empty_result_preserves_column_names_and_order() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[], columns=["second", "first"])]
    )

    result = query_dataframe(connection, "SELECT second, first FROM items WHERE 0")

    assert result.shape == (0, 2)
    assert result.columns == ["second", "first"]
    assert connection.commits == 1


def test_query_rejects_polars_coercion_of_heterogeneous_result_values() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(1,), ("two",)], columns=["mixed"])]
    )

    with pytest.raises(DataFrameDatabaseError, match="Unable to execute"):
        query_dataframe(connection, "SELECT mixed FROM items")

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_query_can_materialize_a_data_changing_select_result() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(5,)], columns=["changed_rows"])]
    )

    result = query_dataframe(
        connection, "SELECT update_inventory(:sku)", {"sku": "A-1"}
    )

    assert result.to_dicts() == [{"changed_rows": 5}]
    assert connection.commits == 1


def test_query_passes_repeated_parameters_once_and_ignores_quoted_markers() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(8,)], columns=["id"])]
    )

    query_dataframe(
        connection,
        "SELECT :id, ':literal', `:identifier`, :id /* :comment */",
        {"id": 8},
    )

    sql, params = connection.created_cursors[0].calls[0]
    assert sql == "SELECT %(id)s, ':literal', `:identifier`, %(id)s /* :comment */"
    assert params == {"id": 8}


@pytest.mark.parametrize(
    "query",
    [
        "BEGIN",
        "START TRANSACTION",
        "COMMIT",
        "ROLLBACK",
        "SAVEPOINT nested",
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED",
        "SET SESSION autocommit = 1",
        "CREATE TABLE unsafe (id INT)",
        "ALTER TABLE items ADD COLUMN x INT",
        "DROP TABLE items",
        "CALL stored_proc()",
        "SELECT 1; SELECT 2",
        "SELECT 1 /*!80000 UNION SELECT 2 */",
        "SELECT 1 INTO OUTFILE '/tmp/result.txt'",
    ],
)
def test_query_rejects_unsupported_sql_before_transaction(query: str) -> None:
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError):
        query_dataframe(connection, query)

    assert connection.events == []
    assert connection.created_cursors == []


def test_query_rejects_missing_parameter_before_transaction() -> None:
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError, match="Missing"):
        query_dataframe(connection, "SELECT :required")

    assert connection.events == []


def test_query_rejects_active_caller_transaction_without_touching_it() -> None:
    connection = FakeConnection(in_transaction=True)

    with pytest.raises(DataFrameDatabaseError):
        query_dataframe(connection, "SELECT 1")

    assert connection.events == []
    assert connection.in_transaction is True


def test_query_rejects_no_result_and_rolls_back() -> None:
    connection = FakeConnection(results=[FakeStatementResult(rows=None)])

    with pytest.raises(DataFrameDatabaseError):
        query_dataframe(connection, "UPDATE items SET value = 1")

    assert connection.rollbacks == 1
    assert connection.commits == 0
    assert connection.created_cursors[0].closed


def test_query_rejects_additional_result_set_and_rolls_back() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(1,)], columns=["id"], extra_result_sets=1)]
    )

    with pytest.raises(DataFrameDatabaseError):
        query_dataframe(connection, "SELECT 1")

    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_query_rolls_back_conversion_failure_and_keeps_cause(monkeypatch) -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(object(),)], columns=["value"])]
    )
    original = ValueError("cannot convert")
    monkeypatch.setattr(
        pl, "read_database", lambda *a, **k: (_ for _ in ()).throw(original)
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        query_dataframe(connection, "SELECT value FROM items")

    assert captured.value.original_exception is original
    assert captured.value.__cause__ is original
    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_query_rolls_back_commit_failure() -> None:
    failure = RuntimeError("commit failed")
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(1,)], columns=["id"])],
        commit_error=failure,
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        query_dataframe(connection, "SELECT 1")

    assert captured.value.original_exception is failure
    assert connection.commits == 1
    assert connection.rollbacks == 1


def test_query_reports_cursor_cleanup_failure_and_rolls_back() -> None:
    failure = RuntimeError("close failed")
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[(1,)], columns=["id"])],
        cursor_close_error=failure,
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        query_dataframe(connection, "SELECT 1")

    assert captured.value.original_exception is failure
    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_query_redacts_bound_values_from_logs_and_errors(caplog) -> None:
    secret = "dataframe-secret-sentinel"
    connection = FakeConnection(
        results=[FakeStatementResult(execute_error=RuntimeError(secret))]
    )

    with caplog.at_level(logging.DEBUG, logger="pintos_utils.database.dataframe"):
        with pytest.raises(DataFrameDatabaseError) as captured:
            query_dataframe(connection, "SELECT :secret", {"secret": secret})

    assert secret not in caplog.text
    assert secret not in str(captured.value)
    assert connection.rollbacks == 1
