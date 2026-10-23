"""Optional Polars operations over a consumer-owned MySQL connection."""

from __future__ import annotations

import importlib
import logging
import math
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import uuid4

from pintos_utils.database._sql import prepare_query
from pintos_utils.database.exceptions import DataFrameDatabaseError
from pintos_utils.database.models import (
    DataFrameImportResult,
    ImportMode,
    SqlScriptResult,
)

if TYPE_CHECKING:
    import polars as pl

_LOGGER = logging.getLogger(__name__)
_TABLE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_STAGING_COLUMN_TYPE = re.compile(
    r"(?:tinyint|smallint|mediumint|int|integer|bigint|float|double|real|decimal|numeric|"
    r"char|varchar|tinytext|text|mediumtext|longtext|binary|varbinary|tinyblob|blob|"
    r"mediumblob|longblob|date|datetime|time|bit)(?:\(\d+(?:,\d+)?\))?"
    r"(?: unsigned)?(?: zerofill)?\Z"
)
_CHARSET_IDENTIFIER = re.compile(r"[A-Za-z0-9_]+\Z")
_INTEGER_BITS = {
    "tinyint": 8,
    "smallint": 16,
    "mediumint": 24,
    "int": 32,
    "integer": 32,
    "bigint": 64,
}
_CHARACTER_TYPES = frozenset(
    {"char", "varchar", "tinytext", "text", "mediumtext", "longtext"}
)
_BINARY_TYPES = frozenset(
    {"binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob"}
)


def sql_script_result_to_dataframe(result: SqlScriptResult) -> pl.DataFrame:
    """Convert a materialized SQL script result into an eager Polars frame.

    Result rows and their schema are copied without adding execution metadata.
    When the result has no rows, known column names are retained and their
    Polars dtypes remain unspecified.
    """
    try:
        polars = _require_polars("convert")
        if not isinstance(result, SqlScriptResult):
            raise TypeError("result must be a SqlScriptResult")

        rows = result.rows
        if result.columns:
            columns = list(result.columns)
        elif rows:
            first_row = rows[0]
            if not isinstance(first_row, Mapping):
                raise TypeError("SQL script result rows must be mappings")
            columns = list(first_row.keys())
        else:
            columns = []

        if any(not isinstance(name, str) for name in columns):
            raise ValueError("SQL script result column names must be strings")
        if len(set(columns)) != len(columns):
            raise ValueError("SQL script result column names must be unique")

        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError("SQL script result rows must be mappings")
            if set(row) != set(columns):
                raise ValueError("SQL script result rows have inconsistent columns")
        _validate_sql_script_scalar_values(rows, columns)

        frame = polars.DataFrame(
            rows,
            schema=columns,
            infer_schema_length=None,
            strict=True,
        )
        _ensure_query_values_lossless(rows, frame)
        return cast("pl.DataFrame", frame)
    except DataFrameDatabaseError:
        raise
    except Exception as error:
        _LOGGER.debug("SQL script result conversion failed")
        raise DataFrameDatabaseError(
            "Unable to convert SQL script result to a DataFrame",
            operation="convert",
            original_exception=error,
        ) from error


def _validate_sql_script_scalar_values(
    rows: list[dict[str, Any]], columns: list[str]
) -> None:
    supported = (
        bool,
        int,
        float,
        str,
        Decimal,
        bytes,
        bytearray,
        memoryview,
        timedelta,
    )
    for row in rows:
        for name in columns:
            value = row[name]
            if value is None or isinstance(value, supported):
                continue
            if isinstance(value, datetime):
                if value.tzinfo is not None and value.utcoffset() is not None:
                    raise ValueError("Timezone-aware SQL result values are unsupported")
                continue
            if isinstance(value, date):
                continue
            if isinstance(value, time):
                if value.tzinfo is not None and value.utcoffset() is not None:
                    raise ValueError("Timezone-aware SQL result values are unsupported")
                continue
            raise TypeError("SQL result value type is unsupported for Polars")


