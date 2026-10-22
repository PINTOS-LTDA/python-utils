# Feature Specification: Polars DataFrame Database Integration

**Feature Branch**: `004-polars-dataframe`<br>
**Created**: 2026-10-22<br>
**Status**: Draft
**Input**: User request to return Polars DataFrames from SQL queries and import Polars DataFrames into existing database tables using APPEND or UPSERT.

## Clarifications

### Session 2026-10-22

- Q: Should the query-to-DataFrame capability accept only read-only queries, or may it execute SQL that changes data? → A: It may execute one supported SQL statement that returns rows, including statements that change data, subject to the documented transaction and result-set limits.
- Q: Who should decide whether changes made by a statement that returns rows are committed or rolled back? → A: The DataFrame operation owns a transaction, commits after success, attempts rollback on failure, rejects a connection with pre-existing uncommitted work, and leaves the connection open.
- Q: Should the query-to-DataFrame operation reject statements that control transactions or commit implicitly, even if they return rows? → A: It rejects those statements before execution so the operation can preserve its transaction and rollback guarantees.
- Q: Are stored procedure calls, multiple SQL statements, or multiple result sets supported? → A: No. Reject `CALL` and multiple SQL statements before execution. If execution exposes an additional result set, reject the operation before commit and attempt rollback.
- Q: What does rollback guarantee for a query whose effects are hidden in a stored function? → A: Rollback covers effects that participate in the operation-owned transaction. The consumer must ensure data-changing statements affect only transactional tables in the same connection; effects on nontransactional tables or external systems are outside this guarantee, and the library cannot inspect hidden routine effects.
- Q: If a database value cannot be represented faithfully in Polars or the target column, should the operation fail rather than silently changing the value? → A: Yes. Unsupported or lossy conversions fail; the library does not silently coerce or truncate values.
- Q: How does UPSERT identify records that already exist? → A: The consumer supplies one or more key columns for each import; matching rows update the supplied non-key columns, while unmatched rows are inserted.
- Q: Must the UPSERT key columns identify at most one row in the target table? → A: Yes. The supplied key tuple must be guaranteed unique by a primary-key or unique constraint on the target table.
- Q: Who owns the import transaction? → A: Each import operation controls its own transaction, confirms it only after success, attempts rollback on failure, and leaves the supplied connection open. An existing uncommitted transaction is rejected before import so the operation cannot confirm unrelated work.
- The first release targets the repository's existing MySQL database integration. Polars remains an optional capability; this feature does not expand the project to other database providers.

## User Scenarios & Testing

### User Story 1 - Receive statement results as a Polars DataFrame (Priority: P1)

As an application developer, I can run one supported SQL statement on a MySQL connection that my application already owns and receive its single row result as a Polars DataFrame, including when the statement also changes data transactionally. Stored procedure calls, multiple SQL statements, and additional result sets are unsupported.

**Why this priority**: Returning statement results in the requested format supports both reading data and statements that report rows while changing data.

**Independent Test**: Run a query against a fake connection with known column names and rows, then verify that the returned DataFrame has the same columns, order, values, and row count. Also cover an empty result and a query error without requiring a network connection.

**Acceptance Scenarios**:

1. **Given** a query that returns rows and columns, **When** the consumer requests the result as a DataFrame, **Then** it contains all returned rows and columns in query order with values preserved.
2. **Given** a valid query with no rows, **When** the consumer requests the result, **Then** the returned DataFrame has zero rows and retains the query's result columns.
3. **Given** a query uses bound values, **When** it executes, **Then** values are passed separately to the database and are not interpolated into SQL text.
4. **Given** query execution or result conversion fails, **When** the failure is reported, **Then** the operation attempts to roll back its transaction, the consumer receives a library error with the database error available as its cause, and the supplied connection remains open.
5. **Given** a single statement returns rows and changes data, **When** the consumer executes it through the query-to-DataFrame capability, **Then** the returned DataFrame contains those rows and the operation commits its transaction after successful result materialization.
6. **Given** the supplied connection already has uncommitted work, **When** the consumer requests a query-to-DataFrame operation, **Then** the library rejects it before sending SQL and leaves the existing transaction untouched.
7. **Given** a statement controls transactions, can commit implicitly, is a stored procedure call, or contains multiple SQL statements, **When** the consumer requests its result as a DataFrame, **Then** the library rejects it before starting a transaction or sending SQL.
8. **Given** an executed statement exposes an additional result set, **When** the consumer requests its result as a DataFrame, **Then** the library rejects the operation before commit and attempts rollback.

### User Story 2 - Append DataFrame rows in batches (Priority: P1)

