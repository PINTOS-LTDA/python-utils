# Feature Specification: MySQL SQL Script Execution

**Feature Branch**: `003-sql-script-execution`<br>
**Created**: 2026-10-21<br>
**Status**: Draft
**Input**: User request to add a reusable, typed database module that executes parameterized multi-statement SQL scripts on an existing MySQL connection.

## Clarifications

### Session 2026-10-21

- Q: Se a conexão já tiver mudanças não confirmadas antes de `execute(..., commit=True)`, o executor deve confirmá-las junto com o script? → A: Não. Se a conexão reportar uma transação ativa antes da execução, o executor deve rejeitar a chamada antes de enviar qualquer instrução SQL, sem confirmar nem reverter a transação; o consumidor continua responsável por encerrá-la.
- Q: O executor deve aceitar comandos explícitos de controle transacional dentro do script, como `COMMIT`, `ROLLBACK` e `START TRANSACTION`? → A: Não. O executor deve rejeitar o script antes de executar qualquer instrução se ele contiver comandos explícitos de controle transacional; esse controle permanece com o consumidor e com o parâmetro `commit`.
- Q: Como o preflight reconhece alterações transacionais e comentários executáveis do MySQL? → A: Reconhece os comandos e formas de `SET` descritos em FR-026, tratando qualificadores e atribuições de `autocommit` como controle transacional. Rejeita comentários executáveis `/*!...*/` antes de qualquer SQL, pois o servidor executa o conteúdo deles. Comentários comuns, strings e identificadores citados permanecem fora da detecção.

## User Scenarios & Testing

### User Story 1 - Execute a script in one MySQL session (Priority: P1)

As an application developer, I can execute a SQL string or `.sql` file containing multiple statements on a connection that my application already owns, so that commands such as `USE` and temporary-table creation can be followed by queries in the same MySQL session.

**Why this priority**: Sequential execution on one session is the core capability and is needed for the supplied reporting-script use case.

**Independent Test**: Unit tests use a fake connection and cursor to observe statement order, connection identity, cursor cleanup, and returned rows without network access. An optional integration test against a disposable MySQL instance verifies a temporary table is visible to a later statement on that connection.

**Acceptance Scenarios**:

1. **Given** a script with several supported statements, **When** the consumer executes it, **Then** each non-empty statement runs in source order on the same connection.
2. **Given** a script that creates and then queries a temporary table, **When** both statements run, **Then** the later statement observes the table created earlier in that session.
3. **Given** a `.sql` file with a selected text encoding, **When** the consumer executes the file, **Then** its decoded contents follow the same execution behavior as a string script.
4. **Given** an empty or ordinary-comment-only script, **When** the consumer executes it, **Then** the result reports zero executed statements and no commit is issued.

### User Story 2 - Bind named values safely (Priority: P1)

As an application developer, I can use named markers in a SQL script and pass Python values separately, so that values are bound by the database driver and are not interpolated into SQL text.

**Why this priority**: Safe parameter binding is required for real scripts and protects consumer code from SQL injection through values.

**Independent Test**: Unit tests inspect the SQL operation and parameter mapping sent to a mocked driver, covering repeated and missing parameters and marker-like text in SQL literals, ordinary comments, and quoted identifiers.

**Acceptance Scenarios**:

1. **Given** a script with valid `:name` markers and matching values, **When** it is executed, **Then** markers are translated to the driver's named binding format and values are passed separately.
2. **Given** the same named marker occurs more than once, **When** the statement executes, **Then** every occurrence receives the same separately bound value.
3. **Given** a required marker has no supplied value anywhere in the script, **When** execution is requested, **Then** a typed error identifies the missing name without executing any statement.
4. **Given** text resembling a marker occurs within a string, ordinary comment, or quoted identifier, **When** the script is processed, **Then** that text remains unchanged and is not treated as a parameter. A MySQL executable comment is rejected as unsupported input.
5. **Given** an application needs to vary a table or column name, **When** it tries to use a value marker for that identifier, **Then** the API does not treat the bound value as an identifier; identifiers must be fixed or safely selected by the caller.