def query_dataframe(
    connection: Any,
    query: str,
    params: Mapping[str, object] | None = None,
) -> pl.DataFrame:
    """Execute one supported bound SQL statement into an eager Polars frame.

    The operation starts and owns one transaction, closes only its cursor, and
    commits after the complete result has been materialized.
    """
    try:
        prepared = prepare_query(query, params)
    except Exception as error:
        raise DataFrameDatabaseError(
            str(error), operation="query", original_exception=error
        ) from error

    try:
        polars = _require_dependencies("query")
    except DataFrameDatabaseError:
        raise

    try:
        if connection.in_transaction:
            raise DataFrameDatabaseError(
                "Cannot run a DataFrame query while a caller transaction is active",
                operation="query",
            )
    except DataFrameDatabaseError:
        raise
    except Exception as error:
        raise DataFrameDatabaseError(
            "Unable to inspect the MySQL transaction state",
            operation="query",
            original_exception=error,
        ) from error

    try:
        connection.start_transaction()
    except Exception as error:
        raise DataFrameDatabaseError(
            "Unable to start the DataFrame query transaction",
            operation="query",
            original_exception=error,
        ) from error

    cursor: Any | None = None
    result: Any = None
    primary_error: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        cursor = connection.cursor()
        reader_cursor = _CapturingCursor(cursor)
        _LOGGER.debug("Executing SQL-to-DataFrame query")
        options = {"params": prepared.params} if prepared.params else None
        result = polars.read_database(
            prepared.sql,
            reader_cursor,
            execute_options=options,
            infer_schema_length=None,
        )
        if cursor.description is None or not cursor.with_rows:
            raise ValueError("The SQL statement did not return a row result")
        if not isinstance(result, polars.DataFrame):
            raise TypeError("The Polars reader did not return an eager DataFrame")
        _ensure_query_values_lossless(reader_cursor.fetched_rows, result)
        nextset = getattr(cursor, "nextset", None)
        if callable(nextset) and nextset():
            raise ValueError("Multiple result sets are not supported")
    except BaseException as error:
        primary_error = error

    if cursor is not None:
        try:
            cursor.close()
        except BaseException as error:
            if primary_error is None:
                primary_error = error
            else:
                cleanup_errors.append(error)

    if primary_error is not None:
        try:
            connection.rollback()
        except BaseException as error:
            cleanup_errors.append(error)
        cleanup_error = _combined_cleanup_error(cleanup_errors)
        _LOGGER.debug("SQL-to-DataFrame query failed")
        raise DataFrameDatabaseError(
            "Unable to execute SQL query as a DataFrame",
            operation="query",
            original_exception=primary_error,
            cleanup_exception=cleanup_error,
        ) from primary_error

    try:
        connection.commit()
    except BaseException as error:
        try:
            connection.rollback()
        except BaseException as rollback_error:
            cleanup_errors.append(rollback_error)
        _LOGGER.debug("SQL-to-DataFrame query commit failed")
        raise DataFrameDatabaseError(
            "Unable to commit SQL-to-DataFrame query",
            operation="query",
            original_exception=error,
            cleanup_exception=_combined_cleanup_error(cleanup_errors),
        ) from error

    _LOGGER.debug("SQL-to-DataFrame query completed")
    return cast("pl.DataFrame", result)


@dataclass(frozen=True, slots=True)
class _ColumnMetadata:
    name: str
    data_type: str
    column_type: str
    nullable: bool
    length: int | None
    precision: int | None
    scale: int | None
    datetime_precision: int | None
    character_set: str | None
    collation: str | None
    extra: str


class _CapturingCursor:
    """Proxy that records fetched DB-API values for lossless-result checks."""

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self.fetched_rows: list[Any] | None = None

    @property
    def description(self) -> Any:
        return self._cursor.description

    @property
    def with_rows(self) -> bool:
        return bool(self._cursor.with_rows)

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    def execute(self, operation: str, **kwargs: Any) -> Any:
        return self._cursor.execute(operation, **kwargs)

    def fetchall(self) -> list[Any]:
        rows = list(self._cursor.fetchall())
        self.fetched_rows = rows
        return rows


