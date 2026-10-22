"""Offline acceptance tests for transactional APPEND imports."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time
from decimal import Decimal

import polars as pl
import pytest

from database.fakes import FakeConnection, FakeStatementResult
from pintos_utils.database import (
    DataFrameDatabaseError,
    DataFrameImportResult,
    ImportMode,
)
from pintos_utils.database.dataframe import import_dataframe


def _column(
    name: str,
    data_type: str,
    *,
    column_type: str | None = None,
    nullable: str = "YES",
    length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
    extra: str = "",
) -> dict[str, object]:
    return {
        "column_name": name,
        "data_type": data_type,
        "column_type": column_type or data_type,
        "is_nullable": nullable,
        "character_maximum_length": length,
        "numeric_precision": precision,
        "numeric_scale": scale,
        "datetime_precision": 6,
        "character_set": None,
        "collation": None,
        "extra": extra,
    }


def _connection(
    columns: list[dict[str, object]],
    *,
    rows: list[FakeStatementResult] | None = None,
    engine: str = "InnoDB",
    transactions: str = "YES",
) -> FakeConnection:
    metadata = FakeStatementResult(
        rows=[
            {
                "engine": engine,
                "table_type": "BASE TABLE",
                "transactions": transactions,
            }
        ]
    )
    column_result = FakeStatementResult(rows=columns)
    return FakeConnection(results=[metadata, column_result, *(rows or [])])


def test_append_converts_and_sends_bounded_batches_then_commits_once() -> None:
    frame = pl.DataFrame({"id": [1, 2, 3, 4, 5], "label": ["a", "b", "c", "d", "e"]})
    connection = _connection(
        [
            _column("id", "int", column_type="int"),
            _column("label", "varchar", length=20),
        ]
    )

    result = import_dataframe(
        connection, frame, "items", mode=ImportMode.APPEND, batch_size=2
    )

    assert isinstance(result, DataFrameImportResult)
    assert (result.rows_processed, result.batches_processed) == (5, 3)
    cursor = connection.created_cursors[0]
    assert [len(rows) for _, rows in cursor.many_calls] == [2, 2, 1]
    assert [row for _, rows in cursor.many_calls for row in rows] == [
        (1, "a"),
        (2, "b"),
        (3, "c"),
        (4, "d"),
        (5, "e"),
    ]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closes == 0


def test_append_empty_frame_is_a_validated_no_op() -> None:
    connection = FakeConnection()

    result = import_dataframe(
        connection,
        pl.DataFrame(schema={"id": pl.Int64}),
        "items",
        mode=ImportMode.APPEND,
    )

    assert (result.rows_processed, result.batches_processed) == (0, 0)
    assert connection.events == []


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5])
def test_append_rejects_invalid_batch_size_before_database_work(
    batch_size: object,
) -> None:
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection,
            pl.DataFrame({"id": [1]}),
            "items",
            mode=ImportMode.APPEND,
            batch_size=batch_size,  # type: ignore[arg-type]
        )

    assert connection.events == []


def test_append_requires_explicit_supported_mode_and_rejects_keys() -> None:
    frame = pl.DataFrame({"id": [1]})
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(connection, frame, "items", mode=None)  # type: ignore[arg-type]
    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(connection, frame, "items", mode="APPEND")  # type: ignore[arg-type]
    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection,
            frame,
            "items",
            mode=ImportMode.APPEND,
            key_columns=["id"],
        )

    assert connection.events == []


def test_append_rejects_bad_identifiers_before_database_work() -> None:
    connection = FakeConnection()

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection,
            pl.DataFrame({"id": [1]}),
            "items; DROP TABLE items",
            mode=ImportMode.APPEND,
        )

    assert connection.events == []


def test_append_rejects_active_caller_transaction_without_querying() -> None:
    connection = FakeConnection(in_transaction=True)

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection, pl.DataFrame({"id": [1]}), "items", mode=ImportMode.APPEND
        )

    assert connection.events == []
    assert connection.in_transaction is True


def test_append_rejects_nontransactional_or_missing_target_before_writes() -> None:
    frame = pl.DataFrame({"id": [1]})
    nontransactional = _connection(
        [_column("id", "int")], engine="MyISAM", transactions="NO"
    )
    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(nontransactional, frame, "items", mode=ImportMode.APPEND)
    assert nontransactional.created_cursors[0].many_calls == []
    assert nontransactional.rollbacks == 1

    missing = FakeConnection(results=[FakeStatementResult(rows=[])])
    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(missing, frame, "missing", mode=ImportMode.APPEND)
    assert missing.rollbacks == 1


def test_append_rejects_unknown_and_generated_columns_before_row_writes() -> None:
    connection = _connection([_column("id", "int")])

    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            connection,
            pl.DataFrame({"id": [1], "unknown": ["x"]}),
            "items",
            mode=ImportMode.APPEND,
        )

    assert connection.created_cursors[0].many_calls == []
    assert connection.rollbacks == 1

    generated = _connection([_column("id", "int", extra="VIRTUAL GENERATED")])
    with pytest.raises(DataFrameDatabaseError):
        import_dataframe(
            generated,
            pl.DataFrame({"id": [1]}),
            "items",
            mode=ImportMode.APPEND,
        )
    assert generated.created_cursors[0].many_calls == []


def test_append_rolls_back_every_batch_after_later_batch_failure() -> None:
    secret = "append-secret-sentinel"
    connection = _connection(
        [_column("id", "int"), _column("label", "varchar", length=40)],
        rows=[
            FakeStatementResult(),
            FakeStatementResult(executemany_error=RuntimeError(secret)),
        ],
    )
    frame = pl.DataFrame({"id": [1, 2], "label": ["first", secret]})

    with pytest.raises(DataFrameDatabaseError) as captured:
        import_dataframe(
            connection, frame, "items", mode=ImportMode.APPEND, batch_size=1
        )

    assert captured.value.original_exception is not None
    assert connection.rollbacks == 1
    assert connection.commits == 0
    assert connection.closes == 0


@pytest.mark.parametrize(
    ("frame", "column", "message"),
    [
        (
            pl.DataFrame({"id": [128]}, schema={"id": pl.Int64}),
            _column("id", "tinyint"),
            "integer range",
        ),
        (
            pl.DataFrame({"label": ["four"]}),
            _column("label", "varchar", length=3),
            "length",
        ),
        (
            pl.DataFrame({"payload": [b"four"]}),
            _column("payload", "varbinary", length=3),
            "length",
        ),
        (
            pl.DataFrame({"amount": [Decimal("1.234")]}),
            _column(
                "amount", "decimal", column_type="decimal(4,2)", precision=4, scale=2
            ),
            "(?i)decimal",
        ),
        (
            pl.DataFrame({"when": [datetime(2026, 1, 1, tzinfo=UTC)]}),
            _column("when", "datetime"),
            "(?i)timezone",
        ),
    ],
)
def test_append_rejects_lossy_or_unsupported_values_before_row_writes(
    frame: pl.DataFrame,
    column: dict[str, object],
    message: str,
) -> None:
    connection = _connection([column])

    with pytest.raises(DataFrameDatabaseError, match=message):
        import_dataframe(connection, frame, "items", mode=ImportMode.APPEND)

    assert connection.created_cursors[0].many_calls == []
    assert connection.rollbacks == 1


def test_append_accepts_exact_decimal_date_and_datetime_values() -> None:
    frame = pl.DataFrame(
        {
            "amount": [Decimal("12.30")],
            "the_date": [date(2026, 10, 22)],
            "created_at": [datetime(2026, 10, 22, 12, 30, 45, 123456)],
        }
    )
    connection = _connection(
        [
            _column(
                "amount", "decimal", column_type="decimal(5,2)", precision=5, scale=2
            ),
            _column("the_date", "date"),
            _column("created_at", "datetime"),
        ]
    )

    result = import_dataframe(connection, frame, "items", mode=ImportMode.APPEND)

    assert result.rows_processed == 1
    assert connection.created_cursors[0].many_calls[0][1] == [
        (
            Decimal("12.30"),
            date(2026, 10, 22),
            datetime(2026, 10, 22, 12, 30, 45, 123456),
        )
    ]


def test_append_accepts_boolean_float_binary_and_time_scalars() -> None:
    frame = pl.DataFrame(
        {
            "enabled": [True],
            "ratio": pl.Series([1.5], dtype=pl.Float32),
            "score": pl.Series([1.25], dtype=pl.Float64),
            "payload": [b"\x00\x01"],
            "run_at": [time(12, 30, 45, 123456)],
        }
    )
    connection = _connection(
        [
            _column("enabled", "tinyint", column_type="tinyint(1)"),
            _column("ratio", "float"),
            _column("score", "double"),
            _column("payload", "varbinary", length=8),
            _column("run_at", "time"),
        ]
    )

    import_dataframe(connection, frame, "items", mode=ImportMode.APPEND)

    assert connection.created_cursors[0].many_calls[0][1] == [
        (True, 1.5, 1.25, b"\x00\x01", time(12, 30, 45, 123456))
    ]


def test_append_rejects_float_rounding_submicrosecond_and_nested_values() -> None:
    cases = [
        (
            pl.DataFrame({"value": pl.Series([0.1], dtype=pl.Float64)}),
            _column("value", "float"),
        ),
        (
            pl.DataFrame(
                {"when": pl.Series([1_234_567], dtype=pl.Int64).cast(pl.Datetime("ns"))}
            ),
            _column("when", "datetime"),
        ),
        (pl.DataFrame({"items": [[1, 2]]}), _column("items", "json")),
    ]

    for frame, column in cases:
        connection = _connection([column])
        with pytest.raises(DataFrameDatabaseError):
            import_dataframe(connection, frame, "items", mode=ImportMode.APPEND)
        assert connection.created_cursors[0].many_calls == []


def test_append_rejects_null_for_nonnullable_column_before_writes() -> None:
    connection = _connection([_column("id", "int", nullable="NO")])

    with pytest.raises(DataFrameDatabaseError, match="non-nullable"):
        import_dataframe(
            connection,
            pl.DataFrame({"id": [None]}, schema={"id": pl.Int64}),
            "items",
            mode=ImportMode.APPEND,
        )

    assert connection.created_cursors[0].many_calls == []


def test_append_redacts_row_values_from_logs_and_errors(caplog) -> None:
    secret = "sensitive-row-sentinel"
    connection = _connection(
        [_column("label", "varchar", length=80)],
        rows=[FakeStatementResult(executemany_error=RuntimeError(secret))],
    )

    with caplog.at_level(logging.DEBUG, logger="pintos_utils.database.dataframe"):
        with pytest.raises(DataFrameDatabaseError) as captured:
            import_dataframe(
                connection,
                pl.DataFrame({"label": [secret]}),
                "items",
                mode=ImportMode.APPEND,
            )

    assert secret not in caplog.text
    assert secret not in str(captured.value)
