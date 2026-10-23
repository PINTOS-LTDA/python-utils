# Tasks: Polars Excel Export

**Input**: Design documents from `specs/006-polars-excel-export/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/polars-excel.md`, and `quickstart.md`

**Organization**: Tasks are grouped by user story. Deterministic unit tests are included because the project constitution requires tests for public behavior.

**Format**: `- [ ] [TaskID] [P?] [Story?] Description with file path`

## Phase 1: Setup

**Purpose**: Establish and lock the optional spreadsheet writer dependency.

- [X] T001 Update the optional dependency metadata and import-boundary tests in `tests/unit/database/test_dataframe_optional.py` to require Polars and XlsxWriter in the `polars` extra, confirm `project.dependencies` remains empty, and block both optional imports while importing base capabilities.
- [X] T002 Add `xlsxwriter>=3.0.8,<4` to the `polars` extra in `pyproject.toml` and refresh `uv.lock`.

---

## Phase 2: Foundational

**Purpose**: No separate infrastructure is required. The dependency setup in Phase 1 is the only shared prerequisite; the workbook helper is implemented with User Story 1 so that story remains an independently testable MVP.

---

## Phase 3: User Story 1 - Export a Polars DataFrame to an Excel file (Priority: P1) 🎯 MVP

**Goal**: Write a DataFrame to a caller-selected `.xlsx` path with the supplied worksheet and display behavior.

**Independent Test**: Export representative and empty DataFrames to temporary paths, inspect the workbook ZIP/XML for row and column order, values, worksheet settings, and number formats, then verify errors and that the caller's frame is unchanged.

### Tests for User Story 1

- [X] T003 [P] [US1] Add file-output tests for row and column preservation, both `str` and `Path` destinations, default and custom worksheet names, and replacement of an existing destination in `tests/unit/test_polars_excel_file.py`; confirm the new tests fail before implementation.
- [X] T004 [P] [US1] Add workbook tests for all specified date/time/numeric formats, Medium 2 table style, autofit and filtering when columns exist, a frozen first row and hidden gridlines for both populated and zero-column frames, zero-row behavior, unsupported-value errors, invalid destinations/names, dimension-limit errors, and input immutability in `tests/unit/test_polars_excel_formatting.py`; assert that a zero-column frame gains no synthetic table, use patched limits for boundary tests instead of allocating oversized frames, and confirm failures before implementation.

### Implementation for User Story 1

- [X] T005 [US1] Create `src/pintos_utils/polars_excel.py` with the typed `exportar_excel` API and a shared workbook writer that applies the source formats and worksheet options, handles zero-column frames without a synthetic column, checks Excel row/column limits, and lets invalid-path, invalid-name, and unsupported-value errors remain observable.

**Checkpoint**: User Story 1 is complete when the file-export tests pass and the output preserves the input data and specified workbook presentation.

---

## Phase 4: User Story 2 - Obtain an Excel workbook as bytes (Priority: P2)

**Goal**: Return the same workbook as complete bytes without creating a destination file.

**Independent Test**: Export a representative DataFrame to bytes, inspect the archive for the same worksheet, values, formats, and workbook settings as file output, and confirm no file is created as a side effect.

### Tests for User Story 2

- [X] T006 [US2] Add tests for a valid finalized `.xlsx` byte archive, default/custom worksheet names, data and formatting parity with file output, unsupported-value errors, input immutability, and absence of filesystem side effects in `tests/unit/test_polars_excel_bytes.py`; confirm the tests fail before implementation.

### Implementation for User Story 2

- [X] T007 [US2] Add the typed `exportar_excel_bytes` API in `src/pintos_utils/polars_excel.py`, pass a `BytesIO` destination through the shared writer, close/finalize the workbook, and return the completed buffer contents.
- [X] T008 [P] [US2] Document the `pintos-utils[polars]` installation, `pintos_utils.polars_excel` imports, both file and bytes examples, default/custom worksheet behavior, and visible errors for unsupported data or destinations in `README.md`.

**Checkpoint**: Both output modes are independently verifiable and documented; the bytes call returns a complete workbook without creating a file.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Run the feature and repository quality checks after both stories are complete.

- [X] T009 Run the commands in `specs/006-polars-excel-export/quickstart.md` and the distribution metadata validation in `.github/workflows/_quality.yml`; cover the full unit suite, Ruff, mypy, and build, and resolve failures in the affected source, test, documentation, or metadata paths.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 updates the metadata guard; T002 adds and locks XlsxWriter. T002 follows T001.
- **Foundational (Phase 2)**: No additional tasks; the Setup phase provides the shared dependency prerequisite.
- **User Stories**: Both require Setup. User Story 2 also depends on User Story 1's shared workbook writer.
- **Polish (Phase 5)**: T009 depends on both stories and documentation being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Starts after T002. T003 and T004 can run in parallel; T005 follows both test tasks.
- **User Story 2 (P2)**: Starts after T005. T006 specifies bytes behavior before T007 implements it. T008 can run in parallel with T006/T007 because it targets `README.md` and follows the approved contract.

### Parallel Opportunities

- T003 and T004 use separate test files and can be authored in parallel after Setup.
- After User Story 1 is complete, T008 can be handled in parallel with the bytes tests and implementation because it changes only `README.md`.
- The public functions in one module and tests for the same output mode are intentionally sequential; they share files and the tests are specified first.

## Parallel Examples

### User Story 1

After T002, separate contributors can prepare these test modules at the same time:

```text
Task: T003 - file-path behavior in tests/unit/test_polars_excel_file.py
Task: T004 - workbook format and edge cases in tests/unit/test_polars_excel_formatting.py
```

Then complete T005 in `src/pintos_utils/polars_excel.py` after both test tasks.

### User Story 2

After T005, the README work can run alongside bytes tests and implementation:

```text
Task: T006 - bytes behavior in tests/unit/test_polars_excel_bytes.py
Task: T008 - public examples and installation guidance in README.md
```

Complete T007 in `src/pintos_utils/polars_excel.py` after T006; T008 does not edit that module.

## Implementation Strategy

### MVP First

1. Complete Setup (T001-T002).
2. Complete User Story 1 tests and implementation (T003-T005).
3. Stop at the checkpoint and validate file output independently.
4. Deliver the file-export API as the first usable increment.

### Incremental Delivery

1. Add User Story 2 tests and bytes API (T006-T007), with README work (T008) in parallel where useful.
2. Run final quickstart and repository validation (T009).

## Notes

- Every task has a sequential ID and an exact repository path.
- `[P]` is used only for tasks that change different files and do not depend on each other.
- `[US1]` and `[US2]` map tasks to the corresponding prioritized stories in `spec.md`.
- No task adds a base runtime dependency or an Excel-reading capability.

## Phase 6: Convergence

- [X] T010 [CRITICAL] Review the public exports and signatures in `src/pintos_utils/polars_excel.py` against the existing API and record the compatibility and SemVer impact in `specs/006-polars-excel-export/contracts/polars-excel.md` before release, per Constitution II and the compatibility assumption in `spec.md` (missing).