def _ensure_query_values_lossless(
    fetched_rows: list[Any] | None, dataframe: Any
) -> None:
    if fetched_rows is None:
        raise ValueError("The SQL result could not be verified for lossless conversion")
    frame_rows = list(dataframe.iter_rows(named=False))
    if len(fetched_rows) != len(frame_rows):
        raise ValueError("Polars changed the SQL result row count")
    for source_row, frame_row in zip(fetched_rows, frame_rows, strict=True):
        if isinstance(source_row, Mapping):
            source_values = tuple(source_row[name] for name in dataframe.columns)
        else:
            source_values = tuple(source_row)
        if len(source_values) != len(frame_row) or any(
            not _query_value_equivalent(source, converted)
            for source, converted in zip(source_values, frame_row, strict=True)
        ):
            raise ValueError(
                "A SQL result value cannot be represented faithfully by Polars"
            )


def _query_value_equivalent(source: Any, converted: Any) -> bool:
    if isinstance(source, (bytes, bytearray, memoryview)) and isinstance(
        converted, (bytes, bytearray, memoryview)
    ):
        return bytes(source) == bytes(converted)
    if type(source) is not type(converted):
        return False
    if isinstance(source, float) and math.isnan(source):
        return isinstance(converted, float) and math.isnan(converted)
    try:
        return bool(source == converted)
    except Exception:
        return False


def import_dataframe(
    connection: Any,
    dataframe: pl.DataFrame,
    table_name: str,
    *,
    mode: ImportMode,
    key_columns: Sequence[str] | None = None,
    batch_size: int = 1000,
) -> DataFrameImportResult:
    """Import a Polars frame into an existing transactional MySQL table."""
    polars = _require_dependencies("import")
    try:
        _validate_import_arguments(
            polars,
            dataframe,
            table_name,
            mode,
            key_columns,
            batch_size,
        )
    except Exception as error:
        raise DataFrameDatabaseError(
            str(error), operation="import", original_exception=error
        ) from error

    if dataframe.height == 0:
        return DataFrameImportResult(rows_processed=0, batches_processed=0)

    try:
        if connection.in_transaction:
            raise DataFrameDatabaseError(
                "Cannot import a DataFrame while a caller transaction is active",
                operation="import",
            )
    except DataFrameDatabaseError:
        raise
    except Exception as error:
        raise DataFrameDatabaseError(
            "Unable to inspect the MySQL transaction state",
            operation="import",
            original_exception=error,
        ) from error

    try:
        connection.start_transaction()
    except Exception as error:
        raise DataFrameDatabaseError(
            "Unable to start the DataFrame import transaction",
            operation="import",
            original_exception=error,
        ) from error

    cursor: Any | None = None
    primary_error: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    batches_processed = 0
    staging_name: str | None = None
    try:
        cursor = connection.cursor(dictionary=True)
        columns = _load_target_columns(cursor, table_name)
        source_columns = list(dataframe.columns)
        _validate_source_columns(source_columns, columns)
        schema = dataframe.schema
        _validate_temporal_precision(dataframe, polars)
        for frame_slice in dataframe.iter_slices(n_rows=batch_size):
            for row in frame_slice.iter_rows(named=False):
                _convert_row(row, source_columns, schema, columns, polars)

        if mode is ImportMode.APPEND:
            batches_processed = _append_batches(
                cursor,
                dataframe,
                source_columns,
                schema,
                columns,
                table_name,
                batch_size,
                polars,
            )
        else:
            keys = list(key_columns or [])
            indexes = _load_indexes(cursor, table_name)
            _validate_unique_key(keys, columns, indexes)
            staging_name = f"pintos_utils_stage_{uuid4().hex}"
            _create_staging_table(cursor, staging_name, source_columns, columns, keys)
            batches_processed = _load_staging_batches(
                cursor,
                dataframe,
                source_columns,
                schema,
                columns,
                staging_name,
                batch_size,
                polars,
            )
            _apply_upsert(cursor, table_name, staging_name, source_columns, keys)
            cursor.execute(f"DROP TEMPORARY TABLE `{staging_name}`")
            staging_name = None
    except BaseException as error:
        primary_error = error

    if primary_error is not None:
        try:
            connection.rollback()
        except BaseException as error:
            cleanup_errors.append(error)
        if cursor is not None and staging_name is not None:
            try:
                cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS `{staging_name}`")
                staging_name = None
            except BaseException as error:
                cleanup_errors.append(error)
        if cursor is not None:
            try:
                cursor.close()
            except BaseException as error:
                cleanup_errors.append(error)
        cleanup_error = _combined_cleanup_error(cleanup_errors)
        message = (
            str(primary_error)
            if isinstance(primary_error, (ValueError, TypeError))
            else f"Unable to import DataFrame into table {table_name!r}"
        )
        _LOGGER.debug("DataFrame import failed")
        raise DataFrameDatabaseError(
            message,
            operation="import",
            original_exception=primary_error,
            cleanup_exception=cleanup_error,
        ) from primary_error

    if cursor is not None:
        try:
            cursor.close()
        except BaseException as error:
            try:
                connection.rollback()
            except BaseException as rollback_error:
                cleanup_errors.append(rollback_error)
            if staging_name is not None:
                try:
                    cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS `{staging_name}`")
                except BaseException as stage_error:
                    cleanup_errors.append(stage_error)
            raise DataFrameDatabaseError(
                f"Unable to close DataFrame import cursor for table {table_name!r}",
                operation="import",
                original_exception=error,
                cleanup_exception=_combined_cleanup_error(cleanup_errors),
            ) from error

    try:
        connection.commit()
    except BaseException as error:
        try:
            connection.rollback()
        except BaseException as rollback_error:
            cleanup_errors.append(rollback_error)
        _LOGGER.debug("DataFrame import commit failed")
        raise DataFrameDatabaseError(
            f"Unable to commit DataFrame import into table {table_name!r}",
            operation="import",
            original_exception=error,
            cleanup_exception=_combined_cleanup_error(cleanup_errors),
        ) from error

    _LOGGER.debug("DataFrame import completed")
    return DataFrameImportResult(
        rows_processed=dataframe.height,
        batches_processed=batches_processed,
    )