### User Story 3 - Inspect execution results and errors (Priority: P2)

As an application developer, I can inspect a structured result or diagnose which statement failed, while retaining control of the external connection and its transaction.

**Why this priority**: Reliable diagnostics and explicit ownership boundaries make the executor safe to reuse in applications with existing database workflows.

**Independent Test**: Mocked tests verify result counts and rows, `SqlScriptError` context and exception chaining, commit behavior, no automatic rollback, and that neither a successful nor failed execution closes the supplied connection. When a disposable MySQL environment is configured, opt-in integration tests also verify the driver's transaction behavior using DML.

**Acceptance Scenarios**:

1. **Given** a script where one or more statements return rows, **When** execution completes, **Then** the result contains rows from only the last statement that returned a result set.
2. **Given** successful DML statements whose driver reports affected rows, **When** execution completes, **Then** the result contains their accumulated affected-row count.
3. **Given** `commit=False`, **When** all statements succeed, **Then** the executor does not call `commit()`.
4. **Given** `commit=True` and no transaction is active before a non-empty script starts, **When** all statements succeed, **Then** the executor calls `commit()` once after the final statement.
5. **Given** a statement fails, **When** execution stops, **Then** a `SqlScriptError` exposes the one-based statement index and SQL, chains the original exception, and does not cause an automatic rollback or close the caller's connection.
6. **Given** `commit=True` and the supplied connection already reports an active transaction before a non-empty script starts, **When** execution is requested, **Then** the executor raises `SqlScriptError` before sending any statement and leaves that transaction untouched.
7. **Given** a script contains an explicit transaction-control statement, a system-variable assignment to `autocommit`, or an executable MySQL comment, **When** execution is requested, **Then** the executor rejects the entire script before sending any statement, without committing or rolling back the connection.

### User Story 4 - Install and use optional MySQL support (Priority: P3)

As an application developer, I can install MySQL script support only when required and consult examples that explain its transaction and script limitations.

**Why this priority**: Optional dependencies keep the base package and unrelated modules lightweight while making the new integration usable and discoverable.

**Independent Test**: Package metadata and consumer documentation are reviewed to confirm the `mysql` extra, installation instructions, typed API examples, transaction policy, and limitations. The base package and existing email module remain importable without MySQL optional dependencies installed.

**Acceptance Scenarios**:

1. **Given** the package is installed with the `mysql` extra, **When** the consumer imports the database API, **Then** the MySQL Connector/Python and SQL statement-splitting support are available.
2. **Given** the package is installed without the `mysql` extra, **When** the consumer uses the base package or email module, **Then** it does not require MySQL dependencies.
3. **Given** the consumer reads the database documentation, **When** they prepare a script with stored routines, triggers, `DELIMITER`, or executable MySQL comments, **Then** the documented v1 limitation is clear before execution.

### Edge Cases

