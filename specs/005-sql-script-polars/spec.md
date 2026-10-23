# Feature Specification: SQL Script Results as Polars DataFrames

**Feature Branch**: `005-sql-script-polars`<br>
**Created**: 2026-10-23<br>
**Status**: Draft<br>
**Input**: User request to convert `SqlScriptResult` values to Polars DataFrames and add `SqlScriptExecutor` methods that return those DataFrames directly.

## Clarifications

### Session 2026-10-23

- Q: When Polars conversion fails in a method called with `commit=True`, should SQL changes be committed or rolled back? → A: Convert before committing; commit only after successful conversion, and attempt rollback if conversion fails.
- Q: What does faithful conversion mean for representative SQL scalar values? → A: Preserve both Python type and value for tested values; compare byte-like values by byte content, preserve NaN as NaN, and reject unsupported or out-of-range values instead of coercing them. This follows the existing SQL-to-Polars lossless comparison behavior.
- Q: Which Python temporal values represent SQL time results? → A: Test both `datetime.time` and `datetime.timedelta`; Connector/Python returns MySQL `TIME` values as durations, which can be negative or exceed 24 hours.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convert a script result to a DataFrame (Priority: P1)

As a Python developer who already has a `SqlScriptResult`, I can convert its rows into a Polars DataFrame so I can continue processing the result with Polars.

**Why this priority**: It lets consumers reuse script execution results without manually rebuilding tabular data.

**Independent Test**: Convert a result with known columns and rows and verify that the DataFrame contains the same columns, order, values, and row count. Convert an empty result and verify its documented empty shape.

**Acceptance Scenarios**:

1. **Given** a result with rows, **When** a developer converts it, **Then** the DataFrame contains the same rows and column order as the result.
2. **Given** a result with column metadata but no rows, **When** a developer converts it, **Then** the DataFrame has zero rows and retains those columns in order.
3. **Given** an empty result with neither rows nor column metadata, **When** a developer converts it, **Then** the DataFrame has zero rows and zero columns.
4. **Given** a result value that cannot be represented faithfully, **When** conversion is attempted, **Then** the conversion fails instead of silently changing or dropping the value.
5. **Given** a non-empty result without separate column metadata, **When** a developer converts it, **Then** column order follows the keys of its first row.
6. **Given** conversion fails for a result containing sensitive row data, **When** the error is reported, **Then** the message and default logs do not expose the row contents.
7. **Given** rows contain representative SQL scalar values (`None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes), **When** conversion succeeds, **Then** values retain their Python type and value; byte-like values are compared by byte content and NaN remains NaN. Unsupported or out-of-range values fail without coercion.

### User Story 2 - Execute SQL and receive a DataFrame (Priority: P1)

As a Python developer, I can run a SQL string or SQL file through the existing script executor and receive its final result set as a Polars DataFrame, so I do not need to convert the result manually.

**Why this priority**: It provides a direct path from the executor's existing query results to the format used by the project's Polars database features.

**Independent Test**: Execute a multi-statement script with a final result set using a fake connection, then verify the returned DataFrame and that existing SQL binding, error, and connection-lifecycle behavior is preserved alongside the clarified commit timing.

**Acceptance Scenarios**:

1. **Given** a SQL string whose last result-producing statement returns rows, **When** the developer selects the DataFrame-returning execution method, **Then** the method returns those rows and columns as a DataFrame.
2. **Given** a SQL file with an encoding and bound values, **When** the developer selects the file-based DataFrame method, **Then** it follows the same file-reading and parameter-binding behavior as the existing file method.
3. **Given** a script with no result-producing statement, **When** it is executed through a DataFrame-returning method, **Then** the method returns an empty DataFrame.
4. **Given** `commit=True` and both SQL execution and DataFrame conversion succeed, **When** a DataFrame-returning method completes, **Then** it commits once after conversion.
5. **Given** `commit=True` and DataFrame conversion fails, **When** a DataFrame-returning method completes with an error, **Then** it does not commit and attempts to roll back.
6. **Given** `commit=False`, **When** a DataFrame-returning method completes, **Then** it does not commit or roll back automatically.
7. **Given** SQL script execution fails, **When** a DataFrame-returning method is called, **Then** the existing script execution error and diagnostic context are preserved.
8. **Given** `commit=True` and SQL execution, result fetching, or cursor closing fails, **When** a DataFrame-returning method reports the error, **Then** it preserves the existing error and transaction behavior without committing or attempting an automatic rollback.
9. **Given** conversion fails with `commit=True` and the rollback attempt also fails, **When** the method reports the conversion error, **Then** the conversion error remains primary and the rollback failure is available as cleanup context.

### User Story 3 - Keep Polars optional (Priority: P2)

As a developer who does not use Polars, I can continue importing and using the existing database APIs without installing Polars.

**Why this priority**: The new convenience must fit the library's optional integration model and not burden consumers who do not need it.

**Independent Test**: In an environment without Polars, import and use the existing non-Polars database APIs, then call a new DataFrame capability and verify it reports an actionable optional-installation error.

**Acceptance Scenarios**:

1. **Given** the base package is installed without Polars, **When** a consumer imports the database package and uses the existing script-result methods, **Then** those APIs remain available and behave as before.
2. **Given** the Polars dependency is missing, **When** a consumer calls a new conversion or DataFrame-returning method, **Then** the library explains which optional installation is required.
3. **Given** a consumer consults the database guide, **When** they choose a DataFrame-returning operation, **Then** the guide explains installation, returned data, and how it relates to the existing script-result methods, including how to obtain execution totals.

### Edge Cases

- The final result-producing statement returns zero rows; its column names and order remain available to DataFrame-returning methods.
- A script has later statements that do not return rows; the DataFrame still represents the last statement that produced a result set, matching `SqlScriptResult` semantics.
- An empty or comment-only script remains an executor no-op; it returns a zero-by-zero DataFrame without inspecting or committing the connection transaction.
- An empty `SqlScriptResult` created without column metadata converts to a zero-row, zero-column DataFrame.
- Result sets with duplicate column names cannot be represented faithfully by dictionary-backed rows; DataFrame conversion fails with a sanitized error, and consumers must use unique SQL aliases.
- Result rows contain values or column shapes that cannot be faithfully represented; conversion reports an error instead of silently discarding or coercing them.
- Representative scalar round-trip coverage includes `None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes. Conversion requires equal values and Python types, except byte-like values are compared by byte content and NaN by NaN; unsupported or out-of-range values fail.
- Conversion errors must not expose row contents in diagnostic messages or default logs.
- DataFrame conversion fails with `commit=True`; no commit is issued and rollback is attempted, subject to MySQL's existing implicit-commit limitations.
- Polars is unavailable while existing non-Polars script execution is still used.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST provide a public function that converts a `SqlScriptResult` into an eager Polars DataFrame.
- **FR-002**: Conversion MUST preserve the rows, column names, and column order of the result's final result set. Values that cannot be represented faithfully MUST cause a clear conversion failure rather than silent loss or coercion.
- **FR-003**: `SqlScriptResult` MUST retain the column names and order of its final result-producing statement, including when that statement returns zero rows, so conversion can preserve an empty result's schema. Results with no result-producing statement MUST have no result columns.
- **FR-004**: When rows are present, conversion MUST preserve their existing row ordering and use the result's column order. If no separate column metadata is available, the keys of the first row MUST define column names and order. A result with no rows and no column metadata MUST convert to a DataFrame with zero rows and zero columns.
- **FR-005**: `SqlScriptExecutor` MUST provide a DataFrame-returning counterpart for execution of a SQL string and a DataFrame-returning counterpart for execution of a SQL file. Each MUST accept the same relevant parameters as its existing counterpart, including bound values, `commit`, and file encoding where applicable.
- **FR-006**: The DataFrame-returning methods MUST return only the rows and columns from the last result-producing statement. Execution totals such as `statements_executed` and `affected_rows` are not columns in the returned DataFrame; consumers needing those totals can continue using the existing methods.
- **FR-007**: The existing `execute` and `execute_file` methods MUST continue returning `SqlScriptResult` and retain their existing SQL execution, parameter binding, error, connection, cursor, and transaction behavior.
- **FR-008**: The DataFrame-returning methods MUST preserve their corresponding existing methods' parameter binding, connection ownership, and transaction ownership. With `commit=True`, they MUST convert the result before committing, commit once only after successful conversion, and attempt rollback if conversion fails. If that rollback also fails, the conversion error MUST remain primary and the rollback error MUST be retained as cleanup context. With `commit=False`, they MUST NOT commit or roll back automatically. SQL execution, fetch, and cursor-close failures MUST retain existing executor error and transaction behavior, with no added automatic rollback. Rollback is subject to the existing MySQL limitations for implicit commits and non-transactional effects. Conversion MUST NOT close or replace the consumer-owned connection.
- **FR-009**: Polars MUST remain optional. Importing and using existing APIs that do not require Polars MUST continue to work without Polars installed.
- **FR-010**: Calling a new Polars capability without its optional dependency MUST fail with an actionable library error that identifies the required installation.
- **FR-011**: Public APIs MUST have type annotations and docstrings, be exported through the documented database package API, and be covered by consumer documentation.
- **FR-012**: Deterministic offline tests MUST cover populated and empty conversion, column order, result selection, representative SQL scalar round trips, unsupported/out-of-range values, missing optional dependencies, preservation of existing executor behavior, transaction behavior for conversion and SQL/fetch/cursor-close failures, rollback cleanup failures, and row-content redaction from errors and default logs.
- **FR-013**: Conversion errors and default logs MUST NOT include result row contents.

### Key Entities

- **SqlScriptResult**: The structured outcome of script execution, including statement and affected-row totals, rows from the last result-producing statement, and its column names when available.
- **Polars DataFrame**: A tabular representation of that result set, preserving its rows and columns for subsequent data processing.
- **DataFrame-returning script execution**: An alternate way to run an existing SQL string or file operation and receive the result set as a Polars DataFrame.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a result containing N rows and C columns, conversion produces exactly N rows and C columns, with matching names, order, and faithfully represented values.
- **SC-002**: A result with C known columns and zero rows produces a DataFrame with zero rows and C columns; a result with no rows and no known columns produces a DataFrame with zero rows and zero columns.
- **SC-003**: For scripts with multiple statements, the returned DataFrame contains exactly the rows and columns from the last result-producing statement, regardless of later statements that produce no rows.
- **SC-004**: Existing script execution methods continue returning `SqlScriptResult`, and their parameter binding, error reporting, connection lifecycle, and transaction outcomes remain unchanged.
- **SC-005**: Consumers without Polars can import and use existing non-Polars database APIs; consumers who call a Polars capability without the dependency receive an actionable installation message.
- **SC-006**: Every conversion and execution scenario in the acceptance criteria is verifiable with deterministic tests that do not require a live database service.
- **SC-007**: A DataFrame-returning method with `commit=True` commits only after successful conversion and attempts rollback if conversion fails; a rollback failure remains cleanup context, and SQL/fetch/cursor-close failures add no automatic rollback. With `commit=False`, it does not commit or roll back automatically.
- **SC-008**: Conversion errors and default logs do not reveal result row contents.
- **SC-009**: Deterministic converter tests verify representative values for `None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes; values that cannot round-trip without coercion fail with a sanitized conversion error.

## Assumptions

- The DataFrame-returning counterparts cover both existing methods: SQL string execution and SQL file execution.
- The converter represents only the result-set rows; statement counts and affected-row totals remain available through `SqlScriptResult` and the existing methods. Consumers who need those totals use `execute()` or `execute_file()` and convert the returned result separately.
- The result schema refers to the last statement that produces a result set, even if that set contains zero rows. A script with no result-producing statement has no result schema.
- For a manually constructed result with rows but no separate column metadata, dictionary key order in the first row defines the DataFrame's columns. Inconsistent row shapes or unrepresentable values are conversion errors.
- DataFrame conversion uses the project's existing optional Polars installation. Existing MySQL support remains required for script execution, and this feature does not add another database provider.
- New methods use the existing `commit` option and connection ownership rules, but defer a requested commit until result conversion succeeds. A conversion failure with `commit=True` causes a rollback attempt before any commit; MySQL implicit commits and non-transactional effects retain their existing limitations. The existing `execute` and `execute_file` methods remain unchanged.
- The API addition is additive; any public API compatibility impact will be reviewed under the project's Semantic Versioning policy before release.