def _validate_import_arguments(
    polars: Any,
    dataframe: Any,
    table_name: str,
    mode: ImportMode,
    key_columns: Sequence[str] | None,
    batch_size: int,
) -> None:
    if not isinstance(dataframe, polars.DataFrame):
        raise TypeError("dataframe must be an eager Polars DataFrame")
    if not isinstance(mode, ImportMode):
        raise ValueError("Import mode must explicitly be APPEND or UPSERT")
    if not isinstance(table_name, str) or not _TABLE_IDENTIFIER.fullmatch(table_name):
        raise ValueError("table_name must be one unqualified MySQL identifier")
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size <= 0
    ):
        raise ValueError("batch_size must be a positive non-boolean integer")
    if len(set(dataframe.columns)) != len(dataframe.columns):
        raise ValueError("DataFrame column names must be unique")
    if any(not isinstance(name, str) or "\x00" in name for name in dataframe.columns):
        raise ValueError("DataFrame column names must be valid strings")
    if mode is ImportMode.APPEND and key_columns is not None:
        raise ValueError("key_columns are only supported for UPSERT mode")
    if mode is ImportMode.UPSERT:
        if (
            not isinstance(key_columns, Sequence)
            or isinstance(key_columns, (str, bytes))
            or not key_columns
        ):
            raise ValueError("UPSERT requires one or more key_columns")
        if any(not isinstance(name, str) or not name for name in key_columns):
            raise ValueError("UPSERT key column names must be non-empty strings")
        if len(set(key_columns)) != len(key_columns):
            raise ValueError("UPSERT key columns must be unique")
        missing = set(key_columns) - set(dataframe.columns)
        if missing:
            raise ValueError("UPSERT key columns must exist in the DataFrame")
        seen: set[tuple[Any, ...]] = set()
        key_indexes = [dataframe.columns.index(name) for name in key_columns]
        for source_row in dataframe.iter_rows(named=False):
            key = tuple(source_row[index] for index in key_indexes)
            if any(value is None for value in key):
                raise ValueError("UPSERT source keys cannot contain null values")
            try:
                duplicate = key in seen
                seen.add(key)
            except TypeError as error:
                raise ValueError("UPSERT source keys must be scalar values") from error
            if duplicate:
                raise ValueError("UPSERT source keys must be unique")