- A semicolon inside single-quoted or double-quoted string content, a backtick-quoted identifier, or an ordinary line/block comment must not split the script. MySQL executable comments are rejected before statement execution.
- A statement fragment containing only whitespace or ordinary comments must be skipped; MySQL executable comments are rejected during preflight.
- A missing parameter in a later statement must be detected before the first statement is sent, preventing partial execution caused by parameter validation.
- A SQL execution error in the middle of a script stops subsequent statements; the error identifies the failed statement.
- A driver reports no affected-row count (for example, a negative or unavailable count); it contributes zero to `affected_rows`.
- Several statements return rows; only the rows from the last result-producing statement are retained, while earlier results are consumed before the next statement.
- The last result set is very large; the API loads its rows in memory, and documentation warns that it is not intended for unbounded result sets.
- Cursor creation, file reading/decoding, or the final commit fails; the failure is surfaced as a library error with available context and its original cause chained.
- The supplied connection already has a transaction open; a non-empty script requested with `commit=True` is rejected before any statement is sent, and the executor neither commits nor rolls back the existing transaction. The consumer remains responsible for ending that transaction before retrying.
- A script contains `START TRANSACTION`, `BEGIN [WORK]`, `COMMIT [WORK]`, `ROLLBACK [WORK]`, `SAVEPOINT`, `RELEASE SAVEPOINT`, or `SET [GLOBAL | SESSION] TRANSACTION`; the entire script is rejected before any statement is sent.
- A `SET` statement assigns the server system variable `autocommit`; reject it regardless of value or scope, including unqualified, `GLOBAL`, `SESSION`, `LOCAL`, `PERSIST`, `PERSIST_ONLY`, and corresponding `@@` forms, using `=` or `:=`. Inspect every target in a multi-assignment statement. A single-`@` user variable such as `@autocommit` is not the server system variable.
- Ordinary comment, string, and quoted-identifier text does not trigger transaction-control rejection. A MySQL executable comment such as `/*!80000 SET autocommit=0 */`, when present as an actual SQL comment outside strings and quoted identifiers, is rejected in v1 before any SQL is sent. The same character sequence inside a string or quoted identifier is preserved and does not trigger rejection.
- A script contains DDL or temporary-table DDL; MySQL implicit commit and rollback rules may prevent full atomicity.
- A script contains a stored procedure, trigger body, or client-side `DELIMITER` directive; v1 does not promise to parse or execute it as a compound statement.
- SQL values include `None`, strings, integers, floats, decimals, dates, or datetimes; their types are passed through driver binding rather than string interpolation.
- Extra keys supplied in `params` are ignored; only names referenced by actual markers are passed to a statement.

## Requirements

### Functional Requirements