As an application developer, I can explicitly choose `APPEND` to insert every row from a DataFrame into an existing table in batches, so that large imports do not require one statement per complete dataset and a failed import does not leave a partial batch committed.

**Why this priority**: Batch insertion is the basic import capability and gives consumers a clear alternative to updating existing data.

**Independent Test**: Use a fake database to observe multiple batches, explicit transaction start and completion, and rollback after a later batch fails. An opt-in test against a disposable MySQL database verifies persisted rows and rollback behavior.

**Acceptance Scenarios**:

1. **Given** a non-empty DataFrame whose columns map to an existing table, **When** the consumer explicitly selects `APPEND`, **Then** every source row is inserted once, across one or more batches.
2. **Given** a DataFrame that requires multiple batches, **When** all batches succeed, **Then** they are committed as one import operation.
3. **Given** any batch fails, **When** the import ends, **Then** the operation attempts to roll back all rows written by that import and reports the failure.
4. **Given** the consumer omits the mode or supplies an unsupported mode, **When** import is requested, **Then** the library rejects the request before writing rows.

### User Story 3 - Insert and update rows through UPSERT (Priority: P2)

As an application developer, I can explicitly choose `UPSERT`, provide one or more key columns, and import through a staging area, so that matching records are updated and new records are inserted without manually comparing the DataFrame to the table.

**Why this priority**: Consumers can synchronize snapshots or changes with an existing table using one explicit operation.

**Independent Test**: Seed a disposable table with matching and non-matching keys, import a DataFrame through a fake or disposable MySQL database, and verify that matching rows have the supplied non-key values, unmatched rows are inserted, and staging artifacts are not left in the target schema.

**Acceptance Scenarios**:

1. **Given** a DataFrame containing keys that exist in the target, **When** the consumer selects `UPSERT` and supplies those keys, **Then** existing rows receive the DataFrame's supplied non-key values.
2. **Given** a DataFrame containing keys absent from the target, **When** the consumer selects `UPSERT`, **Then** each unmatched row is inserted.
3. **Given** an UPSERT operation encounters a failure while staging or applying rows, **When** the operation ends, **Then** it attempts to roll back target changes, cleans up operation-scoped staging state where possible, and leaves the connection open.
4. **Given** a key column is absent from the DataFrame or target, or source rows contain null or duplicate key combinations, **When** UPSERT is requested, **Then** the library rejects the import before changing the target table.
5. **Given** the DataFrame contains only key columns, **When** an existing row matches, **Then** its non-key values remain unchanged; unmatched keys are inserted subject to the target table's constraints.
6. **Given** the supplied key tuple is not guaranteed unique by a primary-key or unique constraint on the target, **When** UPSERT is requested, **Then** the library rejects the import before changing the target table.

### User Story 4 - Install Polars support only when needed (Priority: P3)

As an application developer, I can install Polars database support separately from the base library, so that applications that do not use this feature do not acquire the Polars dependency.

**Why this priority**: Optional installation preserves the lightweight base library and existing email and database-script use cases.

**Independent Test**: Inspect package metadata and import behavior in separate environments with the base package and the optional Polars/MySQL dependencies. The base package and existing modules must remain usable without Polars.

**Acceptance Scenarios**:

1. **Given** the feature's optional dependencies are installed, **When** the consumer imports and uses the DataFrame database capability, **Then** query and import scenarios are available.
2. **Given** Polars is not installed, **When** the consumer uses the base library or existing database script and email modules, **Then** those features continue to work and no Polars import is required.
3. **Given** the consumer invokes the DataFrame capability without its optional dependencies, **When** the operation is requested, **Then** an actionable library error explains which optional installation is needed.

### Edge Cases

- An empty query result preserves the query's column names and order.
- An empty DataFrame is a no-op and does not start or commit an import transaction.
- A DataFrame column not present in the existing table is rejected before row writes; columns omitted from the DataFrame are left to the target table's defaults and constraints.
- A required target column omitted from the DataFrame and lacking a database default causes the import to fail without committing partial changes.
- A uniqueness or foreign-key constraint rejects an APPEND row; the entire import is rolled back.
- The target table does not support transactions; the library rejects an import before writing rather than claiming atomic rollback it cannot guarantee.
- The supplied connection already has uncommitted work; query and import operations are rejected before SQL writes and do not commit or roll back that work.
- A query statement controls transactions or may commit implicitly; the query-to-DataFrame operation rejects it before starting its transaction or executing SQL.
- A query is a stored procedure call or contains multiple SQL statements; it is rejected before execution. An additional result set is rejected before commit.
- A data-changing query invokes effects on nontransactional tables or external systems; those effects are outside the rollback guarantee, so the consumer must ensure query side effects use transactional tables in the same connection.
- UPSERT key columns are composite; the complete key tuple determines a match.
- The target table does not enforce uniqueness for the supplied UPSERT key tuple; the import is rejected before target changes.
- UPSERT input contains null or repeated key tuples; the import is rejected before target changes to avoid ambiguous matching.
- UPSERT contains only key columns; matching rows are unchanged and unmatched rows are inserted.
- A database conversion, staging, target write, commit, or rollback operation fails; the library surfaces a diagnostic error, preserves the original cause when available, and never closes the supplied connection.
- A query result or imported value cannot be represented without loss; the operation fails instead of silently coercing, truncating, or replacing the value, and any active operation-owned transaction is rolled back.
- The staging operation fails to clean up after a database error; the failure is reported and documented without hiding the original import error.
- Query or import values contain sensitive data; values are not included in default logs or error messages.

