# Data Model: Polars DataFrame Database Integration

This feature has no durable schema or ORM entities. Its data model describes the public request/result types and short-lived structures used while operating on a consumer-owned MySQL connection.

## Public types

### `ImportMode`

A string enum with two required values:

- `APPEND`: insert every input row.
- `UPSERT`: update rows matched by the supplied key columns and insert unmatched rows.

The import function requires an explicit enum value. It does not infer a mode.

### `DataFrameImportResult`

An immutable typed result with:

- `rows_processed: int`: number of source rows successfully committed.
- `batches_processed: int`: number of bounded source batches submitted; zero for an empty no-op.

It does not report separate inserted and updated counts because MySQL/Connector affected-row semantics depend on whether values changed and on client flags.

### `DataFrameDatabaseError`

Feature-specific exception context:

- `operation`: `query` or `import`.
- `original_exception`: underlying driver, Polars, or conversion exception when present.
- `cleanup_exception`: optional rollback or temporary-table cleanup failure that must not hide the primary failure.

Messages identify operation/table context without including SQL parameter values or row contents. The import exception should avoid embedding data-frame values. The existing `SqlScriptError` contract remains unchanged.

## Operation data

### Query request/result

Input consists of a supplied MySQL Connector/Python connection, one supported SQL statement, and an optional parameter mapping. Stored procedure calls and multiple SQL statements are rejected; an additional result set is rejected before commit. Public `:name` markers are translated to connector binding syntax and values remain separately bound. The operation returns one eager Polars DataFrame containing the single result set's column names, order, and values. Zero-row results retain their column names and order; zero-row dtypes are unspecified.

Internal query state consists of parsed statement tokens, normalized parameter bindings, cursor metadata, and the materialized result. These are transient and never stored on the connection or returned separately.

### Import request

The request contains:

- an eager Polars DataFrame;
- an unqualified existing table name in the connection's selected database;
- explicit `ImportMode`;
- key column names for UPSERT only;
- positive `batch_size`, defaulting to 1,000 rows.

DataFrame columns map to target columns by exact name, independent of target column order. Every supplied column must exist in the target. Omitted target columns use MySQL defaults and constraints. Duplicate source column names, invalid identifiers, absent target columns, invalid batches, or unsupported mode/key combinations fail before target writes.

An empty DataFrame is a no-op: after validating that it is a Polars DataFrame and the mode/arguments are structurally valid, no import transaction or database write is started. Its result reports zero rows and batches.

### Target metadata snapshot

During import preflight, query MySQL metadata for the named base table, engine, ordered columns, nullability, defaults, type family, precision/scale/length, character set/collation, generated-column state, and unique indexes. Validate the requested operation against this metadata before row writes:

- table exists and is a base table in the selected database;
- storage engine supports transactions;
- DataFrame column names exist and are writable;
- each Polars-to-MySQL mapping is supported and range/precision safe;
- UPSERT key names exist in both source and target;
- a complete primary/unique index exactly covers the key tuple (prefix/function indexes are excluded);
- the source key tuples contain no nulls or duplicates.

The metadata snapshot is only used during that call. It is not a schema cache and does not change the target schema.

### Import batch

A batch is at most `batch_size` row tuples obtained from one non-copying Polars slice. It is sent with parameter binding through `cursor.executemany`. Batches share one operation-owned transaction; a batch boundary never commits.

The target table remains the authoritative owner of defaults, foreign keys, checks, and uniqueness outside the selected UPSERT key. A violation causes the operation to fail and roll back.

### UPSERT staging table

An internal name generated for one call identifies a MySQL session-local temporary table. Its columns mirror only the input columns, with explicit type, nullability, character set, and collation definitions from target metadata. It has one unique index over the selected key tuple and no other target indexes or constraints, so MySQL key comparison rules reject collation-equivalent duplicate source keys during staging. It is populated in batches, joined to the target by the supplied key tuple, and dropped before commit. It is not a persistent entity and must not survive successful cleanup.

UPSERT ordering:

1. validate source keys and target metadata;
2. start an owned transaction;
3. create the temporary staging table and load all batches;
4. update matching target rows for supplied non-key columns;
5. insert staging rows with no target key match;
6. drop the staging table;
7. commit once.

If any step fails, attempt rollback and staging cleanup while preserving the primary error. A temporary table can survive rollback because MySQL does not roll back temporary-table creation, so cleanup is an explicit part of the lifecycle.

## Transaction state

Each non-empty query or import transitions through:

`in-memory preflight -> active-transaction check -> transaction started -> database preflight -> execute/materialize or write -> cleanup cursor/stage -> commit`

Any failure after transaction start transitions to:

`rollback attempted -> cleanup attempted -> error reported`

Before transaction start, validate function arguments and source-only properties. Reject an active caller transaction before issuing metadata SQL, and leave it untouched. Read target metadata inside the new owned transaction so no database work is performed in the caller's transaction; reject an invalid target or schema before target row writes. Query rollback covers effects that participate in the operation-owned transaction; consumers must ensure data-changing query effects are limited to transactional tables in the same connection. Nontransactional and external effects are outside this guarantee. The supplied connection is never closed, its autocommit setting is never changed, and empty imports do not enter this lifecycle. Rollback/cleanup failures are recorded alongside the primary failure.
