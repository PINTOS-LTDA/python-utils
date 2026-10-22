"""Opt-in query acceptance tests for a disposable MySQL database."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest

from pintos_utils.database import DataFrameDatabaseError, query_dataframe

_ENV_PREFIX = "PINTOS_UTILS_MYSQL_TEST_"


def _mysql_config() -> dict[str, Any]:
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


def test_real_mysql_query_and_empty_result() -> None:
    connector = pytest.importorskip("mysql.connector")
    config = _mysql_config()
    connection = connector.connect(**config)
    table = f"pintos_utils_df_{uuid4().hex}"
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"CREATE TEMPORARY TABLE `{table}` (id INT PRIMARY KEY, label VARCHAR(80))"
        )
        cursor.executemany(
            f"INSERT INTO `{table}` (id, label) VALUES (%s, %s)",
            [(1, "one"), (2, "two")],
        )
        connection.commit()

        result = query_dataframe(
            connection,
            f"SELECT id, label FROM `{table}` WHERE id >= :minimum",
            {"minimum": 1},
        )
        assert result.to_dicts() == [
            {"id": 1, "label": "one"},
            {"id": 2, "label": "two"},
        ]

        empty = query_dataframe(
            connection,
            f"SELECT id, label FROM `{table}` WHERE id < :minimum",
            {"minimum": 0},
        )
        assert empty.shape == (0, 2)
        assert empty.columns == ["id", "label"]
    finally:
        connection.rollback()
        cursor.close()
        connection.close()


def test_real_mysql_query_rolls_back_reader_conversion_failure(monkeypatch) -> None:
    polars = pytest.importorskip("polars")
    connector = pytest.importorskip("mysql.connector")
    connection = connector.connect(**_mysql_config())
    failure = ValueError("synthetic reader conversion failure")
    monkeypatch.setattr(
        polars, "read_database", lambda *args, **kwargs: (_ for _ in ()).throw(failure)
    )
    try:
        with pytest.raises(DataFrameDatabaseError) as captured:
            query_dataframe(connection, "SELECT 1 AS id")
        assert captured.value.original_exception is failure
        assert connection.in_transaction is False
    finally:
        connection.rollback()
        connection.close()


def test_real_mysql_append_batches_validate_schema_and_roll_back_failure() -> None:
    polars = pytest.importorskip("polars")
    connector = pytest.importorskip("mysql.connector")
    from pintos_utils.database import ImportMode, import_dataframe

    connection = connector.connect(**_mysql_config())
    table = f"pintos_utils_append_{uuid4().hex}"
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"CREATE TABLE `{table}` (id INT PRIMARY KEY, "
            "label VARCHAR(80) NOT NULL) ENGINE=InnoDB"
        )
        connection.commit()

        imported = import_dataframe(
            connection,
            polars.DataFrame({"id": [1, 2, 3], "label": ["one", "two", "three"]}),
            table,
            mode=ImportMode.APPEND,
            batch_size=1,
        )
        assert (imported.rows_processed, imported.batches_processed) == (3, 3)

        with pytest.raises(DataFrameDatabaseError):
            import_dataframe(
                connection,
                polars.DataFrame({"id": [9], "unknown": ["x"]}),
                table,
                mode=ImportMode.APPEND,
            )

        with pytest.raises(DataFrameDatabaseError):
            import_dataframe(
                connection,
                polars.DataFrame({"id": [4, 1], "label": ["rolled back", "duplicate"]}),
                table,
                mode=ImportMode.APPEND,
                batch_size=1,
            )

        cursor.execute(f"SELECT id, label FROM `{table}` ORDER BY id")
        assert cursor.fetchall() == [(1, "one"), (2, "two"), (3, "three")]
    finally:
        connection.rollback()
        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        connection.commit()
        cursor.close()
        connection.close()


def test_real_mysql_upsert_composite_key_and_other_unique_conflict() -> None:
    polars = pytest.importorskip("polars")
    connector = pytest.importorskip("mysql.connector")
    from pintos_utils.database import ImportMode, import_dataframe

    connection = connector.connect(**_mysql_config())
    table = f"pintos_utils_upsert_{uuid4().hex}"
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TABLE `{table}` (
                tenant_id INT NOT NULL,
                sku VARCHAR(40) CHARACTER SET utf8mb4
                    COLLATE utf8mb4_general_ci NOT NULL,
                label VARCHAR(80) NOT NULL,
                email VARCHAR(120) NOT NULL,
                PRIMARY KEY (tenant_id, sku),
                UNIQUE KEY uq_email (email)
            ) ENGINE=InnoDB"""
        )
        cursor.execute(
            f"INSERT INTO `{table}` VALUES (1, 'A', 'old', 'a@example.test'), "
            "(2, 'Z', 'other', 'z@example.test')"
        )
        connection.commit()

        imported = import_dataframe(
            connection,
            polars.DataFrame(
                {
                    "tenant_id": [1, 3],
                    "sku": ["A", "B"],
                    "label": ["updated", "new"],
                    "email": ["updated@example.test", "b@example.test"],
                }
            ),
            table,
            mode=ImportMode.UPSERT,
            key_columns=["tenant_id", "sku"],
            batch_size=1,
        )
        assert (imported.rows_processed, imported.batches_processed) == (2, 2)

        cursor.execute(
            f"SELECT tenant_id, sku, label FROM `{table}` ORDER BY tenant_id, sku"
        )
        assert cursor.fetchall() == [
            (1, "A", "updated"),
            (2, "Z", "other"),
            (3, "B", "new"),
        ]
        connection.commit()
        cursor.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME LIKE 'pintos_utils_stage_%'"
        )
        assert cursor.fetchone()[0] == 0

        with pytest.raises(DataFrameDatabaseError):
            import_dataframe(
                connection,
                polars.DataFrame(
                    {
                        "tenant_id": [4],
                        "sku": ["C"],
                        "label": ["conflict"],
                        "email": ["updated@example.test"],
                    }
                ),
                table,
                mode=ImportMode.UPSERT,
                key_columns=["tenant_id", "sku"],
            )
        cursor.execute(f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id = 4")
        assert cursor.fetchone()[0] == 0
        connection.commit()

        with pytest.raises(DataFrameDatabaseError):
            import_dataframe(
                connection,
                polars.DataFrame(
                    {
                        "tenant_id": [5, 5],
                        "sku": ["Q", "q"],
                        "label": ["first", "second"],
                        "email": ["q1@example.test", "q2@example.test"],
                    }
                ),
                table,
                mode=ImportMode.UPSERT,
                key_columns=["tenant_id", "sku"],
            )
        cursor.execute(f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id = 5")
        assert cursor.fetchone()[0] == 0
    finally:
        connection.rollback()
        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        connection.commit()
        cursor.close()
        connection.close()
