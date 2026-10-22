# Implementation Plan: Polars DataFrame Database Integration

**Branch**: `004-polars-dataframe` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-polars-dataframe/spec.md`

## Summary

Add an optional, typed MySQL DataFrame API: `query_dataframe` returns the result of one supported SQL statement as an eager Polars DataFrame, and `import_dataframe` writes rows to an existing transactional table in explicit `APPEND` or `UPSERT` mode. Both operations preserve the caller's connection, own one transaction when applicable, and use bound values. Polars remains optional. APPEND uses bounded `executemany` batches; UPSERT loads an operation-scoped temporary table and reconciles by an explicitly selected, constraint-backed key.

## Technical Context

**Language/Version**: Python >=3.11; preserve the project's type-checking and `src/` conventions.

**Primary Dependencies**: Existing optional `mysql` extra (`mysql-connector-python>=9.2,<10`, `sqlparse>=0.5,<1`); add a named optional `polars` extra (planned `polars>=1.0,<3`). Consumers install both extras for this feature. No new base dependency.

**Storage**: MySQL only. Imports require an existing base table whose storage engine advertises transaction support. UPSERT uses a session-local InnoDB temporary table; no persistent target-schema objects are created.

**Testing**: Deterministic pytest unit tests with extended fake connection/cursor behavior; opt-in integration coverage only against an explicitly configured disposable MySQL database. Implementation verification also follows the constitution's Ruff, mypy, package-build, and coverage checks.

**Target Platform**: Python applications using a consumer-created MySQL Connector/Python connection. The minimum MySQL server version is not currently declared by the project; use long-standing `INFORMATION_SCHEMA`, transaction, and temporary-table features and document the tested server version when implementation integration tests are run.

**Project Type**: Reusable Python library with an optional provider capability.

**Performance Goals**: Bounded source-to-driver batches, default `batch_size=1000`, with the option to tune per call. Query results are fully materialized in memory as required by the eager DataFrame return contract. No throughput benchmark or large-result streaming API is in scope.

**Constraints**: Keep SQL values bound and identifiers safely quoted; do not log row contents or bound values. Reject a connection with an active caller transaction. Do not change autocommit or close the connection. Fail on unsupported or lossy conversions. Query rollback covers effects that participate in the operation-owned transaction; the consumer must ensure data-changing queries affect only transactional tables in the same connection. UPSERT must not use MySQL's conflict-on-any-unique-key behavior.

**Scale/Scope**: One supported SQL statement and one result set per query operation; stored procedure calls and multiple SQL statements are rejected; one existing target table per import; eager Polars DataFrames; bounded writes; no schema creation, DDL migration, connection pooling, retry policy, or support for other database providers.

## Constitution Check

**Before Phase 0**

- **I. Library-first and framework independence — PASS.** The public API is a Python library capability and adds no framework dependency.
- **II. Stable, typed public API — PASS.** Define and export typed functions, mode enum, result model, and feature-specific exception. The API is additive and intended for a compatible minor release; T023 reviews the public surface and records its SemVer compatibility impact before release.
- **III. Explicit boundaries and proportional dependency injection — PASS.** The consumer supplies the MySQL connection; provider metadata, transaction handling, and SQL remain at the database boundary. No factory or service layer is needed.
- **IV. Optional integrations and secure defaults — PASS.** Polars is a named optional extra, imported lazily; no values or secrets are logged.
- **V. Verification and documentation — PASS.** Plan includes offline fakes, opt-in disposable MySQL integration checks, static checks, and consumer documentation.

**After Phase 1**

The proposed design still passes all five principles: it keeps Polars out of base imports, places the API in the existing database package, uses injected connection state, and keeps validation at the MySQL boundary. T023 is the pre-release public API compatibility gate; no constitution exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/004-polars-dataframe/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── dataframe-api.md
└── tasks.md                 # Produced by $speckit-tasks; not part of this plan
```

### Source Code (repository root)

```text
pyproject.toml                              # Optional polars extra
src/pintos_utils/database/
├── __init__.py                             # Export the public API
├── _sql.py                                  # Shared single-statement/marker preflight
├── dataframe.py                             # Query and import operations
├── exceptions.py                            # DataFrameDatabaseError
└── models.py                                # ImportMode and DataFrameImportResult
docs/database.md                             # Installation, API, limitations
tests/unit/database/
├── fakes.py                                 # Transaction and batch instrumentation
├── test_dataframe_models.py                 # Public mode/result contracts
├── test_dataframe_exceptions.py             # Feature error contract
├── test_dataframe_query.py                  # Offline query behavior
├── test_dataframe_append.py                 # Offline APPEND behavior
├── test_dataframe_upsert.py                 # Offline UPSERT behavior
└── test_dataframe_optional.py               # Optional dependency behavior
tests/integration/database/
└── test_dataframe_mysql.py                  # Opt-in disposable MySQL acceptance
```

**Structure Decision**: Extend the existing `pintos_utils.database` package and its current unit/integration test layout. Extract only reusable SQL marker and statement-preflight behavior into a private helper if needed; do not couple the new API to `SqlScriptExecutor` or make Polars a package-import requirement.

## Phase 0: Research

Completed in [research.md](research.md). The research resolves Polars cursor integration, named binding and transaction handling, bounded batching, temporary staging, key validation, and failure/concurrency behavior. It also records explicit limits where MySQL or Polars cannot provide the guarantees without additional policy.

## Phase 1: Design

Completed in [data-model.md](data-model.md), [contracts/dataframe-api.md](contracts/dataframe-api.md), and [quickstart.md](quickstart.md). The contract calls for `query_dataframe(connection, query, params=None)` and `import_dataframe(connection, dataframe, table_name, *, mode, key_columns=None, batch_size=1000)`, with `ImportMode`, `DataFrameImportResult`, and `DataFrameDatabaseError` exported from `pintos_utils.database`.

The query operation will preflight one supported statement, reject stored procedure calls, hidden transaction/implicit-commit behavior, and multiple SQL statements, validate the single result before commit, start an explicit Connector/Python transaction, materialize the result, close its cursor, and commit once. Rollback covers effects that participate in that transaction; the consumer is responsible for ensuring data-changing statements do not affect nontransactional tables or external systems. Import first validates arguments and source-only constraints in memory, rejects an active caller transaction, then starts its transaction and checks target metadata/conversions before any target row write. APPEND batches directly into the target. UPSERT writes batches to a uniquely named session temporary table, applies a key-based `UPDATE` followed by an ordinary insert of unmatched rows, drops the temporary table, and commits once.

## Complexity Tracking

No constitution violations or additional architectural layers are proposed.
