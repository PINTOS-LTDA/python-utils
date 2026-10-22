# Research: Polars DataFrame Database Integration

**Date**: 2026-10-22
**Scope**: Polars' Python API, existing MySQL Connector/Python integration, transaction ownership, bounded writes, and key-based UPSERT.

## Decisions

### 1. Use Polars with the consumer's existing cursor

Use `polars.read_database` with a cursor explicitly created from the supplied MySQL connection. This keeps execution in the caller's session and transaction; URI-based readers could create another connection and cannot satisfy that boundary. Supply parameters through the cursor's bound-parameter API, after translating the library's existing `:name` marker convention to Connector/Python's `%(name)s` style. Set `infer_schema_length=None` so non-empty results are inferred across all rows rather than a sample. Keep result materialization eager and fully in memory, consistent with the spec.

Polars documents `read_database` for DB-API connections/cursors and supports execution options and schema overrides. An already-open cursor remains under the caller's control, so the library can own its cleanup. A zero-row result can retain column names and order from cursor metadata, but its values provide no dtype evidence; zero-row dtypes are therefore not promised by this feature. The acceptance contract is the column names/order and zero row count.

Use one result set. Preflight exactly one SQL statement, reject transaction-control and potentially implicit-commit forms, reject stored procedure calls (their bodies can contain transaction control and may return multiple result sets), and reject any additional result set exposed by the cursor before commit. MySQL permits data-modifying side effects from stored functions used in a `SELECT`, while stored functions are restricted from explicit or implicit transaction commits. Rollback covers only effects that participate in the operation-owned transaction; the consumer must ensure data-changing statements affect only transactional tables in the same connection. Effects on nontransactional tables or external systems are outside this guarantee, and the library cannot inspect hidden routine effects. A statement that has no row result is an operation error and is rolled back.

