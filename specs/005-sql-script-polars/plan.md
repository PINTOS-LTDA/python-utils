# Implementation Plan: SQL Script Results as Polars DataFrames

**Branch**: `005-sql-script-polars` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-sql-script-polars/spec.md`

## Summary

Add an optional conversion function, `sql_script_result_to_dataframe`, plus `SqlScriptExecutor.execute_dataframe` and `execute_file_dataframe`. Extend `SqlScriptResult` with ordered result-column metadata, then reuse the existing lazy Polars integration and lossless-value checks. DataFrame execution shares the current SQL execution path; when `commit=True`, it converts the result before committing and attempts rollback only if conversion fails. Existing result-returning methods keep their current behavior.

## Technical Context

**Language/Version**: Python >=3.11, using the project's `src/` layout and strict typing conventions.

**Primary Dependencies**: Existing optional `mysql` extra (`mysql-connector-python>=9.2,<10`, `sqlparse>=0.5,<1`) and optional `polars` extra (`polars>=1.0,<3`). No new runtime dependency and no base-dependency change.

**Storage**: MySQL through a consumer-owned Connector/Python connection; no schema or persistent storage changes.

**Testing**: Deterministic pytest unit tests with the existing fake connection and cursor. No live service is required for the feature's acceptance checks. Tests characterize representative SQL scalar round trips and transaction behavior for conversion failures, rollback cleanup failures, and SQL/fetch/cursor-close failures. Ruff and mypy apply to maintained source; package and CI metadata checks ensure Polars remains optional.

**Target Platform**: Python 3.11+ applications using the existing MySQL executor; no additional operating-system or server-version requirement.

**Project Type**: Reusable Python library with optional database integrations.

**Performance Goals**: No latency target is specified. Results and DataFrames are eager and fully materialized; conversion uses memory proportional to the result size and may temporarily keep both row dictionaries and the DataFrame in memory. No streaming interface is in scope.

**Constraints**: Preserve SQL binding, statement ordering, caller-owned connection and transaction boundaries, and existing error behavior. Import Polars lazily. Retain ordered column metadata for empty result sets. Reject ambiguous or lossy conversion without putting row values in public error messages or default logs. With `commit=True`, perform conversion before commit and attempt rollback only for a conversion failure; a rollback cannot reverse MySQL implicit commits or non-transactional effects.

**Scale/Scope**: One result model, one standalone conversion function, two additive executor methods, one conversion operation error classification, database guide and README updates, and deterministic offline coverage. MySQL remains the only database provider.

## Constitution Check

**Before Phase 0**

- **I. Library-first and framework independence — PASS.** The feature adds Python APIs to the existing database package and no application framework.
- **II. Stable, typed public API — PASS.** New functions and methods will be typed, documented, package-exported, and reviewed as additive SemVer-compatible API.
- **III. Explicit boundaries and proportional dependency injection — PASS.** The consumer continues to supply the connection. A small shared private execution path avoids duplicating statement parsing and binding; no new factory or service layer is required.
- **IV. Optional integrations and secure defaults — PASS.** Polars remains in the named optional extra and is imported at call time. Error messages and default logs omit row contents.
- **V. Verification and documentation — PASS.** Fakes provide offline transaction and cursor evidence; public API docs, README cards, Ruff, mypy, and package checks are included in implementation validation.

**After Phase 1**

The design still passes all five principles. The new converter uses the existing optional integration module, the result model remains independent of Polars types, and no database connection ownership changes. The only transaction change applies to the new DataFrame-returning methods and follows the approved clarification. No constitution exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/005-sql-script-polars/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── python-api.md
└── tasks.md                 # Produced by $speckit-tasks; not part of this plan
```

### Source Code (repository root)

```text
src/pintos_utils/database/
├── __init__.py                              # Export the converter
├── dataframe.py                             # Lazy Polars conversion and validation
├── exceptions.py                            # Add the conversion operation classification
├── models.py                                # Ordered SqlScriptResult column names
└── sql_script_executor.py                   # Capture metadata and add DataFrame methods

tests/unit/database/
├── fakes.py                                 # Cursor metadata and transaction events
├── test_models.py                           # SqlScriptResult schema defaults
├── test_execution.py                        # Existing executor compatibility
├── test_results_transactions_errors.py      # Commit/rollback ordering and failures
├── test_sql_script_result_dataframe.py      # Standalone conversion contract
└── test_sql_script_executor_dataframe.py    # SQL and file DataFrame methods

docs/database.md                             # User-facing database API guidance
README.md                                    # Developer reference cards and exports
```

**Structure Decision**: Extend the existing `pintos_utils.database` modules and test layout. Keep Polars loading and conversion in `dataframe.py`, where optional database DataFrame operations already live; keep `SqlScriptResult` provider-independent. Share SQL execution internals in `sql_script_executor.py` so both return modes preserve statement handling.

## Phase 0: Research

Completed in [research.md](research.md). Research resolves API naming, ordered result metadata, Polars construction and lossless validation, optional dependency errors, and the conversion-before-commit flow. It also records duplicate column names and empty-result dtypes as explicit limits.

## Phase 1: Design

Completed in [data-model.md](data-model.md), [contracts/python-api.md](contracts/python-api.md), and [quickstart.md](quickstart.md). The API contract adds `sql_script_result_to_dataframe(result)`, `execute_dataframe(script, params=None, commit=False)`, and `execute_file_dataframe(file_path, params=None, commit=False, encoding="utf-8")`.

The executor stores the column names from the last statement whose cursor reports a row result, including zero-row results. The converter uses that order; for a manually created non-empty result without metadata, it uses the first row's key order. It rejects inconsistent row keys, duplicate column labels, and values that fail lossless verification. A known-schema empty result retains names and order; its Polars dtypes are not promised because no row values are available to infer them.

For DataFrame execution, missing Polars is detected before SQL is sent. After SQL succeeds and the cursor is closed, the executor converts the result. It commits once only after conversion succeeds. A conversion failure with `commit=True` triggers a rollback attempt and reports a rollback failure as cleanup context; with `commit=False`, the executor performs neither action. SQL execution, fetch, and cursor-close errors and existing methods retain their current transaction behavior, with no added automatic rollback. Consumers needing script totals use `execute()` or `execute_file()` and convert the returned result separately.

## Complexity Tracking

No constitution violations or additional architectural layers are proposed.