def _load_target_columns(cursor: Any, table_name: str) -> dict[str, _ColumnMetadata]:
    cursor.execute(
        """SELECT t.ENGINE AS engine, t.TABLE_TYPE AS table_type,
                  e.TRANSACTIONS AS transactions
           FROM INFORMATION_SCHEMA.TABLES AS t
           LEFT JOIN INFORMATION_SCHEMA.ENGINES AS e ON e.ENGINE = t.ENGINE
           WHERE t.TABLE_SCHEMA = DATABASE() AND t.TABLE_NAME = %s""",
        (table_name,),
    )
    table_rows = cursor.fetchall()
    if not table_rows:
        raise ValueError("Target table does not exist in the selected database")
    table = table_rows[0]
    if _row_value(table, "table_type") != "BASE TABLE":
        raise ValueError("Target must be an existing base table")
    if str(_row_value(table, "transactions") or "").upper() != "YES":
        raise ValueError("Target table engine does not support transactional rollback")

    cursor.execute(
        """SELECT COLUMN_NAME AS column_name, DATA_TYPE AS data_type,
                  COLUMN_TYPE AS column_type, IS_NULLABLE AS is_nullable,
                  CHARACTER_MAXIMUM_LENGTH AS character_maximum_length,
                  NUMERIC_PRECISION AS numeric_precision,
                  NUMERIC_SCALE AS numeric_scale,
                  DATETIME_PRECISION AS datetime_precision,
                  CHARACTER_SET_NAME AS character_set,
                  COLLATION_NAME AS collation, EXTRA AS extra
           FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
           ORDER BY ORDINAL_POSITION""",
        (table_name,),
    )
    rows = cursor.fetchall()
    if not rows:
        raise ValueError("Target table has no writable columns")
    result: dict[str, _ColumnMetadata] = {}
    for row in rows:
        name = str(_row_value(row, "column_name"))
        result[name] = _ColumnMetadata(
            name=name,
            data_type=str(_row_value(row, "data_type")).lower(),
            column_type=str(_row_value(row, "column_type")).lower(),
            nullable=str(_row_value(row, "is_nullable")).upper() == "YES",
            length=_optional_int(_row_value(row, "character_maximum_length")),
            precision=_optional_int(_row_value(row, "numeric_precision")),
            scale=_optional_int(_row_value(row, "numeric_scale")),
            datetime_precision=_optional_int(_row_value(row, "datetime_precision")),
            character_set=(
                str(_row_value(row, "character_set"))
                if _row_value(row, "character_set") is not None
                else None
            ),
            collation=(
                str(_row_value(row, "collation"))
                if _row_value(row, "collation") is not None
                else None
            ),
            extra=str(_row_value(row, "extra") or ""),
        )
    return result


def _load_indexes(cursor: Any, table_name: str) -> list[dict[str, Any]]:
    cursor.execute(
        """SELECT INDEX_NAME AS index_name, NON_UNIQUE AS non_unique,
                  SEQ_IN_INDEX AS seq_in_index, COLUMN_NAME AS column_name,
                  SUB_PART AS sub_part
           FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
           ORDER BY INDEX_NAME, SEQ_IN_INDEX""",
        (table_name,),
    )
    return list(cursor.fetchall())


def _validate_unique_key(
    key_columns: list[str],
    target_columns: dict[str, _ColumnMetadata],
    index_rows: list[dict[str, Any]],
) -> None:
    if any(name not in target_columns for name in key_columns):
        raise ValueError("UPSERT key columns must exist in the target table")

    indexes: dict[str, list[dict[str, Any]]] = {}
    for row in index_rows:
        name = str(_row_value(row, "index_name"))
        indexes.setdefault(name, []).append(row)

    requested = set(key_columns)
    for rows in indexes.values():
        if not rows or any(int(_row_value(row, "non_unique")) != 0 for row in rows):
            continue
        ordered = sorted(rows, key=lambda row: int(_row_value(row, "seq_in_index")))
        names = [_row_value(row, "column_name") for row in ordered]
        if any(name is None for name in names):
            continue
        if any(_row_value(row, "sub_part") is not None for row in ordered):
            continue
        if len(names) == len(key_columns) and set(names) == requested:
            return
    raise ValueError(
        "UPSERT key columns must exactly match a complete primary or unique index"
    )