## Requirements

### Functional Requirements

- **FR-001**: The library MUST provide a public capability that executes one supported SQL statement using a MySQL connection supplied by the consumer and returns its single complete row result as a Polars DataFrame, whether or not the statement changes data. Stored procedure calls and multiple SQL statements MUST be rejected before execution; an additional result set MUST be rejected before commit.
- **FR-002**: Query results MUST preserve the database result's column names, column order, row count, and values without lossy conversion. If any result value cannot be represented faithfully, the operation MUST fail rather than silently coerce or discard it.
- **FR-003**: Query values MUST be supplied separately from SQL text and MUST NOT be interpolated into SQL by the library.
- **FR-004**: Each non-empty query-to-DataFrame operation MUST start and own its transaction. Before starting a transaction, the library MUST reject statements that explicitly control transactions, whose MySQL behavior may commit implicitly, that call a stored procedure, or that contain multiple SQL statements. If the supplied connection already contains uncommitted work, the library MUST reject the operation before sending SQL and MUST leave that work untouched. On success it MUST commit once after the complete result has been materialized; on execution, conversion, additional-result-set, or commit failure it MUST attempt rollback. Rollback covers effects that participate in the operation-owned transaction; the consumer MUST ensure data-changing statements affect only transactional tables in the same connection. Effects on nontransactional tables or external systems are outside this guarantee. The library MUST NOT close the supplied connection.
- **FR-005**: The library MUST provide a public import capability for a Polars DataFrame and an existing MySQL table. It MUST NOT create or alter the target table.
- **FR-006**: Every import request MUST explicitly select `APPEND` or `UPSERT`; omission or an unsupported mode MUST be rejected before target writes.
- **FR-007**: `APPEND` MUST insert all DataFrame rows using bounded batches within one explicit transaction. A successful non-empty import MUST commit once after all batches succeed.
- **FR-008**: If an APPEND batch fails, the library MUST attempt to roll back all changes from that import and MUST report the failure without closing the supplied connection.
- **FR-009**: `UPSERT` MUST use an operation-scoped staging area before applying rows to the target table. The staging lifecycle MUST NOT leave persistent staging objects or rows in the target schema after a successful operation.
- **FR-010**: Each UPSERT request MUST include one or more key column names that exist in both the DataFrame and the target table. The target MUST enforce that the complete supplied key tuple identifies at most one row through a primary-key or unique constraint. Matching rows MUST receive the DataFrame's supplied non-key values; non-matching rows MUST be inserted.
- **FR-011**: UPSERT MUST reject absent key columns, null key values, or duplicate key tuples in the source before modifying the target table. Composite keys MUST be treated as one complete key tuple.
- **FR-012**: A DataFrame column that does not exist in the target table MUST be rejected before row writes. Target columns omitted from the DataFrame MUST remain governed by target defaults and constraints.
- **FR-013**: Every non-empty import MUST own its transaction. If the supplied connection already contains uncommitted work, the library MUST reject the import before writing and MUST leave that work untouched. On success it MUST commit once; on failure it MUST attempt rollback. It MUST NOT close the supplied connection.
- **FR-014**: The library MUST reject import into a target table that cannot provide transactional rollback, before writing rows.
- **FR-015**: An empty DataFrame MUST be a no-op and MUST NOT open, commit, or roll back an import transaction.
- **FR-016**: Database and conversion failures MUST be reported through a library error with available operation context and the original cause when one exists. Default logs and error messages MUST NOT include bound values or row contents.
- **FR-017**: Polars support MUST be optional and installable without adding Polars to the base installation. Existing base, email, and MySQL SQL-script capabilities MUST remain usable without Polars.
- **FR-018**: If optional dependencies required by the requested DataFrame operation are missing, the library MUST provide an actionable error identifying the required optional installation.
- **FR-019**: Public documentation MUST explain installation, query-to-DataFrame behavior, explicit import modes, batch behavior, UPSERT keys, transaction ownership, supported target requirements, errors, and limitations.
- **FR-020**: Unit tests MUST run without network access and cover query conversion, lossless-conversion failures, APPEND batching, UPSERT key matching, invalid input, transaction behavior, errors, sensitive-value redaction in logs and errors, and connection preservation. Optional integration tests MUST use only an explicitly configured disposable MySQL database and MUST NOT target production or corporate databases.
- **FR-021**: The feature MUST preserve the project's Python `>=3.11`, `src` layout, optional-integration boundaries, typed public API, and Semantic Versioning policy.
- **FR-022**: Imported values MUST be stored without silent truncation or lossy coercion. If a value cannot be represented faithfully by its target column, the import MUST fail and MUST NOT commit any rows from that operation.

