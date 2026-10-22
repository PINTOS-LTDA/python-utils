"""Tests for SQL script splitting and same-session execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import SqlScriptError, SqlScriptExecutor


def test_execute_runs_one_statement_on_a_dictionary_cursor() -> None:
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"value": 7}], rowcount=1)]
    )
    executor = SqlScriptExecutor(connection)

    result = executor.execute("SELECT 7 AS value;")

    assert result.statements_executed == 1
    assert result.rows == [{"value": 7}]
    assert connection.cursor_options == [True]
    assert [call[0] for call in connection.created_cursors[0].calls] == [
        "SELECT 7 AS value;"
    ]


def test_execute_runs_multiple_statements_in_order_on_one_connection() -> None:
    connection = FakeConnection(
        results=[
            FakeStatementResult(rowcount=1),
            FakeStatementResult(rows=[{"value": "final"}]),
        ]
    )
    executor = SqlScriptExecutor(connection)

    result = executor.execute("USE inventory; SELECT 'final' AS value;")

    assert result.statements_executed == 2
    assert result.rows == [{"value": "final"}]
    assert len(connection.created_cursors) == 1
    assert [call[0] for call in connection.created_cursors[0].calls] == [
        "USE inventory;",
        "SELECT 'final' AS value;",
    ]
    assert connection.closes == 0


def test_execute_skips_empty_and_comment_only_fragments() -> None:
    connection = FakeConnection(results=[FakeStatementResult(rows=[{"ok": 1}])])
    executor = SqlScriptExecutor(connection)

    result = executor.execute(
        "-- leading; comment\n; /* isolated; block */ ; SELECT 1 AS ok; -- tail;\n"
    )

    assert result.statements_executed == 1
    assert result.rows == [{"ok": 1}]
    assert len(connection.created_cursors[0].calls) == 1


def test_comment_only_script_is_a_noop_even_when_commit_is_requested() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    result = executor.execute(
        " -- only comment;\n /* another; comment */ ", commit=True
    )

    assert result.statements_executed == 0
    assert result.rows == []
    assert connection.created_cursors == []
    assert connection.commits == 0


def test_semicolons_in_strings_comments_and_quoted_identifiers_do_not_split() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)
    script = (
        "SELECT 'left;right' AS value; "
        "SELECT `semi;colon` FROM records /* block; comment */ "
        "-- line; comment\nWHERE enabled = 1; "
        'SELECT "double;quoted" AS value;'
    )

    result = executor.execute(script)

    statements = [call[0] for call in connection.created_cursors[0].calls]
    assert result.statements_executed == 3
    assert len(statements) == 3
    assert "'left;right'" in statements[0]
    assert "`semi;colon`" in statements[1]
    assert '"double;quoted"' in statements[2]


def test_executable_mysql_comments_are_rejected_before_cursor_creation() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    with pytest.raises(SqlScriptError, match="executable"):
        executor.execute("SELECT 1; /*!80000 SELECT 2 */")

    assert connection.created_cursors == []
    assert connection.commits == 0


@pytest.mark.parametrize(
    "script",
    [
        "SELECT '/*!80000 SELECT 2 */' AS text;",
        "SELECT `/*!80000 SELECT 2 */` AS identifier;",
    ],
)
def test_executable_comment_marker_text_inside_quotes_is_preserved(
    script: str,
) -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    result = executor.execute(script)

    assert result.statements_executed == 1
    assert connection.created_cursors[0].calls[0][0] == script


def test_execute_file_uses_requested_encoding_and_preserves_unicode(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "reporte.sql"
    file_path.write_text("SELECT 'ação e café' AS texto;", encoding="utf-8")
    connection = FakeConnection(
        results=[FakeStatementResult(rows=[{"texto": "ação e café"}])]
    )
    executor = SqlScriptExecutor(connection)

    result = executor.execute_file(file_path, encoding="utf-8")

    assert result.rows == [{"texto": "ação e café"}]
    assert "ação e café" in connection.created_cursors[0].calls[0][0]


def test_result_rows_come_from_the_last_result_producing_statement() -> None:
    connection = FakeConnection(
        results=[
            FakeStatementResult(rows=[{"value": "first"}]),
            FakeStatementResult(rowcount=2),
            FakeStatementResult(rows=[{"value": "last"}]),
        ]
    )
    executor = SqlScriptExecutor(connection)

    result = executor.execute("SELECT 'first'; UPDATE t SET c = 1; SELECT 'last';")

    assert result.statements_executed == 3
    assert result.rows == [{"value": "last"}]


def test_cursor_is_closed_but_supplied_connection_is_not() -> None:
    connection = FakeConnection()
    executor = SqlScriptExecutor(connection)

    executor.execute("SELECT 1;")

    assert connection.created_cursors[0].closed is True
    assert connection.closes == 0