def _row_value(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row[name]
    raise TypeError("Database metadata cursor did not return named columns")


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _validate_source_columns(
    source_columns: list[str], target_columns: dict[str, _ColumnMetadata]
) -> None:
    unknown = [name for name in source_columns if name not in target_columns]
    if unknown:
        raise ValueError("DataFrame contains columns absent from the target table")
    generated = [
        name
        for name in source_columns
        if "GENERATED" in target_columns[name].extra.upper()
    ]
    if generated:
        raise ValueError("DataFrame cannot provide generated target columns")


def _validate_temporal_precision(dataframe: Any, polars: Any) -> None:
    for name, dtype in dataframe.schema.items():
        base_type = dtype.base_type()
        if base_type not in {polars.Datetime, polars.Time}:
            continue
        if base_type is polars.Datetime and dtype.time_zone is not None:
            raise ValueError("Timezone-aware Polars datetimes are not supported")
        time_unit = dtype.time_unit if base_type is polars.Datetime else "ns"
        if time_unit == "ns":
            raw_values = dataframe.get_column(name).cast(polars.Int64).to_list()
            if any(value is not None and value % 1000 for value in raw_values):
                raise ValueError(
                    "Sub-microsecond temporal values cannot be stored exactly"
                )


def _convert_row(
    row: tuple[Any, ...],
    source_columns: list[str],
    schema: Mapping[str, Any],
    target_columns: dict[str, _ColumnMetadata],
    polars: Any,
) -> tuple[Any, ...]:
    return tuple(
        _convert_value(value, schema[name], target_columns[name], polars)
        for name, value in zip(source_columns, row, strict=True)
    )


def _convert_value(value: Any, dtype: Any, target: _ColumnMetadata, polars: Any) -> Any:
    if value is None:
        if not target.nullable:
            raise ValueError(
                "Null value cannot be stored in a non-nullable target column"
            )
        return None

    kind = dtype.base_type()
    mysql_type = target.data_type
    if kind is polars.Null:
        raise ValueError("A non-null value cannot have Polars Null dtype")

    if dtype.is_integer():
        if mysql_type not in _INTEGER_BITS:
            raise ValueError("Integer values require a compatible MySQL integer column")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Integer value cannot be converted exactly")
        bits = _INTEGER_BITS[mysql_type]
        unsigned = "unsigned" in target.column_type
        lower = 0 if unsigned else -(2 ** (bits - 1))
        upper = 2**bits - 1 if unsigned else 2 ** (bits - 1) - 1
        if not lower <= value <= upper:
            raise ValueError("Integer value is outside the target integer range")
        return value

    if kind is polars.Boolean:
        if mysql_type not in {*_INTEGER_BITS, "bit", "bool", "boolean"}:
            raise ValueError("Boolean values require a MySQL boolean or integer column")
        return bool(value)

    if dtype.is_float():
        if mysql_type not in {"float", "double", "real"}:
            raise ValueError(
                "Floating-point values require a MySQL FLOAT or DOUBLE column"
            )
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Non-finite floating-point values are not supported")
        if "unsigned" in target.column_type and number < 0:
            raise ValueError(
                "Negative floating-point values cannot be stored as unsigned"
            )
        if mysql_type == "float":
            try:
                stored = struct.unpack("!f", struct.pack("!f", number))[0]
            except OverflowError as error:
                raise ValueError(
                    "Floating-point value exceeds the target range"
                ) from error
            if stored != number:
                raise ValueError(
                    "Floating-point value cannot be represented exactly by FLOAT"
                )
        return number

    if kind is polars.Decimal:
        if mysql_type not in {"decimal", "numeric"} or not isinstance(value, Decimal):
            raise ValueError("Decimal values require a MySQL DECIMAL column")
        if "unsigned" in target.column_type and value < 0:
            raise ValueError("Negative decimal values cannot be stored as unsigned")
        _validate_decimal(value, target)
        return value

    if kind in {polars.String, polars.Categorical, polars.Enum}:
        if mysql_type not in _CHARACTER_TYPES or not isinstance(value, str):
            raise ValueError(
                "String values require a compatible MySQL character column"
            )
        if target.length is not None and len(value) > target.length:
            raise ValueError("String value exceeds the target character length")
        return value

    if kind is polars.Binary:
        if mysql_type not in _BINARY_TYPES or not isinstance(value, bytes):
            raise ValueError("Binary values require a compatible MySQL binary column")
        if target.length is not None and len(value) > target.length:
            raise ValueError("Binary value exceeds the target byte length")
        return value

    if kind is polars.Date:
        if (
            mysql_type != "date"
            or not isinstance(value, date)
            or isinstance(value, datetime)
        ):
            raise ValueError("Date values require a MySQL DATE column")
        return value

    if kind is polars.Datetime:
        if mysql_type != "datetime" or not isinstance(value, datetime):
            raise ValueError("Naive datetime values require a MySQL DATETIME column")
        if value.tzinfo is not None and value.utcoffset() is not None:
            raise ValueError("Timezone-aware Python datetimes are not supported")
        precision = target.datetime_precision
        if precision is not None and precision < 6:
            factor = 10 ** (6 - precision)
            if value.microsecond % factor:
                raise ValueError(
                    "Datetime value exceeds the target fractional precision"
                )
        return value

    if kind is polars.Time:
        if mysql_type != "time" or not isinstance(value, time):
            raise ValueError("Time values require a MySQL TIME column")
        precision = target.datetime_precision
        if precision is not None and precision < 6:
            factor = 10 ** (6 - precision)
            if value.microsecond % factor:
                raise ValueError("Time value exceeds the target fractional precision")
        return value

    raise ValueError("Polars dtype is not supported for lossless MySQL import")


def _validate_decimal(value: Decimal, target: _ColumnMetadata) -> None:
    if not value.is_finite():
        raise ValueError("Non-finite decimal values are not supported")
    precision = target.precision
    scale = target.scale
    if precision is None or scale is None:
        raise ValueError("Target DECIMAL precision metadata is unavailable")
    quantum = Decimal(1).scaleb(-scale)
    try:
        quantized = value.quantize(quantum)
    except InvalidOperation as error:
        raise ValueError("Decimal value exceeds target precision") from error
    if quantized != value:
        raise ValueError("Decimal value exceeds target scale")
    digits = value.copy_abs().as_tuple().digits
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("Decimal value has an unsupported exponent")
    integer_digits = max(len(digits) + exponent, 0)
    if integer_digits > precision - scale:
        raise ValueError("Decimal value exceeds target precision")


def _append_batches(
    cursor: Any,
    dataframe: Any,
    source_columns: list[str],
    schema: Mapping[str, Any],
    target_columns: dict[str, _ColumnMetadata],
    table_name: str,
    batch_size: int,
    polars: Any,
) -> int:
    quoted_table = _quote_identifier(table_name)
    quoted_columns = ", ".join(_quote_identifier(name) for name in source_columns)
    placeholders = ", ".join("%s" for _ in source_columns)
    statement = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})"
    batches = 0
    for frame_slice in dataframe.iter_slices(n_rows=batch_size):
        batch = [
            _convert_row(row, source_columns, schema, target_columns, polars)
            for row in frame_slice.iter_rows(named=False)
        ]
        cursor.executemany(statement, batch)
        batches += 1
    return batches


