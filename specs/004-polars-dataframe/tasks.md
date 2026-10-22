# Tasks: Polars DataFrame Database Integration

**Input**: Design documents from `/specs/004-polars-dataframe/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/dataframe-api.md](contracts/dataframe-api.md), [quickstart.md](quickstart.md)

**Tests**: Included because FR-020 explicitly requires deterministic offline unit tests and optional disposable-MySQL integration coverage.

**Organization**: Tasks are grouped by the four user stories in `spec.md`: US1 query, US2 APPEND, US3 UPSERT, and US4 optional Polars installation.

## Phase 1: Setup

**Purpose**: Add the optional dependency and ensure CI installs it for the feature's tests without changing base dependencies.

- [X] T001 [P] Add the `polars` optional extra to `pyproject.toml` and refresh the resolved dependency in `uv.lock` without adding Polars to base dependencies.
- [X] T002 [P] Add `--extra polars` to the locked test-environment sync in `.github/workflows/_quality.yml`, preserving the existing `gmail` and `mysql` extras.

## Phase 2: Foundational

**Purpose**: Create public result/error contracts and fake transaction/batch behavior required by the story implementations.

- [X] T003 [P] Define `ImportMode` and immutable `DataFrameImportResult` in `src/pintos_utils/database/models.py`, with enum and result coverage in `tests/unit/database/test_dataframe_models.py`.
- [X] T004 [P] Define `DataFrameDatabaseError` with operation, original-cause, and cleanup-error context in `src/pintos_utils/database/exceptions.py`, with coverage in `tests/unit/database/test_dataframe_exceptions.py`.
- [X] T005 [P] Extend `tests/unit/database/fakes.py` to model explicit transaction start, `executemany` batches and failures, cursor metadata, multiple result sets, rollback, cleanup, and connection preservation while keeping existing fake behavior intact.

**Checkpoint**: Complete Phase 1 and Phase 2 before beginning any user story.

## Phase 3: User Story 1 - Receive statement results as a Polars DataFrame (Priority: P1)

**Goal**: Execute one supported, bound SQL statement through the supplied connection and return its single row result as an eager Polars DataFrame with operation-owned transaction behavior.

**Independent Test**: With fake MySQL cursors, verify columns/order/values, empty-result columns, bound values, a statement that returns rows while changing data, commit/rollback, active-transaction rejection, unsupported-statement preflight, and that the supplied connection remains open. The optional integration test uses only the configured disposable MySQL database.

### Tests for User Story 1

- [X] T006 [P] [US1] Write offline query, empty-result, bound-parameter, simulated data-changing statement with returned rows, no-result, conversion-error, transaction-control and implicit-commit rejection, `CALL` and multiple-statement rejection, additional-result-set rollback, commit/rollback, connection-preservation, and sensitive-parameter redaction cases (assert sentinel values are absent from logs and errors) in `tests/unit/database/test_dataframe_query.py`.
- [X] T007 [P] [US1] Add opt-in disposable-MySQL query acceptance cases, including empty results and rollback after a failing conversion, in `tests/integration/database/test_dataframe_mysql.py`.

### Implementation for User Story 1

- [X] T008 [US1] Implement private single-statement parsing, `:name` binding translation, and preflight rejection for transaction controls, implicit-commit forms, executable comments, and `CALL` in `src/pintos_utils/database/_sql.py`.
- [X] T009 [US1] Implement `query_dataframe` with a lazily imported Polars reader, explicit cursor ownership, one-result validation, transaction start/commit/rollback, feature errors, and exports for `query_dataframe`, `ImportMode`, `DataFrameImportResult`, and `DataFrameDatabaseError` in `src/pintos_utils/database/dataframe.py` and `src/pintos_utils/database/__init__.py`.

**Checkpoint**: US1 is independently usable and its offline acceptance suite passes.

## Phase 4: User Story 2 - Append DataFrame rows in batches (Priority: P1)

**Goal**: Insert every valid DataFrame row into an existing transactional table in bounded batches under one import-owned transaction.

**Independent Test**: Use fakes to observe multiple bound `executemany` batches with one commit, and inject a later-batch failure to verify rollback. Cover empty frames, invalid batch sizes, unknown columns, unsupported conversions, transactional-engine checks, and connection preservation. The opt-in integration cases verify committed rows and all-or-nothing rollback.

### Tests for User Story 2

- [X] T010 [P] [US2] Write offline APPEND cases for validation, exact scalar conversion, bounded batches, empty no-op, one-commit behavior, later-batch rollback, error causes, connection preservation, and sensitive-row redaction (assert sentinel values are absent from logs and errors) in `tests/unit/database/test_dataframe_append.py`.
- [X] T011 [P] [US2] Add opt-in disposable-MySQL APPEND cases for persisted multi-batch rows, rejected target schemas, and rollback after a constraint failure in `tests/integration/database/test_dataframe_mysql.py`.

### Implementation for User Story 2

- [X] T012 [US2] Implement safe table/column identifier handling, selected-schema table metadata lookup, transaction-capable-engine checks, writable-column validation, and lossless Polars-to-MySQL scalar conversion in `src/pintos_utils/database/dataframe.py`.
- [X] T013 [US2] Implement explicit `APPEND` mode with positive batch-size validation, `iter_slices` bounded row conversion, parameterized `executemany`, one transaction across all batches, empty-frame no-op, and exports for `import_dataframe`, `ImportMode`, and `DataFrameImportResult` in `src/pintos_utils/database/dataframe.py` and `src/pintos_utils/database/__init__.py`.

**Checkpoint**: US2 is independently usable after US1 and its offline acceptance suite passes.

## Phase 5: User Story 3 - Insert and update rows through UPSERT (Priority: P2)

**Goal**: Stage DataFrame rows, update matches by the caller-selected complete unique key, and insert unmatched rows without creating persistent staging objects.

**Independent Test**: Fake database cases verify composite and single keys, matches and inserts, key-only input, null/duplicate/missing/non-unique key rejection before target writes, other-unique-key conflicts, rollback, cleanup failure reporting, and connection preservation. The opt-in integration cases verify final target rows and staging cleanup.

### Tests for User Story 3

- [X] T014 [P] [US3] Write offline UPSERT cases for unique-index metadata, source nulls/duplicates, matched updates, unmatched inserts, key-only frames, other-unique conflicts, rollback, staging cleanup, and sensitive-row redaction (assert sentinel values are absent from logs and errors) in `tests/unit/database/test_dataframe_upsert.py`.
- [X] T015 [P] [US3] Add opt-in disposable-MySQL UPSERT cases for composite keys, existing-row updates, unmatched inserts, a conflict on a different unique index, rollback, and absence of persistent staging artifacts in `tests/integration/database/test_dataframe_mysql.py`.

### Implementation for User Story 3

- [X] T016 [US3] Implement complete primary/unique-index validation from `INFORMATION_SCHEMA.STATISTICS`, source key null/duplicate checks, unique temporary staging lifecycle, key-based `UPDATE`, unmatched ordinary `INSERT`, cleanup, and atomic rollback in `src/pintos_utils/database/dataframe.py`.

**Checkpoint**: US3 is independently usable after US2 and its offline acceptance suite passes.

## Phase 6: User Story 4 - Install Polars support only when needed (Priority: P3)

**Goal**: Keep the base library and existing modules usable without Polars while giving DataFrame operations an actionable missing-extra error.

**Independent Test**: In a base-plus-existing-extras environment without Polars, import the base package, email module, SQL-script database API, and public DataFrame models/errors successfully; invoking a DataFrame operation reports the `[mysql,polars]` installation. In an environment with both extras, the public DataFrame API imports and operates.

### Tests for User Story 4

- [X] T017 [US4] Add package-metadata and no-Polars import tests for base dependencies, existing database/email imports, public models, and actionable operation errors in `tests/unit/database/test_dataframe_optional.py`.

### Implementation for User Story 4

- [X] T018 [US4] Ensure `src/pintos_utils/database/__init__.py` and `src/pintos_utils/database/dataframe.py` defer Polars imports until an operation is called and translate a missing Polars/MySQL dependency into an actionable `DataFrameDatabaseError` naming `pintos-utils[mysql,polars]`.

**Checkpoint**: US4 preserves base imports and offers the documented optional installation path.

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete consumer documentation and verify all acceptance paths and repository quality gates.

- [X] T019 Update `docs/database.md` with both extras, query binding/transaction semantics, the transactional-only rollback boundary for query side effects, APPEND and UPSERT examples, lossless conversion limits, error handling, target requirements, and stored-procedure/multiple-result limitations. Document the tested MySQL server version after disposable integration verification. Disposable MySQL was not configured; server version is documented as unverified.
- [X] T020 Validate the examples and behavior statements in `specs/004-polars-dataframe/quickstart.md` against the implemented signatures, optional install path, query rollback boundary, and unsupported query forms. Examples and stated boundaries were checked against the implemented API.
- [X] T021 Run the offline unit suite under `tests/unit/database/` plus the full unit suite with pytest-cov (for example, `uv run pytest tests/unit --cov=pintos_utils --cov-report=term-missing`); run Ruff and mypy over `src/pintos_utils/`, and build the package using the commands/configuration in `pyproject.toml`. Validated: 189 unit tests passed; Ruff, formatting, mypy, and isolated package build passed.
- [X] T022 Run `tests/integration/database/test_dataframe_mysql.py` only when its explicit disposable-database environment is configured, confirming the configured database name passes the test guard and is not production or corporate. When run, record the MySQL server version and update `docs/database.md` with the verified version. Skipped by its environment gate because no explicit disposable MySQL configuration is present.
- [X] T023 After the required user stories and documentation are complete, review the public exports and signatures in `src/pintos_utils/database/__init__.py`, including transaction, error, and conversion semantics, against the existing API. Record the SemVer compatibility impact in `docs/database.md` before release. Public API review found the change additive and compatible with a minor release.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T001 and T002 can run in parallel.
- **Foundational (Phase 2)**: Starts after setup; T003, T004, and T005 touch separate files and can run in parallel. This phase blocks all user stories.
- **US1 (Phase 3)**: Starts after foundations. Write T006 and T007 first; they can run in parallel. T008 and T009 follow in order.
- **US2 (Phase 4)**: Starts after US1 because it extends the same public operation module. Write T010 and T011 first; they can run in parallel. T012 and T013 follow in order.
- **US3 (Phase 5)**: Starts after US2 because it reuses import validation, batching, result types, and transaction handling. Write T014 and T015 first; they can run in parallel. T016 follows.
- **US4 (Phase 6)**: The optional extra is prepared in Setup; verify the complete lazy-import and missing-dependency behavior after the public operations exist.
- **Polish (Phase 7)**: Depends on the desired stories being complete.

### User Story Dependencies

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> US4 -> Polish
```