- **FR-001**: The library MUST provide a public `SqlScriptExecutor` constructed with an existing MySQL Connector/Python connection supplied by the consumer.
- **FR-002**: The executor MUST NOT create or close the supplied connection, change its autocommit configuration, or open a replacement connection.
- **FR-003**: The public `execute(script: str, params: Mapping[str, Any] | None = None, commit: bool = False) -> SqlScriptResult` method MUST execute a script supplied as a string.
- **FR-004**: The public `execute_file(file_path: str | Path, params: Mapping[str, Any] | None = None, commit: bool = False, encoding: str = "utf-8") -> SqlScriptResult` method MUST read and execute a SQL file.
- **FR-005**: Scripts MUST support sequential execution of conventional MySQL statements including `USE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TEMPORARY TABLE`, and `DROP TEMPORARY TABLE`.
- **FR-006**: Statement separation MUST preserve source order and MUST NOT split on semicolons inside string literals, quoted identifiers, or ordinary comments. Empty and ordinary-comment-only fragments MUST be ignored; actual MySQL executable comments outside strings and quoted identifiers MUST be rejected during preflight. The implementation MUST NOT split with a plain `script.split(";")` operation.
- **FR-007**: Scripts MUST support named markers with names matching `[A-Za-z_][A-Za-z0-9_]*`, including multiple occurrences of the same name.
- **FR-008**: Marker recognition MUST preserve marker-like text in string literals, ordinary comments, and quoted identifiers. Actual MySQL executable comments outside strings and quoted identifiers MUST be rejected in preflight. Values MUST be bound through the driver API and MUST NOT be interpolated into SQL text or used in place of identifiers.
- **FR-009**: The executor MUST validate that every referenced marker has a corresponding supplied value before executing any statement. Unreferenced supplied values MUST be ignored.
- **FR-010**: Bound values MUST preserve compatible Python types, including `str`, `int`, `float`, `Decimal`, `date`, `datetime`, and `None`, for conversion by MySQL Connector/Python.
- **FR-011**: Each statement MUST execute using the same connection/session. Cursors used by the executor MUST be closed after use, and result rows needed for the API result MUST be consumed before a later statement runs.
- **FR-012**: The public `SqlScriptResult` MUST expose `statements_executed: int`, `rows: list[dict[str, Any]]`, and `affected_rows: int`. Its `rows` MUST represent only the last result set produced, or an empty list if no statement produces rows.
- **FR-013**: `statements_executed` MUST count successful statements only. `affected_rows` MUST sum non-negative row counts reported for DML statements; unavailable or negative counts MUST contribute zero.
- **FR-014**: With `commit=False`, the executor MUST NOT automatically call `connection.commit()`. With `commit=True` and a non-empty script, the executor MUST reject the call before executing any statement if the supplied connection already reports an active transaction; it MUST NOT commit or roll back that transaction. Otherwise, it MUST call `connection.commit()` once only after every statement succeeds. An empty or ordinary-comment-only script remains a no-op and MUST NOT commit; executable MySQL comments are rejected by FR-026.
- **FR-015**: On failure, the executor MUST stop immediately and MUST NOT issue an automatic rollback. Transaction rollback remains the consumer's responsibility. Failures MUST NOT close the supplied connection.
- **FR-016**: The public `SqlScriptError` MUST provide a diagnostic message, the one-based index and SQL text for a failed statement when available, and the original exception through its public diagnostic context and chained cause when an underlying exception exists. Failures without statement context, including rejection because a transaction is already active, MUST still be surfaced as a library exception.
- **FR-017**: Error messages and default logs MUST NOT contain bound parameter values. The error context MAY expose the SQL statement, as required for diagnosis.
- **FR-018**: The module MUST use standard-library `logging` without configuring the consuming application's logging system. DEBUG-level records SHOULD report execution start, statement count, current one-based index, per-statement duration, completion, and errors without logging parameter values.
- **FR-019**: MySQL support MUST be installable through the optional `mysql` extra, including MySQL Connector/Python. Any SQL statement-splitting dependency MUST remain optional with the database feature. The base package and existing email module MUST remain usable without these dependencies.
- **FR-020**: The package MUST expose `SqlScriptExecutor`, `SqlScriptResult`, and `SqlScriptError` from the database module's public package API, with type hints and API docstrings.
- **FR-021**: Consumer documentation MUST cover installation, consumer-owned MySQL connection setup, string and file execution, named binding, errors, result semantics, transaction ownership, temporary tables, security, and known limitations, including transaction-control rejection and executable-comment rejection.
- **FR-022**: The v1 parser MUST NOT claim support for stored procedures, triggers, client-side `DELIMITER` directives, or MySQL executable comments.
- **FR-023**: Unit tests MUST run without network access and MUST cover statement splitting, binding, results, errors, transaction calls, cursor/connection lifecycle, UTF-8 file content, and absence of sensitive values in default logs. Optional integration tests MUST use a disposable, explicitly configured MySQL environment and MUST NOT target a corporate production database. When such an environment is configured, integration tests MUST verify temporary-table session behavior and real-driver transaction behavior: active-transaction rejection before SQL while leaving the caller transaction active, successful `commit=True` after DML, and no automatic commit with `commit=False`.
- **FR-024**: The feature MUST preserve the project's Python `>=3.11`, `src` layout, Hatchling build, Ruff/mypy/pytest conventions, and Semantic Versioning policy; adding the public module is an additive minor-version-compatible change before release.
- **FR-025**: SQL containing DDL MUST be documented as potentially causing implicit commits and breaking script-level atomicity, including scripts that use temporary tables.
- **FR-026**: The executor MUST reject the entire script during preflight, before sending any SQL, if it contains `START TRANSACTION`, `BEGIN [WORK]`, `COMMIT [WORK]`, `ROLLBACK [WORK]`, `SAVEPOINT`, `RELEASE SAVEPOINT`, or `SET [GLOBAL | SESSION] TRANSACTION`. It MUST also reject any `SET` assignment whose target is the server system variable `autocommit`, regardless of assigned value or scope. This includes unqualified, `GLOBAL`, `SESSION`, `LOCAL`, `PERSIST`, `PERSIST_ONLY`, and corresponding `@@` forms, with either `=` or `:=`; every target in multi-assignment statements MUST be inspected. A single-`@` user variable is not a system-variable assignment. Detection MUST use lexical tokens, not substring matching. Words in strings, ordinary comments, and quoted identifiers MUST NOT trigger transaction-command rejection. Actual MySQL executable comments `/*!...*/` outside strings and quoted identifiers MUST be rejected during preflight, because the server executes their contents; the same sequence inside a string or quoted identifier MUST be preserved. Rejection MUST NOT commit or roll back the connection, which MUST remain open.

