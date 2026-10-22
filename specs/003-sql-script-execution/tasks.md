# Tasks: MySQL SQL Script Execution

**Input**: Design documents in `specs/003-sql-script-execution/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included because the specification explicitly requires deterministic unit tests and optional disposable-MySQL integration coverage.

**Organization**: Tasks are grouped by the four prioritized user stories. Tasks within each story are ordered test-first where tests exercise new behavior.

## Phase 1: Setup

**Purpose**: Register optional runtime dependencies and create the minimal package/test scaffolding.

- [X] T001 [P] Add `mysql-connector-python` and `sqlparse` to the `mysql` optional extra and refresh the development lock in `pyproject.toml` and `uv.lock`.
- [X] T002 [P] Create the database package scaffold at `src/pintos_utils/database/__init__.py` without changing root or email exports.
- [X] T003 [P] Add reusable fake connection and cursor objects at `tests/unit/database/fakes.py` that record statement order, bindings, commits, rollbacks, cursor closure, and connection closure.

## Phase 2: Foundational Contracts

**Purpose**: Establish the shared result/error contracts before user-story execution work begins.

- [X] T004 [P] Add `SqlScriptResult` contract tests for its three fields and result defaults in `tests/unit/database/test_models.py`.
- [X] T005 [P] Add `SqlScriptError` contract tests for optional statement context and original exception chaining in `tests/unit/database/test_exceptions.py`.
- [X] T006 Implement `SqlScriptResult` and `SqlScriptError`, then export both from `src/pintos_utils/database/models.py`, `src/pintos_utils/database/exceptions.py`, and `src/pintos_utils/database/__init__.py`.

**Checkpoint**: The public result/error types and offline fakes are available for story work.

## Phase 3: User Story 1 - Execute a script in one MySQL session (Priority: P1) 🎯 MVP

**Goal**: Execute SQL strings and files in source order on the caller's connection and return the last result set.

**Independent Test**: Fake-backed tests verify one/multiple statements, ordinary-comment-only input, semicolons in strings/ordinary comments/quoted identifiers, UTF-8 file decoding, result replacement, cursor cleanup, and connection/session identity. An opt-in integration test confirms a temporary table created in one statement is visible to a later statement on the same disposable MySQL connection.

### Tests for User Story 1

> Write the unit and opt-in integration tests before implementing the execution path.

- [X] T007 [P] [US1] Add fake-backed tests for single/multiple statements, empty/ordinary-comment-only scripts, executable-comment rejection outside quotes and no rejection of `/*!` text inside strings/quoted identifiers, semicolons in strings/ordinary comments/quoted identifiers, UTF-8 files, last-result rows, cursor closure, and connection preservation in `tests/unit/database/test_execution.py`.
- [X] T008 [P] [US1] Add an opt-in disposable-MySQL test for temporary-table visibility across statements on one connection in `tests/integration/database/test_sql_script_executor_mysql.py`.

### Implementation for User Story 1

- [X] T009 [US1] Implement typed, documented `execute()` and `execute_file()` methods with `sqlparse` splitting, empty/comment filtering, sequential same-connection execution, dictionary rows, file encoding, and cursor cleanup in `src/pintos_utils/database/sql_script_executor.py`.

**Checkpoint**: US1 works independently for ordinary scripts without named markers and is verifiable offline; live session behavior has an explicitly gated integration test.

## Phase 4: User Story 2 - Bind named values safely (Priority: P1)

**Goal**: Bind named values through Connector/Python without changing marker-like text in strings, ordinary comments, or quoted identifiers.

**Independent Test**: Fake-backed tests inspect SQL and mappings sent to the cursor, verify repeated names and compatible Python values, and prove missing names fail before any SQL is executed.

### Tests for User Story 2

- [X] T010 [US2] Add tests for marker grammar, repeated/missing names, ignored extra keys, literal/ordinary-comment/identifier contexts, type preservation, and driver binding in `tests/unit/database/test_parameters.py`.

### Implementation for User Story 2

- [X] T011 [US2] Implement the lexical `:name` scanner, complete-script missing-name validation, conversion to Connector/Python named markers, and per-statement parameter filtering in `src/pintos_utils/database/sql_script_executor.py`.

**Checkpoint**: Marker values remain separate from SQL text, and missing parameters cannot cause partial execution.

## Phase 5: User Story 3 - Inspect results and errors while retaining transaction control (Priority: P2)

**Goal**: Provide accurate DML counts and diagnostics while enforcing the caller-owned connection and transaction policy.

**Independent Test**: Fake-backed tests verify affected-row totals, `commit=False` and `commit=True` behavior, rejection of an already-active transaction before cursor creation, preflight rejection of transaction-control SQL, stop-on-error behavior, exception chaining, no rollback, connection preservation, cursor cleanup, and logs without bound values. When disposable MySQL is configured, opt-in integration tests verify the real driver's transaction behavior using DML.

### Tests for User Story 3

- [X] T012 [P] [US3] Add tests for non-negative DML affected-row totals, commit/no-commit behavior, active-transaction rejection before cursor creation, and full-script transaction-control rejection. Cover `SET TRANSACTION` scope forms, `autocommit` assignment qualifiers/operators and multi-assignment targets; verify no false positives for strings, ordinary comments, quoted identifiers, and `@autocommit`, plus rejection of executable comments in `tests/unit/database/test_results_transactions_errors.py`.
- [X] T013 [P] [US3] Add tests for one-based statement diagnostics, chained driver errors, cursor/file/result/commit failures, no automatic rollback, and sensitive-value-free DEBUG logs in `tests/unit/database/test_errors_logging.py`.
- [X] T014 [P] [US3] Add opt-in tests against an explicitly configured disposable MySQL database for active-transaction rejection before SQL while asserting `connection.in_transaction` remains true, successful `commit=True` after DML, and no automatic commit with `commit=False`, using a second connection to verify visibility and caller rollback for cleanup in `tests/integration/database/test_sql_script_executor_mysql.py`.

### Implementation for User Story 3

- [X] T015 [US3] Implement DML row-count aggregation, transaction-control preflight, executable-comment rejection, `autocommit` assignment detection, the `connection.in_transaction` guard for non-empty `commit=True` calls, `SqlScriptError` wrapping/chaining, and DEBUG timing/progress logs without SQL or parameter values in `src/pintos_utils/database/sql_script_executor.py` and `src/pintos_utils/database/exceptions.py`.

**Checkpoint**: Transaction ownership, result counts, failure behavior, and diagnostics match the public contract.

## Phase 6: User Story 4 - Install and use optional MySQL support (Priority: P3)

**Goal**: Let consumers opt into MySQL dependencies and understand safe usage, transactions, and unsupported scripts.

**Independent Test**: The package metadata exposes the `mysql` extra; the base package and email module remain usable without it; database usage and limitations are documented with typed examples.

### Documentation and package verification for User Story 4

- [X] T016 [P] [US4] Document installation, consumer-created connections, string/file execution, named binding, results, errors, temporary tables, transaction ownership, security, memory use, and SQL limitations, including executable MySQL comments, in `docs/database.md`.
- [X] T017 [P] [US4] Add a discovery link to the database guide in `README.md` without changing existing email documentation.
- [X] T018 [US4] Verify base and `[mysql]` installation behavior, built wheel metadata, and email imports using `pyproject.toml`, `uv.lock`, and isolated package environments.

**Checkpoint**: Consumers can find the guide and install the optional feature without adding MySQL dependencies to the base installation.

## Phase 7: Polish and Cross-Cutting Validation

**Purpose**: Confirm the implementation meets the repository quality and release requirements.

- [X] T019 Align CI type-check/build metadata validation with the new `mysql` extra, then run pytest and coverage, Ruff check/format, strict mypy, and Hatchling wheel/sdist build; review public API compatibility and SemVer impact before release in `.github/workflows/_quality.yml` and `docs/releases.md`.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001, T002, and T003 target separate files and can be prepared in parallel.
- **Foundational (Phase 2)**: Depends on package/test scaffolding. T004 and T005 can be prepared in parallel; T006 follows both contract-test tasks.
- **US1 (Phase 3)**: Depends on setup and foundational contracts. T007 and T008 can be prepared in parallel; T009 follows the tests.
- **US2 (Phase 4)**: Depends on US1's `execute()` path. T010 tests precede T011 implementation.
- **US3 (Phase 5)**: Depends on US1 and US2 execution paths. T012, T013, and opt-in T014 can be prepared in parallel; T015 follows the test tasks.
- **US4 (Phase 6)**: Depends on the public API and dependency boundary being stable. T016 and T017 can be prepared in parallel; T018 verifies the finished package metadata and installation behavior.
- **Polish (Phase 7)**: Depends on all intended user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after setup/foundation; provides the executor spine and is the MVP.
- **US2 (P1)**: Extends US1 with safe named binding.
- **US3 (P2)**: Adds transaction policy, result counts, errors, and logs to the US1/US2 path.
- **US4 (P3)**: Documents and verifies the completed public API and optional dependency boundary.

### Requirement Coverage

- **US1**: FR-001–006, FR-011–012, and the session/result cases in FR-023.
- **US2**: FR-007–010 and the binding cases in FR-023.
- **US3**: FR-013–018, FR-025–026, and the transaction/error/logging cases in FR-023.
- **US4**: FR-019–024, including packaging, documentation, compatibility, and release checks.

### Parallel Opportunities

- **Setup**: T001, T002, and T003 use independent paths.
- **Foundation**: T004 and T005 test different public types and files.
- **US1**: T007 unit tests and T008 isolated integration test use different files; T009 follows.
- **US3**: T012 transaction/result unit tests, T013 error/logging tests, and T014 disposable-MySQL integration tests use separate files; T015 follows.
- **US4**: T016 guide authoring and T017 README linking use separate files; T018 follows the metadata change and stable API.
- Do not implement US1, US2, or US3 concurrently: they extend the same `sql_script_executor.py` and have an explicit dependency order.

## Parallel Examples

### User Story 1

After Phase 2, prepare `T007` and `T008` in parallel. Start `T009` after both test files are ready.

### User Story 2

Complete `T010` first, then implement `T011`; both tasks use the same executor path and should not overlap.

### User Story 3

After US2, prepare `T012`, `T013`, and the opt-in integration test `T014` in parallel. Start `T015` after the test tasks are ready.

### User Story 4

After the public API is stable, prepare `T016` and `T017` in parallel. Run `T018` after the optional-extra metadata and documentation exist.

## Implementation Strategy

### MVP First

1. Complete setup and foundational contracts.
2. Complete US1 tests and implementation.
3. Validate US1 with fakes; run the MySQL integration test only with an explicitly configured disposable database.
4. Review the working P1 execution increment before adding named binding and transaction behavior.

### Incremental Delivery

1. Deliver US1: sequential execution and final rows on the supplied session.
2. Deliver US2: safe named binding and full-script missing-name validation.
3. Deliver US3: transaction boundaries, result counts, diagnostics, and logs.
4. Deliver US4: optional installation, consumer documentation, and packaging verification.
5. Run cross-cutting quality gates and review the SemVer impact before release.

## Notes

- Every task uses the required checkbox, sequential ID, optional parallel marker, story label for story work, and a concrete target path.
- Tests are required by the feature specification and remain network-free by default.
- Integration tests must be explicitly gated to a disposable MySQL environment and must never target a corporate or production database.
- This file plans implementation; it does not authorize source-code changes by itself.

## Phase 8: Convergence

- [X] T020 Recognize CTE-prefixed `UPDATE` and `DELETE` statements when summing non-negative DML row counts, with fake-backed coverage, per FR-013 (partial).

## Phase 9: Convergence

- [X] T021 Stop CTE DML classification at the top-level statement verb and add fake-backed coverage proving `SELECT ... FOR UPDATE` does not contribute to DML row counts, per FR-013 (partial).