def _create_staging_table(
    cursor: Any,
    staging_name: str,
    source_columns: list[str],
    target_columns: dict[str, _ColumnMetadata],
    key_columns: list[str],
) -> None:
    definitions: list[str] = []
    for name in source_columns:
        target = target_columns[name]
        column_type = target.column_type
        if not _STAGING_COLUMN_TYPE.fullmatch(column_type):
            raise ValueError("Target column type cannot be copied safely to staging")
        character_attributes = ""
        if target.character_set is not None:
            if not _CHARSET_IDENTIFIER.fullmatch(target.character_set):
                raise ValueError("Target character set metadata is invalid")
            character_attributes += f" CHARACTER SET {target.character_set}"
        if target.collation is not None:
            if not _CHARSET_IDENTIFIER.fullmatch(target.collation):
                raise ValueError("Target collation metadata is invalid")
            character_attributes += f" COLLATE {target.collation}"
        nullability = "NULL" if target.nullable else "NOT NULL"
        definitions.append(
            f"{_quote_identifier(name)} {column_type}"
            f"{character_attributes} {nullability}"
        )
    key_index = (
        "UNIQUE KEY `pintos_utils_source_key` ("
        + ", ".join(_quote_identifier(name) for name in key_columns)
        + ")"
    )
    columns = ", ".join([*definitions, key_index])
    cursor.execute(
        f"CREATE TEMPORARY TABLE {_quote_identifier(staging_name)} "
        f"({columns}) ENGINE=InnoDB"
    )