### Key Entities

- **SQL script**: A string or decoded file containing one or more conventional SQL statements, optional named value markers, comments, and literals.
- **Statement**: A non-empty SQL unit identified in source order and sent individually to the same connection.
- **Execution result**: The successful-statement count, aggregate reported DML affected-row count, and rows from the last result-producing statement.
- **Supplied connection**: A MySQL connection whose creation, broader session lifecycle, and transaction ownership remain with the consuming application.
- **Execution error**: A library exception describing the failed phase and, for a failed SQL statement, its one-based position and source SQL while chaining the original cause.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For a script containing multiple supported statements, the observable outcome is equivalent to executing each non-empty statement in source order within one session; a temporary table created by an earlier statement is available to a later statement.
- **SC-002**: For every supported named marker, changing the bound value changes only the value supplied to SQL evaluation; repeated markers use the same supplied value, and marker-like text in literals, ordinary comments, or quoted identifiers remains unchanged. MySQL executable comments are rejected.
- **SC-003**: When a script has more than one result-producing statement, the returned `rows` exactly represent the final result-producing statement; statement and affected-row totals reflect only successful execution and non-negative DML counts.
- **SC-004**: With `commit=False`, no automatic commit occurs. With `commit=True`, a pre-existing active transaction is rejected before SQL execution; otherwise, a non-empty successful script commits once. Scripts containing explicit transaction-control statements, `autocommit` assignments, or executable MySQL comments are rejected before any SQL executes. The consumer's connection remains open, and no rollback is issued automatically after a failure or rejection.
- **SC-005**: Every execution failure is reported through `SqlScriptError`; SQL-statement failures identify the one-based statement position and source SQL, and the original cause remains inspectable.
- **SC-006**: All required success and failure cases have offline unit coverage. When live verification is configured, integration tests use a disposable MySQL database to verify temporary-table session behavior and real-driver transaction behavior; they never target production or corporate databases.
- **SC-007**: Consumers can install the base library without MySQL support and install the optional database support separately without changing the existing email module's behavior.
- **SC-008**: Consumer documentation makes transaction ownership, DDL limitations, result-memory behavior, safe binding, installation, and unsupported compound scripts and executable comments clear before a consumer runs a script.
- **SC-009**: Existing public email behavior and its base installation requirements remain unchanged when database support is added.

## Assumptions

- The first implementation targets MySQL through MySQL Connector/Python; generic database support and additional providers are future work and do not justify a provider/factory abstraction in v1.
- The public `:name` markers are translated to a binding format accepted by the selected MySQL driver. No parameter value is interpolated by the library.
- Missing marker names are validated across the full script before any statement is executed. Extra mapping entries are ignored.
- An empty or ordinary-comment-only script is a no-op and does not commit, even when `commit=True`; executable MySQL comments are rejected.
- The consuming application owns the connection and transaction lifecycle. The executor never rolls back automatically; after a failure, the caller decides whether and when to roll back. For a non-empty script with `commit=True`, execution is rejected before SQL if the connection reports a transaction already active; otherwise, the executor commits once after all statements succeed. Explicit transaction-control statements and executable MySQL comments are rejected before execution, and empty/ordinary-comment-only scripts remain no-ops even when `commit=True`.
- DDL can cause implicit commits under MySQL rules; temporary-table scripts are not promised to be atomic.
- `rows` contains all rows from only the last result-producing statement and is loaded in memory. Consumers should not use this API for unbounded result sets.
- V1 does not support stored procedures, triggers, or scripts using client-side `DELIMITER` directives.
- V1 rejects MySQL executable comments such as `/*!...*/`; ordinary comments remain opaque to parameter and transaction-command recognition.
- The new feature is an additive library capability and does not change the email module's dependencies or public behavior.
