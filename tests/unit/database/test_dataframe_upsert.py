"""Offline acceptance tests for staged key-based UPSERT imports."""

from __future__ import annotations

import logging

import polars as pl
import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import DataFrameDatabaseError, ImportMode
from pintos_utils.database.dataframe import import_dataframe


def _column(
    name: str, data_type: str = "int", **overrides: object
) -> dict[str, object]:
    values: dict[str, object] = {
        "column_name": name,
        "data_type": data_type,
        "column_type": data_type,
        "is_nullable": "YES",
        "character_maximum_length": None,
        "numeric_precision": None,
        "numeric_scale": None,
        "datetime_precision": 6,
        "character_set": None,
        "collation": None,
        "extra": "",
    }
    values.update(overrides)
    return values


def _index(
    name: str,
    column: str | None,
    position: int,
    *,
    non_unique: int = 0,
    prefix_length: int | None = None,
) -> dict[str, object]:
    return {
        "index_name": name,
        "non_unique": non_unique,
        "seq_in_index": position,
        "column_name": column,
        "sub_part": prefix_length,
    }


def _connection(
    columns: list[dict[str, object]],
    indexes: list[dict[str, object]],
    *,
    outcomes: list[FakeStatementResult] | None = None,
) -> FakeConnection:
    return FakeConnection(
        results=[
            FakeStatementResult(
                rows=[
                    {
                        "engine": "InnoDB",
                        "table_type": "BASE TABLE",
                        "transactions": "YES",
                    }
                ]
            ),
            FakeStatementResult(rows=columns),
            FakeStatementResult(rows=indexes),
            *(outcomes or []),
        ]
    )


def _composite_target() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    columns = [
        _column("account_id", "int"),
        _column(
            "sku",
            "varchar",
            column_type="varchar(20)",
            character_maximum_length=20,
            character_set="utf8mb4",
            collation="utf8mb4_0900_ai_ci",
        ),
        _column(
            "label",
            "varchar",
            column_type="varchar(80)",
            character_maximum_length=80,
            character_set="utf8mb4",
            collation="utf8mb4_0900_ai_ci",
        ),
    ]
    indexes = [
        _index("PRIMARY", "account_id", 1),
        _index("PRIMARY", "sku", 2),
    ]
    return columns, indexes


def test_upsert_stages_batches_updates_matches_inserts_unmatched_and_cleans_up() -> (
    None
):
    columns, indexes = _composite_target()
    connection = _connection(columns, indexes)
    frame = pl.DataFrame(
        {
            "account_id": [1, 1, 2],
            "sku": ["A", "B", "C"],
            "label": ["updated", "inserted", "inserted too"],
        }
    )

    result = import_dataframe(
        connection,
        frame,
        "inventory",
        mode=ImportMode.UPSERT,
        key_columns=["account_id", "sku"],
        batch_size=2,
    )

    assert (result.rows_processed, result.batches_processed) == (3, 2)
    cursor = connection.created_cursors[0]
    statements = [statement for statement, _ in cursor.calls]
    assert any(
        statement.startswith("CREATE TEMPORARY TABLE `pintos_utils_stage_")
        for statement in statements
    )
    create_statement = next(
        statement
        for statement in statements
        if statement.startswith("CREATE TEMPORARY TABLE `pintos_utils_stage_")
    )
    assert (
        "`sku` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        in create_statement
    )
    assert (
        "UNIQUE KEY `pintos_utils_source_key` (`account_id`, `sku`)" in create_statement
    )
    assert "AS SELECT" not in create_statement
    assert (
        sum(statement.startswith("UPDATE `inventory`") for statement in statements) == 1
    )
    assert (
        sum(statement.startswith("INSERT INTO `inventory`") for statement in statements)
        == 1
    )
    assert statements[-1].startswith("DROP TEMPORARY TABLE")
    assert [len(rows) for _, rows in cursor.many_calls] == [2, 1]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_upsert_key_only_frame_does_not_update_existing_rows() -> None:
    columns, indexes = _composite_target()
    connection = _connection(columns, indexes)

    result = import_dataframe(
        connection,
        pl.DataFrame({"account_id": [1], "sku": ["A"]}),
        "inventory",
        mode=ImportMode.UPSERT,
        key_columns=["account_id", "sku"],
    )

    statements = [statement for statement, _ in connection.created_cursors[0].calls]
    assert not any(
        statement.startswith("UPDATE `inventory`") for statement in statements
    )
    assert any(
        statement.startswith("INSERT INTO `inventory`") for statement in statements
    )
    assert result.rows_processed == 1


