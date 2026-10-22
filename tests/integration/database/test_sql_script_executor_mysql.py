"""Opt-in integration tests for a disposable MySQL instance."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest

from pintos_utils.database import SqlScriptError, SqlScriptExecutor

_ENV_PREFIX = "PINTOS_UTILS_MYSQL_TEST_"


def _mysql_config() -> dict[str, Any]:
    """Return explicit disposable-database configuration or skip safely."""
    values = {
        name: os.getenv(f"{_ENV_PREFIX}{name}")
        for name in ("HOST", "PORT", "USER", "PASSWORD", "DATABASE")
    }
    if os.getenv(f"{_ENV_PREFIX}DISPOSABLE") != "1" or any(
        value is None for value in values.values()
    ):
        pytest.skip("explicit disposable MySQL test configuration is not enabled")

    database = values["DATABASE"]
    if database is None or not (
        database.startswith("test_") or database.endswith("_test")
    ):
        pytest.skip("integration database name must start with test_ or end with _test")

    try:
        port = int(values["PORT"] or "")
    except ValueError:
        pytest.skip("integration MySQL port must be an integer")

    return {
        "host": values["HOST"],
        "port": port,
        "user": values["USER"],
        "password": values["PASSWORD"],
        "database": database,
        "autocommit": False,
    }


@contextmanager
def _connection_pair(config: dict[str, Any]) -> Iterator[tuple[Any, Any]]:
    """Open two driver connections and close them even if an assertion fails."""
    connector = pytest.importorskip("mysql.connector")
    first = connector.connect(**config)
    second = connector.connect(**config)
    try:
        yield first, second
    finally:
        try:
            first.rollback()
        finally:
            first.close()
            second.close()


@contextmanager
def _persistent_table(connection: Any, table: str) -> Iterator[None]:
    """Create a uniquely named integration table and always remove it."""
    setup = connection.cursor()
    try:
        setup.execute(
            f"CREATE TABLE `{table}` (id INT PRIMARY KEY, label VARCHAR(100))"
        )
        connection.commit()
    finally:
        setup.close()
    try:
        yield
    finally:
        cleanup = connection.cursor()
        try:
            cleanup.execute(f"DROP TABLE IF EXISTS `{table}`")
            connection.commit()
        finally:
            cleanup.close()


def test_temporary_table_is_visible_across_script_statements() -> None:
    config = _mysql_config()
    with _connection_pair(config) as (connection, _):
        table = f"pintos_utils_it_{uuid4().hex}"
        result = SqlScriptExecutor(connection).execute(
            f"CREATE TEMPORARY TABLE `{table}` (id INT PRIMARY KEY, label TEXT);"
            f"INSERT INTO `{table}` (id, label) VALUES (1, :label);"
            f"SELECT id, label FROM `{table}`;",
            params={"label": "same MySQL session"},
        )

        assert result.statements_executed == 3
        assert result.rows == [{"id": 1, "label": "same MySQL session"}]


def test_real_driver_transaction_boundaries_with_two_connections() -> None:
    config = _mysql_config()
    with _connection_pair(config) as (connection, observer):
        table = f"pintos_utils_it_{uuid4().hex}"
        with _persistent_table(observer, table):
            executor = SqlScriptExecutor(connection)
            connection.start_transaction()
            with pytest.raises(SqlScriptError):
                executor.execute(
                    f"INSERT INTO `{table}` (id, label) VALUES (1, :label)",
                    params={"label": "pre-existing transaction"},
                    commit=True,
                )
            assert connection.in_transaction is True
            connection.rollback()

            executor.execute(
                f"INSERT INTO `{table}` (id, label) VALUES (2, :label)",
                params={"label": "committed"},
                commit=True,
            )
            observer_cursor = observer.cursor(dictionary=True)
            try:
                observer_cursor.execute(f"SELECT label FROM `{table}` WHERE id = 2")
                assert observer_cursor.fetchall() == [{"label": "committed"}]
            finally:
                observer_cursor.close()

            executor.execute(
                f"INSERT INTO `{table}` (id, label) VALUES (3, :label)",
                params={"label": "uncommitted"},
                commit=False,
            )
            observer_cursor = observer.cursor(dictionary=True)
            try:
                observer_cursor.execute(
                    f"SELECT COUNT(*) AS total FROM `{table}` WHERE id = 3"
                )
                assert observer_cursor.fetchall() == [{"total": 0}]
            finally:
                observer_cursor.close()
            assert connection.in_transaction is True
            connection.rollback()
