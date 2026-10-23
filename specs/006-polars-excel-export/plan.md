# Implementation Plan: Polars Excel Export

**Branch**: `006-polars-excel-export` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-polars-excel-export/spec.md`

## Summary

Add `pintos_utils.polars_excel` with `exportar_excel` and
`exportar_excel_bytes`. Both entry points share the formatting and workbook
generation rules from the supplied helper and delegate DataFrame serialization
to `polars.DataFrame.write_excel`. Add XlsxWriter to the existing optional
`polars` extra, preserve the dependency-free base install, and document and
verify both output modes.

## Technical Context

**Language/Version**: Python >=3.11

**Primary Dependencies**: Existing `polars>=1.0,<3`; add `xlsxwriter>=3.0.8,<4` to the existing `polars` optional extra.

**Storage**: N/A. The file operation writes to a caller-selected path; the bytes operation uses an in-memory buffer.

**Testing**: pytest with Polars and XlsxWriter from the optional extra. Use Python's standard `zipfile` and XML libraries to inspect generated `.xlsx` contents without adding a workbook-reading dependency.

**Target Platform**: Supported Python platforms with Python >=3.11; local filesystem path or in-memory bytes.

**Project Type**: Reusable Python library using the existing `src/` layout.

**Performance Goals**: No latency or throughput target is specified. Column autofit is required by the source behavior; it scans data and is approximate, so no performance guarantee is introduced.

**Constraints**: Keep both spreadsheet dependencies optional. Preserve the specified worksheet, table, number-format, filter, freeze-pane, and gridline behavior. Apply table style, column autofit, and filtering when the DataFrame has columns; freeze the first worksheet row and hide gridlines in either case. Reject inputs that exceed Excel's worksheet bounds rather than silently truncate them. A zero-column DataFrame has no table range, so export a genuinely empty worksheet without inventing a column; table-only styling, filtering, and column autofit are inapplicable in that case.

**Scale/Scope**: One DataFrame per operation, represented on one worksheet. With a header row, at most 1,048,575 data rows and 16,384 columns fit Excel's worksheet limits. Empty frames with columns retain their headings; frames with no columns produce an empty worksheet.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Plan evidence | Gate |
|---|---|---|
| Library-first and framework independence | Adds a focused library module; no application framework or unrelated module dependency. | PASS |
| Stable, typed public API | The clarified API names and module are documented in a public contract; both functions have precise input and return annotations. | PASS |
| Explicit boundaries and proportional design | One private shared writer helper handles the two output destinations; no extra service layer or public exception hierarchy is needed. | PASS |
| Optional integrations and secure defaults | Polars and XlsxWriter stay in an optional extra; `project.dependencies` remains empty. | PASS |
| Verification and documentation | Deterministic local workbook tests, existing static checks, and README examples cover the public behavior. | PASS |

**Pre-research gate**: PASS. The public contract is approved by the feature spec. No unresolved `NEEDS CLARIFICATION` items remain in the technical context.

## Project Structure

### Documentation (this feature)

```text
specs/006-polars-excel-export/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── polars-excel.md
```

### Source Code

```text
src/pintos_utils/polars_excel.py
tests/unit/test_polars_excel_file.py
tests/unit/test_polars_excel_formatting.py
tests/unit/test_polars_excel_bytes.py
tests/unit/database/test_dataframe_optional.py  # update Polars extra metadata assertion
pyproject.toml                                  # add XlsxWriter to the polars extra
uv.lock                                         # lock the added optional dependency
README.md                                       # install matrix, API index, and examples
```

**Structure Decision**: Keep the new public API in the module selected during clarification. Keep its tests in the existing unit-test tree, update the current optional-extra assertion, and follow the README's reference-card format. The existing quality workflow already installs the `polars` extra, so it needs no extra-selection change.

## Design Decisions

1. Add `xlsxwriter>=3.0.8,<4` to the existing `polars` extra. This gives current Polars Excel-writing behavior the required writer version while keeping the base installation unchanged. Do not use Polars' broad `excel` feature extra, which also installs packages for reading Excel files outside this feature's scope.
2. Centralize workbook creation so path and byte output use identical formats and worksheet options. Use `BytesIO` for the bytes API and return its contents only after the workbook has closed.
3. For a zero-column frame, create the named empty worksheet directly instead of asking Polars to add a table with no columns. Do not add a synthetic heading. Table style, filtering, and column sizing have no range to act on for this case; still freeze the first worksheet row and hide gridlines.
4. Check the data dimensions before writing. Excel permits 1,048,576 rows and 16,384 columns; the table header uses one row, leaving a maximum of 1,048,575 DataFrame rows. Raise a visible error when those limits would be exceeded.
5. Let filesystem, worksheet-name, and unsupported-value errors remain observable to the caller; do not swallow them or report a successful export.

**Post-design Constitution Check**: PASS. The design keeps the new capability isolated, typed, dependency-optional, and directly testable. No constitution exception or additional abstraction is required.

## Implementation Sequence for `$speckit-tasks`

1. Declare and lock the optional XlsxWriter dependency; update the existing extra metadata expectation.
2. Implement the shared writer and both public functions in `src/pintos_utils/polars_excel.py`, including empty-frame and Excel-dimension handling.
3. Add deterministic tests in separate story-focused modules for file output, workbook formatting, bytes output, unsupported-value errors, and dependency boundaries.
4. Add the installation row, public module index, and file/bytes reference cards to `README.md`.
5. Run the repository's configured unit, Ruff, mypy, build, and metadata checks during implementation; keep any live spreadsheet applications out of scope.

## Complexity Tracking

No constitution violations. No additional runtime package, public model, or integration layer is introduced.
