# Tasks: SQL Script Results as Polars DataFrames

**Input**: Design documents from `/specs/005-sql-script-polars/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/python-api.md](contracts/python-api.md), [quickstart.md](quickstart.md)

**Tests**: Included because FR-012 requires deterministic offline coverage. Write focused tests before the implementation they specify.

**Organization**: Tasks follow the three user stories and their priorities in `spec.md`. Existing project structure, Polars extra, fakes, and CI configuration are reused.

## Phase 1: Setup

**Purpose**: Project initialization and basic structure.

No setup tasks are needed. The repository already has the planned `src/` layout, optional Polars extra, database unit-test structure, and quality workflow in `src/pintos_utils/database/`, `pyproject.toml`, `tests/unit/database/`, and `.github/workflows/_quality.yml`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared result-schema and conversion-error contracts used by the user stories.

- [X] T001 [P] Add and confirm failing tests for `SqlScriptResult.columns` default and positional compatibility in `tests/unit/database/test_models.py`
- [X] T002 [P] Add and confirm the conversion-operation error contract in `tests/unit/database/test_dataframe_exceptions.py`
- [X] T003 [P] Add a defaulted ordered `columns` field after existing fields in `src/pintos_utils/database/models.py`, preserving existing positional construction
- [X] T004 [P] Extend the `DataFrameDatabaseError.operation` type to include `"convert"` in `src/pintos_utils/database/exceptions.py`

**Checkpoint**: The result model can retain ordered schema metadata, and conversion failures have a typed operation value without changing existing error operations.

---

## Phase 3: User Story 1 - Convert a Script Result to a DataFrame (Priority: P1) 🎯 MVP

**Goal**: Convert existing `SqlScriptResult` objects to eager Polars DataFrames with row order, column order, and values preserved.

**Independent Test**: Convert populated and empty results and verify exact shape, ordered column names, row order, and values; conversion rejects inconsistent or lossy input and does not disclose row values in its error message or default logs.

### Tests for User Story 1

- [X] T005 [US1] Add and confirm failing converter tests for populated rows, known and unknown empty schemas, first-row key order, inconsistent rows, duplicate columns, representative SQL scalar round trips (`None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes), unsupported/lossy values, and redacted failures in `tests/unit/database/test_sql_script_result_dataframe.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement lazy-Polars `sql_script_result_to_dataframe`, exact row-key and duplicate-name validation, lossless-value checks, sanitized conversion errors, and static default logs in `src/pintos_utils/database/dataframe.py`; export it from `src/pintos_utils/database/__init__.py`

**Checkpoint**: The public converter is importable without Polars installed, succeeds with the Polars extra, and returns documented empty shapes.

---

## Phase 4: User Story 2 - Execute SQL and Receive a DataFrame (Priority: P1)

**Goal**: Return the last result-producing statement as a DataFrame from SQL string and SQL file execution, preserving binding and the clarified commit order.

**Independent Test**: With fake connections, verify populated and empty final result sets, later non-result statements, file encoding and parameters, cursor/connection ownership, active-transaction rejection, and conversion-before-commit. A conversion failure with `commit=True` attempts rollback; with `commit=False`, neither commit nor rollback occurs. Existing methods still return `SqlScriptResult` with their prior transaction behavior.

### Tests for User Story 2

- [X] T007 [US2] Add and confirm failing fake-connection tests for `execute_dataframe` and `execute_file_dataframe`, including result selection, binding, encoding, commit/rollback ordering, rollback failure retained as cleanup context, no added automatic rollback on SQL/fetch/cursor-close failures, error preservation, and existing API compatibility in `tests/unit/database/test_sql_script_executor_dataframe.py`

### Implementation for User Story 2

- [X] T008 [US2] Check for Polars before executing SQL and report the `pintos-utils[mysql,polars]` installation if missing; capture ordered result columns and implement `execute_dataframe` and `execute_file_dataframe` in `src/pintos_utils/database/sql_script_executor.py`, converting before commit and attempting rollback only after conversion failure with `commit=True`

**Checkpoint**: Both new methods return the final result set as a DataFrame; `execute` and `execute_file` retain their result type and existing transaction behavior.

---

## Phase 5: User Story 3 - Keep Polars Optional (Priority: P2)

**Goal**: Preserve non-Polars imports and existing APIs without Polars installed, while reporting actionable installation guidance for new Polars capabilities.

**Independent Test**: In a subprocess that blocks Polars imports, import `pintos_utils.database` and use existing non-Polars APIs; call each new Polars capability and verify an actionable error is returned before SQL is sent. Confirm the database guide explains both installation and the result returned by each API.

### Tests for User Story 3

- [X] T009 [P] [US3] Add subprocess coverage for import safety, existing executor availability, standalone converter installation guidance, and DataFrame executor preflight in `tests/unit/database/test_dataframe_optional.py`

### Documentation for User Story 3

- [X] T010 [P] [US3] Document optional installation, conversion semantics, empty results, transaction timing, execution totals and when to use `SqlScriptResult`, and examples for both executor methods in `docs/database.md`
- [X] T011 [P] [US3] Add developer reference cards and public export entries for `sql_script_result_to_dataframe`, `execute_dataframe`, and `execute_file_dataframe` in `README.md`

**Checkpoint**: Consumers without Polars retain current imports and APIs; consumers using the feature receive installation guidance and documented return/transaction semantics.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Verify the completed stories against the quickstart and project quality gates.

- [X] T012 Run the full quality checks from `specs/005-sql-script-polars/quickstart.md`, including unit coverage, Ruff lint and formatting, mypy, `uv build --no-sources`, distribution metadata, and optional imports; resolve failures in `tests/unit/database/`, `src/pintos_utils/database/`, `pyproject.toml`, and `.github/workflows/_quality.yml`
- [X] T013 Review the public API for additive SemVer compatibility, including `SqlScriptResult` positional construction and exported names; record the review outcome in `specs/005-sql-script-polars/contracts/python-api.md` before release

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No work is needed; the repository setup already satisfies the plan.
- **Foundational (Phase 2)**: Begins immediately. T001 and T002 can run in parallel; T003 follows T001 and T004 follows T002. This phase blocks all user stories.
- **User Story 1 (Phase 3)**: Starts after Phase 2; T005 tests precede T006 implementation.
- **User Story 2 (Phase 4)**: Starts after User Story 1 because the executor methods call the public converter; T007 tests precede T008 implementation.
- **User Story 3 (Phase 5)**: Starts after both public API surfaces exist. T009, T010, and T011 use separate files and can run in parallel.
- **Polish (Phase 6)**: T012 follows all desired stories and documentation; T013 records the compatibility review before release.

### User Story Dependencies

- **US1 (P1)**: Depends on the shared result/error contracts; no dependency on another user story.
- **US2 (P1)**: Depends on US1's converter so both methods share one conversion implementation.
- **US3 (P2)**: Verifies the optional behavior of US1 and US2 and documents their public APIs; it depends on both API surfaces being implemented.

### Parallel Opportunities

- **Foundation**: T001 and T002 can be authored concurrently in separate test files. Afterward, T003 and T004 can be implemented concurrently in separate source files.
- **US1**: No safe parallel pair within this story: its focused tests precede implementation in the converter module and public export.
- **US2**: No safe parallel pair within this story: its behavior tests precede the shared executor implementation.
- **US3**: T009, T010, and T011 can run concurrently after T008 because they edit separate test and documentation files.

### Parallel Execution Examples

**Foundation**

```text
Task T001: tests/unit/database/test_models.py
Task T002: tests/unit/database/test_dataframe_exceptions.py
```

**User Story 1**

```text
Run T005 in tests/unit/database/test_sql_script_result_dataframe.py;
after its cases are in place, run T006 in dataframe.py and database/__init__.py.
```

**User Story 2**

```text
Run T007 in tests/unit/database/test_sql_script_executor_dataframe.py;
after its cases are in place, run T008 in sql_script_executor.py.
```

**User Story 3**

```text
Task T009: tests/unit/database/test_dataframe_optional.py
Task T010: docs/database.md
Task T011: README.md
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete the shared result and error contracts (Phase 2).
2. Add and implement the standalone conversion tests/API (US1).
3. Validate the converter independently using its focused offline tests and empty-result cases.

### Incremental Delivery

1. Complete the foundation and deliver US1 as the first usable increment.
2. Add US2 after US1 to offer direct SQL string and file execution into DataFrames.
3. Complete US3's import-safety tests and public documentation.
4. Run T012 against the project quality gates and quickstart scenarios, then complete T013 before release.

## Notes

- `[P]` appears only where tasks touch separate files and have no dependency on each other's changes.
- Every user-story task carries its `[US#]` label; setup, foundation, and polish tasks do not.
- No live MySQL test is required for the specified acceptance coverage; use the repository's fake connection and cursor.