US2 and US3 share `dataframe.py` with earlier stories, so implementation is intentionally incremental. US4's metadata setup occurs in Phase 1, while its end-to-end optional-import check follows the complete API.

### Parallel Opportunities

- T001 and T002: dependency metadata and CI setup edit separate files.
- T003, T004, and T005: public models, exception type, and fakes are separate foundational files.
- T006 with T007, T010 with T011, and T014 with T015: each pair writes a unit-test file and an integration-test file independently; complete both before implementing that story.
- Within story implementation, keep tasks that edit `src/pintos_utils/database/dataframe.py` sequential.

## Parallel Example: User Story 1

```text
After T001-T005 complete, write T006 in tests/unit/database/test_dataframe_query.py
and T007 in tests/integration/database/test_dataframe_mysql.py in parallel.
Run the offline query tests and confirm they fail for the missing API, then complete
T008 and T009 sequentially.
```

## Parallel Example: User Story 2

```text
After US1 is complete, write T010 in tests/unit/database/test_dataframe_append.py
and extend tests/integration/database/test_dataframe_mysql.py in T011 in parallel.
Then implement T012 and T013 sequentially in src/pintos_utils/database/dataframe.py.
```

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1 and validate its offline query acceptance tests; this is the smallest independently usable increment.
3. Add US2 APPEND and validate batching/rollback before starting UPSERT.
4. Add US3 UPSERT and validate key/staging lifecycle.
5. Complete US4 optional-install checks, documentation, and repository quality gates.

### Incremental Delivery

Deliver one complete story at a time in the dependency order above. Do not start a later story's implementation until its own tests have been written and the prior story's shared module changes are complete. Run MySQL integration acceptance only against a configured disposable database.

## Completion Criteria

- Every task uses `- [ ] T###`, with `[P]` only where files/dependencies permit parallel work and `[US#]` on every user-story task.
- Every task description names the source, test, configuration, or documentation path it changes or validates.
- Each story has an independent test criterion and offline test task; integration tasks remain opt-in and disposable-only.
- No task creates or alters the production target schema, changes the caller's connection ownership, or adds Polars to base dependencies.