def test_upsert_accepts_a_single_secondary_unique_key() -> None:
    columns = [
        _column(
            "email",
            "varchar",
            column_type="varchar(80)",
            character_maximum_length=80,
            character_set="utf8mb4",
            collation="utf8mb4_0900_ai_ci",
        ),
        _column(
            "label", "varchar", column_type="varchar(80)", character_maximum_length=80
        ),
    ]
    connection = _connection(columns, [_index("uq_email", "email", 1)])

    result = import_dataframe(
        connection,
        pl.DataFrame({"email": ["person@example.test"], "label": ["updated"]}),
        "contacts",
        mode=ImportMode.UPSERT,
        key_columns=("email",),
    )

    statements = [statement for statement, _ in connection.created_cursors[0].calls]
    assert any(
        "UNIQUE KEY `pintos_utils_source_key` (`email`)" in value
        for value in statements
    )
    assert any(statement.startswith("UPDATE `contacts`") for statement in statements)
    assert result.rows_processed == 1


@pytest.mark.parametrize(
    "frame",
    [
        pl.DataFrame({"key": [1, None]}, schema={"key": pl.Int64}),
        pl.DataFrame({"key": [1, 1]}),
    ],
)
def test_upsert_rejects_null_or_duplicate_source_keys_before_database_work(
    frame: pl.DataFrame,
) -> None:
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection,
            frame,
            "items",
            mode=ImportMode.UPSERT,
            key_columns=["key"],
        )

    assert connection.events == []


def test_upsert_requires_present_complete_primary_or_unique_index() -> None:
    columns, indexes = _composite_target()
    frame = pl.DataFrame({"account_id": [1], "sku": ["A"], "label": ["x"]})
    invalid_indexes = [
        [_index("uq", "account_id", 1, non_unique=1)],
        [_index("uq_prefix", "sku", 1, prefix_length=4)],
        [_index("uq_functional", None, 1)],
        [_index("uq_account", "account_id", 1)],
    ]

    for candidate in invalid_indexes:
        connection = _connection(columns, candidate)
        with pytest.raises(DataFrameDatabaseError):
            import_dataframe(
                connection,
                frame,
                "inventory",
                mode=ImportMode.UPSERT,
                key_columns=["account_id", "sku"],
            )
        assert not any(
            statement.startswith("CREATE TEMPORARY TABLE")
            for statement, _ in connection.created_cursors[0].calls
        )
        assert connection.rollbacks == 1


def test_upsert_rejects_missing_key_column_before_transaction() -> None:
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection,
            pl.DataFrame({"value": [1]}),
            "items",
            mode=ImportMode.UPSERT,
            key_columns=["id"],
        )

    assert connection.events == []


def test_upsert_rolls_back_other_unique_key_conflict_and_drops_staging() -> None:
    columns, indexes = _composite_target()
    conflict = RuntimeError("other unique index conflict")
    connection = _connection(
        columns,
        indexes,
        outcomes=[
            FakeStatementResult(),  # create temporary table
            FakeStatementResult(),  # staging batch
            FakeStatementResult(),  # matched update
            FakeStatementResult(execute_error=conflict),  # unmatched target insert
            FakeStatementResult(),  # cleanup drop
        ],
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        import_dataframe(
            connection,
            pl.DataFrame({"account_id": [2], "sku": ["B"], "label": ["duplicate"]}),
            "inventory",
            mode=ImportMode.UPSERT,
            key_columns=["account_id", "sku"],
        )

    assert captured.value.original_exception is conflict
    statements = [statement for statement, _ in connection.created_cursors[0].calls]
    assert statements[-1].startswith("DROP TEMPORARY TABLE")
    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_upsert_reports_staging_cleanup_failure_without_hiding_primary_error() -> None:
    columns, indexes = _composite_target()
    primary = RuntimeError("update failed")
    cleanup = RuntimeError("drop failed")
    connection = _connection(
        columns,
        indexes,
        outcomes=[
            FakeStatementResult(),
            FakeStatementResult(),
            FakeStatementResult(execute_error=primary),
            FakeStatementResult(execute_error=cleanup),
        ],
    )

    with pytest.raises(DataFrameDatabaseError) as captured:
        import_dataframe(
            connection,
            pl.DataFrame({"account_id": [1], "sku": ["A"], "label": ["x"]}),
            "inventory",
            mode=ImportMode.UPSERT,
            key_columns=["account_id", "sku"],
        )

    assert captured.value.original_exception is primary
    assert captured.value.cleanup_exception is cleanup
    assert connection.rollbacks == 1


def test_upsert_redacts_source_rows_from_logs_and_errors(caplog) -> None:
    columns, indexes = _composite_target()
    secret = "upsert-secret-sentinel"
    failure = RuntimeError(secret)
    connection = _connection(
        columns,
        indexes,
        outcomes=[
            FakeStatementResult(),
            FakeStatementResult(executemany_error=failure),
        ],
    )
    frame = pl.DataFrame({"account_id": [1], "sku": ["A"], "label": [secret]})

    with caplog.at_level(logging.DEBUG, logger="pintos_utils.database.dataframe"):
        with pytest.raises(DataFrameDatabaseError) as captured:
            import_dataframe(
                connection,
                frame,
                "inventory",
                mode=ImportMode.UPSERT,
                key_columns=["account_id", "sku"],
            )

    assert secret not in caplog.text
    assert secret not in str(captured.value)