def _load_staging_batches(
    cursor: Any,
    dataframe: Any,
    source_columns: list[str],
    schema: Mapping[str, Any],
    target_columns: dict[str, _ColumnMetadata],
    staging_name: str,
    batch_size: int,
    polars: Any,
) -> int:
    quoted_columns = ", ".join(_quote_identifier(name) for name in source_columns)
    placeholders = ", ".join("%s" for _ in source_columns)
    statement = (
        f"INSERT INTO {_quote_identifier(staging_name)} ({quoted_columns}) "
        f"VALUES ({placeholders})"
    )
    batches = 0
    for frame_slice in dataframe.iter_slices(n_rows=batch_size):
        batch = [
            _convert_row(row, source_columns, schema, target_columns, polars)
            for row in frame_slice.iter_rows(named=False)
        ]
        cursor.executemany(statement, batch)
        batches += 1
    return batches


def _apply_upsert(
    cursor: Any,
    table_name: str,
    staging_name: str,
    source_columns: list[str],
    key_columns: list[str],
) -> None:
    quoted_target = _quote_identifier(table_name)
    quoted_stage = _quote_identifier(staging_name)
    join_condition = " AND ".join(
        f"t.{_quote_identifier(name)} = s.{_quote_identifier(name)}"
        for name in key_columns
    )
    non_key_columns = [name for name in source_columns if name not in key_columns]
    if non_key_columns:
        assignments = ", ".join(
            f"t.{_quote_identifier(name)} = s.{_quote_identifier(name)}"
            for name in non_key_columns
        )
        cursor.execute(
            f"UPDATE {quoted_target} AS t JOIN {quoted_stage} AS s "
            f"ON {join_condition} SET {assignments}"
        )

    target_columns = ", ".join(_quote_identifier(name) for name in source_columns)
    selected_columns = ", ".join(
        f"s.{_quote_identifier(name)}" for name in source_columns
    )
    cursor.execute(
        f"INSERT INTO {quoted_target} ({target_columns}) "
        f"SELECT {selected_columns} FROM {quoted_stage} AS s "
        f"WHERE NOT EXISTS (SELECT 1 FROM {quoted_target} AS t "
        f"WHERE {join_condition})"
    )


def _quote_identifier(identifier: str) -> str:
    if not identifier or "\x00" in identifier:
        raise ValueError("SQL identifier is invalid")
    return f"`{identifier.replace('`', '``')}`"


def _require_dependencies(operation: Literal["query", "import"]) -> Any:
    """Load optional drivers only when a database DataFrame operation is invoked."""
    try:
        importlib.import_module("mysql.connector")
    except ImportError as error:
        raise DataFrameDatabaseError(
            "DataFrame database operations require pintos-utils[mysql,polars]",
            operation=operation,
            original_exception=error,
        ) from error
    return _require_polars(operation)


def _require_polars(
    operation: Literal["query", "import", "convert"],
) -> Any:
    """Load Polars lazily and give the operation-specific installation extra."""
    try:
        return importlib.import_module("polars")
    except ImportError as error:
        extra = "polars" if operation == "convert" else "mysql,polars"
        raise DataFrameDatabaseError(
            f"DataFrame operations require pintos-utils[{extra}]",
            operation=operation,
            original_exception=error,
        ) from error


def _combined_cleanup_error(errors: list[BaseException]) -> BaseException | None:
    if not errors:
        return None
    if len(errors) == 1:
        return errors[0]
    ordinary = [error for error in errors if isinstance(error, Exception)]
    if len(ordinary) == len(errors):
        return ExceptionGroup("DataFrame operation cleanup failed", ordinary)
    return errors[0]