References: [Polars `read_database`](https://docs.pola.rs/api/python/stable/reference/api/polars.read_database.html), [Polars database guide](https://docs.pola.rs/user-guide/io/database/), [Connector/Python cursor description](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-description.html), [Connector/Python multiple result sets](https://dev.mysql.com/doc/connector-python/en/connector-python-multi.html), [MySQL stored routine restrictions](https://dev.mysql.com/doc/refman/8.4/en/stored-program-restrictions.html), [MySQL data-modifying function side effects](https://dev.mysql.com/doc/refman/8.4/en/subquery-restrictions.html).

### 2. Start and own transactions through Connector/Python

Before sending SQL, inspect `connection.in_transaction` and reject an active transaction. Start new work with `connection.start_transaction()` rather than sending raw `START TRANSACTION`; Connector/Python raises if a transaction is already active, while MySQL's SQL statement can implicitly commit the current transaction. Leave `autocommit` unchanged. Commit once after complete result materialization or all import batches; on execution, conversion, cursor-close, or commit failure, attempt rollback and preserve the primary exception if rollback/cleanup also fails. Never close the supplied connection.

References: [Connector/Python `in_transaction`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-in-transaction.html), [Connector/Python `start_transaction`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-start-transaction.html), [MySQL implicit commits](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html).

### 3. Use bounded `executemany` batches for APPEND and staging loads

Iterate through non-copying DataFrame slices, convert only the current slice to Python-native row tuples, and pass each batch to Connector/Python `executemany`. Do not materialize the full source a second time as a list of rows. Choose a default batch size of 1,000 rows, allow a positive per-call override, and do not commit between batches. Connector/Python optimizes insert `executemany` into multi-row values statements. The row limit is configurable because row width and MySQL packet limits vary.

Polars warns that row iteration can truncate nanosecond temporal values to Python's microsecond precision. Preflight such columns and reject values whose sub-microsecond remainder is nonzero before converting them. Unsupported nested/object values and timezone-aware datetimes also fail explicitly. Keep the supported scalar conversion matrix narrow and verify target compatibility before writes; do not depend on permissive server-side coercion or truncation.

References: [Polars `iter_slices`](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.iter_slices.html), [Polars `iter_rows`](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.iter_rows.html), [Connector/Python `executemany`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-executemany.html).

### 4. Use session temporary staging and explicit key reconciliation for UPSERT

Confirm the target is an existing base table on a transactional engine, all DataFrame columns exist, and the requested key columns form a complete primary or unique index. Read index metadata from `INFORMATION_SCHEMA.STATISTICS`; reject prefix or functional indexes for this contract. Reject null or duplicate source key tuples before touching target rows. MySQL unique keys can permit multiple `NULL` values, so source keys must be non-null.

Create a unique, operation-scoped temporary InnoDB table with explicit column definitions reconstructed from target `COLUMN_TYPE`, nullability, character-set, and collation metadata. Do not use `CREATE TEMPORARY TABLE ... SELECT` to copy definitions: MySQL documents that `CREATE TABLE ... SELECT` can convert data types, including converting `VARCHAR` columns to `CHAR`, which can change staged values. Add one unique index over the selected key tuple and no other target indexes or constraints. The key index applies the target columns' equality and collation rules to source keys, catching duplicates that Python equality would miss. Load rows in bounded batches. Update matched target rows by joining on the caller-selected key, then insert unmatched rows with `INSERT ... SELECT ... WHERE NOT EXISTS`. Do not use `INSERT ... ON DUPLICATE KEY UPDATE`: MySQL chooses any conflicting unique index, which can update the wrong row when the target has more than one unique constraint. A conflict on another unique index should fail and roll back the operation.

Drop the temporary table before commit and retry cleanup after failure where possible. MySQL's `CREATE TEMPORARY TABLE` and `DROP TEMPORARY TABLE` avoid implicit commit, but temporary-table creation is not rolled back; explicit cleanup is required, particularly when a caller retains a pooled session. The target engine must support transactions so ordinary target writes remain rollbackable.

Concurrent UPSERTs rely on the target's unique key for integrity. A competing insert may cause duplicate-key, deadlock, or lock-timeout failure; roll back and surface it. Do not add automatic retries in the first release because retry policy and idempotency belong to the caller.

References: [MySQL `INFORMATION_SCHEMA.STATISTICS`](https://dev.mysql.com/doc/refman/8.4/en/information-schema-statistics-table.html), [MySQL `INFORMATION_SCHEMA.TABLES`](https://dev.mysql.com/doc/refman/8.4/en/information-schema-tables-table.html), [MySQL unique constraints](https://dev.mysql.com/doc/refman/8.4/en/constraint-primary-key.html), [MySQL `ON DUPLICATE KEY UPDATE`](https://dev.mysql.com/doc/refman/8.4/en/insert-on-duplicate.html), [MySQL `CREATE TABLE ... SELECT` type behavior](https://dev.mysql.com/doc/refman/8.4/en/create-table-select.html), [MySQL temporary tables](https://dev.mysql.com/doc/refman/8.4/en/create-temporary-table.html), [MySQL temporary-table drops](https://dev.mysql.com/doc/refman/8.4/en/drop-table.html), [InnoDB transaction isolation](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html).

### 5. Keep Polars optional and expose a small API

Add a `polars` extra without changing base dependencies; consumers install `[mysql,polars]` for database DataFrame support. Import Polars lazily inside the two operations, with type-only imports for annotations, so existing modules and public mode/result/error models remain importable without Polars. Keep the direct Connector/Python implementation; `DataFrame.write_database` uses other engine/dependency paths and does not match the transaction and staging contract as directly.

Use module-level functions rather than a new executor/factory abstraction. Export `query_dataframe`, `import_dataframe`, `ImportMode`, `DataFrameImportResult`, and `DataFrameDatabaseError`. The result model reports source rows and batches processed only. It does not promise inserted-versus-updated counts because connector row-count conventions vary.

Reference: [Polars database guide](https://docs.pola.rs/user-guide/io/database/).

## Conversion policy to implement

Before writing, inspect Polars dtypes and target column metadata. Support the scalar mappings whose value domains can be checked exactly: integer and unsigned integer to compatible integer columns with range checks; boolean to compatible boolean/integer columns; Float32/Float64 to compatible FLOAT/DOUBLE columns with overflow/rounding checks; Decimal to DECIMAL only when scale and precision fit exactly; string/categorical/enum to compatible character columns without character truncation; binary to compatible binary columns without byte truncation; Date to DATE; naive Datetime with microsecond precision to DATETIME; and Time to TIME. Null values remain SQL `NULL` subject to target nullability. Reject nested/array/struct/object/duration values, timezone-aware datetimes, unsupported MySQL target types, and any conversion that cannot be proven lossless. Database constraints remain authoritative for defaults, foreign keys, and additional uniqueness constraints.

For query results, rely on Polars' Python-value inference across the full result. Values outside Polars' representable domain or columns that cannot be represented consistently must produce an operation error. The empty-result contract does not require preserving a declared MySQL dtype.

## Limits and explicit non-goals

- Eager query results may consume memory proportional to the entire result set. No iterator, Arrow, or chunked-result API is part of this feature.
- Stored procedure calls and multiple SQL statements are rejected before execution. Additional result sets are rejected before commit. A single `SELECT` that invokes a data-modifying stored function remains eligible, but the consumer must ensure its side effects are limited to transactional tables in the same connection; nontransactional and external effects are outside the rollback guarantee.
- Import is limited to the connection's currently selected schema and an unqualified table name; creating connections, changing schema, or targeting views are outside scope.
- No automatic retry, schema creation, target alteration, or cross-provider adapter is introduced.
- The first release will document the tested MySQL server version after opt-in integration verification; the repository currently declares no server-version floor.
