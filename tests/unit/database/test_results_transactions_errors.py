"""Tests for result counts and transaction ownership rules."""

from __future__ import annotations

import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import SqlScriptError, SqlScriptExecutor


def test_affected_rows_sum_only_nonnegative_dml_counts() -> None:
    connection = FakeConnection(
        results=[
            FakeStatementResult(rowcount=99),
            FakeStatementResult(rowcount=2),
            FakeStatementResult(rowcount=-1),
            FakeStatementResult(rowcount=3),
        ]
    )

    result = SqlScriptExecutor(connection).execute(
        "SELECT 1; UPDATE t SET v = 1; INSERT INTO t VALUES (2); DELETE FROM t;"
    )

    assert result.statements_executed == 4
    assert result.affected_rows == 5


def test_affected_rows_include_cte_prefixed_update_and_delete() -> None:
    connection = FakeConnection(
        results=[
            FakeStatementResult(rowcount=99),
            FakeStatementResult(rowcount=2),
            FakeStatementResult(rowcount=3),
        ]
    )

    result = SqlScriptExecutor(connection).execute(
        "WITH target AS (SELECT 1) SELECT * FROM target;"
        "WITH target AS (SELECT 1) UPDATE t SET v = 1;"
        "WITH target AS (SELECT 1) DELETE FROM t WHERE v = 1;"
    )

    assert result.statements_executed == 3
    assert result.affected_rows == 5


def test_cte_select_for_update_is_not_counted_as_dml() -> None:
    connection = FakeConnection(results=[FakeStatementResult(rowcount=4)])

    result = SqlScriptExecutor(connection).execute(
        "WITH lock_target AS (SELECT 1) SELECT * FROM lock_target FOR UPDATE;"
    )

    assert result.statements_executed == 1
    assert result.affected_rows == 0


def test_commit_false_never_commits_or_rolls_back() -> None:
    connection = FakeConnection()

    SqlScriptExecutor(connection).execute("UPDATE t SET v = 1;", commit=False)

    assert connection.commits == 0
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_commit_true_commits_once_after_successful_statements() -> None:
    connection = FakeConnection()

    SqlScriptExecutor(connection).execute(
        "UPDATE t SET v = 1; DELETE FROM t WHERE v = 2;", commit=True
    )

    assert connection.commits == 1
    assert connection.events.index("commit") > connection.events.index(
        "execute:DELETE FROM t WHERE v = 2;"
    )


def test_active_transaction_rejects_commit_before_cursor_creation() -> None:
    connection = FakeConnection(in_transaction=True)

    with pytest.raises(SqlScriptError, match="transaction is active"):
        SqlScriptExecutor(connection).execute("SELECT 1;", commit=True)

    assert connection.created_cursors == []
    assert connection.in_transaction is True
    assert connection.commits == 0
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    "statement",
    [
        "START TRANSACTION",
        "BEGIN",
        "BEGIN WORK",
        "COMMIT",
        "COMMIT WORK",
        "ROLLBACK",
        "ROLLBACK WORK",
        "SAVEPOINT checkpoint",
        "RELEASE SAVEPOINT checkpoint",
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED",
        "SET SESSION TRANSACTION READ ONLY",
        "SET GLOBAL TRANSACTION ISOLATION LEVEL SERIALIZABLE",
    ],
)
def test_explicit_transaction_control_is_rejected_for_the_whole_script(
    statement: str,
) -> None:
    connection = FakeConnection()

    with pytest.raises(SqlScriptError, match="transaction-control"):
        SqlScriptExecutor(connection).execute(f"SELECT 1; {statement};")

    assert connection.created_cursors == []
    assert connection.commits == 0
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    "statement",
    [
        "SET autocommit = 0",
        "SET autocommit := 1",
        "SET @@autocommit = 0",
        "SET @@GLOBAL.autocommit = 0",
        "SET @@SESSION.autocommit := 1",
        "SET GLOBAL autocommit = 0",
        "SET SESSION autocommit := 1",
        "SET LOCAL autocommit = 0",
        "SET PERSIST autocommit = 0",
        "SET PERSIST_ONLY autocommit := 0",
        "SET @other = 1, SESSION autocommit = 0",
        "SET @other = 1, @@autocommit := 0",
    ],
)
def test_autocommit_system_variable_assignments_are_rejected(
    statement: str,
) -> None:
    connection = FakeConnection()

    with pytest.raises(SqlScriptError, match="transaction-control"):
        SqlScriptExecutor(connection).execute(f"SELECT 1; {statement};")

    assert connection.created_cursors == []


@pytest.mark.parametrize(
    "script",
    [
        "SELECT 'COMMIT; SET autocommit=0';",
        "SELECT `ROLLBACK`;",
        "-- COMMIT; SET autocommit=0\nSELECT 1;",
        "SELECT 1 /* ROLLBACK; SET autocommit=0 */;",
        "SET @autocommit = 0;",
        "SET @transaction = 1;",
    ],
)
def test_transaction_keywords_in_opaque_contexts_are_not_rejected(
    script: str,
) -> None:
    connection = FakeConnection()

    result = SqlScriptExecutor(connection).execute(script)

    assert result.statements_executed >= 1
    assert len(connection.created_cursors) == 1


def test_transaction_control_is_rejected_without_commit_or_rollback() -> None:
    connection = FakeConnection(in_transaction=True)

    with pytest.raises(SqlScriptError):
        SqlScriptExecutor(connection).execute("ROLLBACK;", commit=True)

    assert connection.in_transaction is True
    assert connection.commits == 0
    assert connection.rollbacks == 0
    assert connection.closes == 0