### Key Entities

- **Query result**: Column names, their order, and rows returned by a SQL query, represented as a Polars DataFrame.
- **Import request**: A DataFrame, an existing target table, an explicit mode, and—when using UPSERT—the supplied key columns, which identify at most one target row.
- **Import mode**: The explicit choice between inserting all rows (`APPEND`) and inserting or updating rows by key (`UPSERT`).
- **Staging data**: An operation-scoped representation of incoming UPSERT rows used to reconcile them with the target.
- **Import transaction**: The transaction owned by one non-empty import, committed after success or rolled back after failure.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For any faithfully representable query result with N rows and C columns, the returned DataFrame contains exactly N rows and C columns with the same names, order, and values, including when N is zero. An unrepresentable value causes failure rather than silent data loss.
- **SC-002**: For an APPEND import of N valid rows, exactly N rows are added when the operation succeeds; if any batch fails, zero rows from that import are committed.
- **SC-003**: For an UPSERT import with M source rows and valid unique keys, every matching target key reflects the supplied non-key values and every previously unmatched key appears once after success.
- **SC-004**: For every rejected or failed query or import, the library attempts to roll back changes that participate in its operation-owned transaction; effects on nontransactional tables or external systems are outside this guarantee. The consumer's pre-existing transaction is left untouched, and the supplied connection remains open. Statements with transaction-control, implicit-commit, stored-procedure-call, or multiple-statement behavior are rejected before execution. A successful non-empty query commits once after result materialization.
- **SC-005**: A valid query returning zero rows produces a zero-row DataFrame and follows the query transaction rules; an empty DataFrame import is a no-op and does not open or commit an import transaction.
- **SC-006**: The base package and existing modules remain usable in an environment without Polars, while consumers who install the optional capability can complete all query, APPEND, and UPSERT acceptance scenarios.
- **SC-007**: Every functional requirement has at least one deterministic offline acceptance scenario; live database verification, when configured, uses a disposable MySQL environment.
- **SC-008**: No query result or successful import silently truncates, replaces, or coerces a value that cannot be represented faithfully.

## Assumptions

- The first release supports the repository's existing MySQL integration only; additional database providers are outside this feature.
- This capability accepts eager Polars DataFrames. Lazy query plans and Polars LazyFrames are outside scope.
- Consumers supply a live MySQL connection and an existing target table; the library does not create the connection or target table.
- Each non-empty query-to-DataFrame operation owns its transaction and rejects a supplied connection that already has uncommitted work, preserving work performed by the calling application.
- The query-to-DataFrame capability accepts one supported statement that returns a single result set. Explicit transaction controls, MySQL statements that may commit implicitly, stored procedure calls, and multiple SQL statements are rejected. The consumer ensures that data-changing statements affect only transactional tables in the same connection; nontransactional and external side effects are outside the rollback guarantee.
- DataFrame columns map by name to existing target columns. A subset may be supplied when omitted target columns have defaults or otherwise satisfy database constraints.
- UPSERT key columns are chosen by the consumer for each call and must identify at most one target row through a primary-key or unique constraint. All supplied DataFrame columns other than those keys are eligible for update; if the DataFrame contains only key columns, an existing match is unchanged.
- Imports require a target table that supports transactions. This requirement enables the promised rollback behavior.
- Each import owns its transaction and will reject a connection that already has uncommitted work, preserving work performed by the calling application.
- An empty DataFrame is treated as a no-op. Query results are materialized completely in memory; streaming and chunked query-result APIs are outside this feature.
- Polars and database dependencies remain optional; consumers install the Polars capability alongside the existing MySQL extra when both are needed.
- No implementation is authorized by this specification alone; source changes follow an approved plan and task list.
