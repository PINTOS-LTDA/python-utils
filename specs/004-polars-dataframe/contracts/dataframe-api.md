# Public Contract: Database DataFrame API

## Installation and import

```bash
python -m pip install "pintos-utils[mysql,polars]"
```

The base package, `pintos_utils.database`, and the API's public enums/models/errors remain importable without Polars. Calling either DataFrame operation requires the MySQL and Polars extras. Missing dependencies produce `DataFrameDatabaseError` with the installation command.

```python
from pintos_utils.database import (
    DataFrameDatabaseError,
    DataFrameImportResult,
    ImportMode,
    import_dataframe,
    query_dataframe,
)
```

## Signatures

```python
def query_dataframe(
    connection: MySQLConnection,
    query: str,
    params: Mapping[str, object] | None = None,
) -> polars.DataFrame: ...

def import_dataframe(
    connection: MySQLConnection,
    dataframe: polars.DataFrame,
    table_name: str,
    *,
    mode: ImportMode,
    key_columns: Sequence[str] | None = None,
    batch_size: int = 1000,
) -> DataFrameImportResult: ...
```

The annotations use type-only Polars imports so importing the API does not load the optional package. Runtime checks still require an actual eager `polars.DataFrame`; `LazyFrame` is unsupported.

## Query behavior

- Accept exactly one preflight-supported SQL statement. `:name` parameters are passed through Connector/Python binding and never interpolated by the library. SQL identifiers cannot be bound as values.
- Return one fully materialized result set as an eager DataFrame. Preserve result column names, their query order, row count, and values where Polars can represent the driver values faithfully. Empty results retain column names and order; their dtype is not guaranteed. A statement may change data while returning rows, including a `SELECT` that invokes a data-modifying MySQL stored function, provided the consumer ensures its side effects affect only transactional tables in the same connection.
- Reject transaction-control commands, statements that may implicitly commit, stored procedure calls, multiple statements, and additional result sets before committing. Statements that do not produce a result set fail.
- Reject an active caller transaction before sending SQL. Start an operation-owned transaction with `connection.start_transaction()`. Commit after full materialization, including a valid zero-row result. On execution, conversion, additional-result-set, cursor cleanup, or commit error, attempt rollback and report the original cause. Rollback covers effects that participate in the operation-owned transaction; nontransactional-table and external side effects are outside the guarantee.
- Never close the supplied connection or alter its autocommit setting.

## Import behavior

- `mode` is mandatory. `APPEND` inserts every source row and does not accept `key_columns`. `UPSERT` requires one or more `key_columns`.
- `table_name` is one unqualified MySQL base-table identifier in the database selected on the connection. The API does not create or alter the target table or change the selected schema.
- DataFrame columns map by exact name. Extra target columns are omitted from generated SQL and retain their defaults/constraints. Unknown or generated target columns in the frame are rejected before writes.
- Imports require a transaction-capable storage engine. A non-empty import starts one owned transaction, shares it across all batches, commits once after all work and staging cleanup, and attempts rollback on any error. Reject an active caller transaction before metadata SQL or writes, without changing it. Do not close the supplied connection or change autocommit.
- Empty DataFrames are validated no-ops and do not start, commit, or roll back an import transaction.
- `batch_size` must be a positive non-boolean integer. The default is 1,000 rows. Each bounded slice is bound with `executemany`; batches do not commit independently.
- Fail on unsupported types, out-of-range values, decimal precision/scale loss, character/binary truncation, lossy float conversion, or sub-microsecond temporal values. Supported mappings and failures are detailed in [research.md](../research.md). No silent coercion or truncation is allowed.

### APPEND

Insert all rows in source column order with a parameterized `INSERT`. A uniqueness, foreign-key, nullability, or conversion failure aborts the operation and rolls back all target rows from this import.

### UPSERT

- The complete `key_columns` tuple must exactly match the columns of a primary or unique target index. Prefix and functional indexes do not qualify.
- Every source key must be non-null and the source must contain no repeated key tuple. These validations happen before target rows are changed.
- Matching rows receive all supplied non-key values. If there are no non-key source columns, matching rows remain unchanged. Unmatched source rows are inserted, with omitted target columns left to MySQL defaults and constraints.
- Load source rows into an operation-scoped session temporary table, update target matches by the selected key, then insert unmatched rows. The temporary table is dropped before commit.
- A conflict on another target unique constraint fails and rolls back; it must not select a different row for update. A concurrent conflicting UPSERT can fail with a duplicate-key, deadlock, or lock-timeout error. The API does not retry automatically.

## Result and errors

`DataFrameImportResult` reports `rows_processed` and `batches_processed`. It does not split rows into inserted and updated counts.

`DataFrameDatabaseError` reports an operation identifier and preserves `original_exception` when available. If rollback or staging cleanup also fails, preserve that as secondary cleanup context without replacing the primary cause. Default logs/errors do not include parameter values or row contents.

## Stability

All public names are exported from `pintos_utils.database` and have type annotations. The feature is additive. Changes that alter these names, signatures, transaction ownership, conversion policy, or mode semantics require compatibility review under the project's Semantic Versioning policy.
