# Implementation Plan: MySQL SQL Script Execution

**Branch**: `003-sql-script-execution` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification for executing named-parameter SQL scripts and files on a consumer-owned MySQL connection.

## Summary

Add the typed public API `pintos_utils.database.SqlScriptExecutor` for executing conventional SQL statements sequentially on one existing MySQL Connector/Python connection. Split statements with `sqlparse`, lexically recognize and bind public `:name` markers, preflight the complete script for missing values and transaction-control commands, and reject MySQL executable comments before executing SQL. With `commit=True`, reject a non-empty script if the connection already reports an active transaction; otherwise commit once after all statements succeed. Never close or roll back the supplied connection. Keep driver and parser dependencies in the optional `mysql` extra, and leave the base package and email module independent of them.

The design adds one cohesive service module, typed result/error models, tests, and consumer documentation. It does not add an ORM, web framework, provider registry, or generic database abstraction.

## Technical Context

**Language/Version**: Python >= 3.11<br>
**Primary Dependencies**: Optional `mysql` extra with `mysql-connector-python` and `sqlparse`; no new base runtime dependency<br>
**Build System**: Existing Hatchling configuration in `pyproject.toml`<br>
**Environment and Locking**: uv manages the development environment and lockfile<br>
**Development Dependencies**: Existing pytest, pytest-cov, Ruff, and strict mypy configuration<br>
**Storage**: None owned by the library; commands run on the consumer's existing MySQL connection<br>
**Testing**: Offline unit tests with fakes; optional integration tests against an explicitly configured disposable MySQL database for session and transaction behavior<br>
**Target Platform**: Python 3.11+ on platforms supported by MySQL Connector/Python<br>
**Project Type**: Reusable Python library<br>
**Performance Goals**: No numeric latency target. Script validation must finish before database execution, statements retain source order, and only the final result set is retained; final rows are materialized in memory.<br>
**Constraints**: Synchronous API; no connection creation/closure, autocommit changes, or automatic rollback; reject named-value omissions, transaction-control commands, and executable MySQL comments before executing any SQL; with `commit=True`, reject a pre-existing active transaction; omit bound values from logs and errors; no stored procedures, triggers, or `DELIMITER` scripts in v1; DDL and other MySQL implicit-commit behavior limits atomicity.<br>
**Scale/Scope**: One executor, one supplied connection/session per call, conventional statements, named values, and the last result set only.

## Constitution Check

| Principle | Plan assessment |
|---|---|
| I. Library-First and Framework Independence | **Pass**: additive importable library API with no web/application framework and no dependency on the email module. |
| II. Stable, Typed Public API | **Pass**: explicit exports, required method signatures, type hints, consumer docs, and compatibility review. The API addition is SemVer-minor-compatible; release versioning remains part of release review. |
| III. Explicit Boundaries and Proportional Dependency Injection | **Pass**: the consumer supplies its MySQL connection. Result/error models remain SDK-independent; no connection factory, generic provider interface, or unnecessary forwarding layer is added. |
| IV. Optional Integrations and Secure Defaults | **Pass**: both runtime dependencies are in the named `mysql` extra; base dependencies remain empty; values use driver binding and do not enter default logs/errors. |
| V. Verification and Documentation | **Pass**: deterministic mocked unit tests, optional disposable-database tests, public documentation, and project pytest-cov/Ruff/mypy checks are included in the implementation plan. |

**Pre-design gate**: Pass. No constitution principle requires an exception or amendment.

## Research Decisions

See [research.md](research.md) for findings, alternatives, and references. The design uses `sqlparse` for statement boundaries and a focused lexical scanner for named markers and prohibited transaction-control syntax. It binds values through Connector/Python, uses one dictionary cursor for the supplied connection, and validates the entire script before sending SQL. The transaction precondition is based on Connector/Python's `connection.in_transaction` property. MySQL implicit-commit behavior remains a documented server limitation.

## Design

### Public API and Responsibility Boundaries

- `models.py`: the SDK-independent `SqlScriptResult` value returned by both execution methods.
- `exceptions.py`: `SqlScriptError` diagnostics for input, file, preflight, cursor, statement, result-consumption, and commit failures.
- `sql_script_executor.py`: the public executor, file decoding, statement splitting, lexical preflight and binding, same-session execution, result collection, transaction option, and DEBUG logging. Keep small helpers private in this module unless implementation size shows a concrete reason to split them.
- `__init__.py`: re-export `SqlScriptExecutor`, `SqlScriptResult`, and `SqlScriptError` and declare the supported public names.
- `docs/database.md`: installation, examples, transaction ownership, security, and supported/unsupported SQL behavior.
- `tests/unit/database/`: fake connection/cursor behavior; no server or network required.
- `tests/integration/database/`: opt-in MySQL verification against an explicitly configured disposable database.

Do not add `contracts.py`, `services/`, `providers/`, or a public connection protocol solely to satisfy an architectural pattern. A single executor is the smallest clear service boundary for this MySQL-specific operation.

### Execution and Validation Flow

1. `execute_file()` reads the requested text using the caller's encoding, then follows the same path as `execute()`.
2. Lexically reject actual MySQL executable comments such as `/*!...*/` outside strings and quoted identifiers before discarding comments. Split the input with `sqlparse.split()`, preserve each original statement for diagnostics, and ignore whitespace-only or ordinary-comment-only fragments.
3. If no statements remain, return a zero-count result without opening a cursor or committing.
4. Scan all statements before database execution. In normal SQL context, identify valid `:name` markers, marker references per statement, and explicit transaction-control commands. Reject `SET` assignments targeting the system variable `autocommit`, including qualified and multi-assignment forms. Do not classify text inside literals, ordinary comments, or quoted identifiers as a marker or command.
5. Reject any transaction-control statement before SQL is sent. Recognize `START TRANSACTION`, `BEGIN [WORK]`, `COMMIT [WORK]`, `ROLLBACK [WORK]`, `SAVEPOINT`, `RELEASE SAVEPOINT`, `SET [GLOBAL | SESSION] TRANSACTION`, and `SET` assignments to `autocommit` with supported scope qualifiers and either assignment operator. Validate all required marker names across the script before execution; unreferenced supplied values are ignored. Do not use plain `script.split(';')` or raw-text regex substitution.
6. When `commit=True`, check `connection.in_transaction` before creating the cursor or executing SQL. If a transaction is active, raise `SqlScriptError` and leave the connection and transaction untouched. `commit=False` makes no such precondition check and never calls `commit()`.
7. Create one dictionary cursor from the supplied connection. For each statement in source order, translate only recognized markers to `%(name)s`, pass that statement's filtered mapping to `cursor.execute()`, consume its result before the next statement, and replace `rows` only when that statement produces a result set.
8. Count only successfully completed statements; sum non-negative DML row counts. Close the cursor in a `finally` path while leaving the supplied connection open.
9. For `commit=True`, call `connection.commit()` once after all non-empty statements succeed. Do not issue rollback automatically on statement, result, or commit failures; wrap failures in `SqlScriptError` and chain an original exception when one exists.

The lexical scanner is intentionally limited to the supported MySQL quoting and ordinary comment forms, the listed transaction-control forms, and public marker grammar; it is not a full SQL validator. MySQL executable comments are rejected rather than parsed. `sqlparse` provides splitting/tokenization rather than MySQL syntax validation. Stored routines, triggers, and client-side `DELIMITER` directives are outside v1.

### Transaction and Safety Boundaries

The caller owns connection and transaction lifecycle. A pre-existing transaction makes non-empty `commit=True` calls fail before SQL; a script cannot issue its own transaction-control commands or assign the system variable `autocommit`. MySQL executable comments are rejected during preflight. For an eligible successful call, `commit=True` commits once; for `commit=False`, the executor never calls `commit()`. No error path calls rollback or closes the connection.

This policy does not make arbitrary scripts atomic. MySQL DDL can commit implicitly; temporary-table creation/deletion may avoid an implicit commit but is still not rollbackable. Other MySQL statements can also have implicit-commit effects, so the documentation must describe the limitation without claiming that `commit=False` suppresses server-side commits caused by SQL itself.

### Project Structure

```text
pyproject.toml
uv.lock
README.md
docs/
└── database.md
src/
└── pintos_utils/
    ├── __init__.py                  # existing package exports remain unchanged
    ├── py.typed
    ├── email/                       # existing module remains independent
    └── database/
        ├── __init__.py
        ├── models.py
        ├── exceptions.py
        └── sql_script_executor.py
tests/
├── unit/
│   └── database/
│       ├── fakes.py
│       ├── test_models.py
│       ├── test_exceptions.py
│       ├── test_execution.py
│       ├── test_parameters.py
│       └── test_results_transactions_errors.py
└── integration/
    └── database/
        └── test_sql_script_executor_mysql.py  # opt-in, disposable MySQL only
specs/
└── 003-sql-script-execution/
    ├── spec.md
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── contracts/
    │   └── database-python-api.md
    ├── checklists/
    │   └── requirements.md
    └── tasks.md                    # generated in the next Spec Kit step
```

**Structure Decision**: Follow the existing single-project `src` layout and email-module naming conventions. Keep the database API in the requested four-file package and keep tests under the existing unit/integration split. Do not modify email modules or the root package exports unless implementation proves a required public import path needs it.

### Dependency Proposal

| Category | Packages | Reason |
|---|---|---|
| Base runtime | None added | Keep the base installation and email module independent of MySQL. |
| Optional `mysql` extra | `mysql-connector-python`, `sqlparse` | Driver-facing MySQL execution and runtime SQL statement splitting. |
| Development group | Existing pytest, pytest-cov, Ruff, mypy | Offline tests, coverage, lint/format, and strict type checking. |
| Build backend | Existing Hatchling | Preserve configured wheel and source-distribution build. |
| Environment manager | Existing uv | Synchronize development dependencies and refresh `uv.lock`. |

Declare the extra under `[project.optional-dependencies]` in `pyproject.toml`. Keep optional imports out of the base package and email module. The database API should remain importable without the extra where practical, while actual SQL execution must report clearly that `pintos-utils[mysql]` is required if `sqlparse` is unavailable.

## Post-Design Constitution Check

| Principle | Post-design assessment |
|---|---|
| I. Library-First and Framework Independence | **Pass**: all planned paths belong to the Python library or its docs/tests; no framework is introduced. |
| II. Stable, Typed Public API | **Pass**: the exact public API is specified in [database-python-api.md](contracts/database-python-api.md) and remains additive. |
| III. Explicit Boundaries and Proportional Dependency Injection | **Pass**: the consumer-owned connection is the injected boundary; models and errors do not depend on the driver SDK. |
| IV. Optional Integrations and Secure Defaults | **Pass**: optional extra is isolated; all binding remains driver-side; logs/errors exclude parameter values; no global logging configuration. |
| V. Verification and Documentation | **Pass**: offline fakes cover deterministic behavior; optional integration tests are isolated; documentation and quality gates are planned. |

No gate failures or unresolved specification questions remain. Implementation remains a separate phase after plan approval and task generation.

## Implementation Phases (After Approval)

1. **Foundation and public models**: Add the optional extra, database package scaffold, `SqlScriptResult`, `SqlScriptError`, and exports; preserve the base/email dependency boundary.
2. **P1 script execution**: Add splitting/filtering, file decoding, one-session sequential execution, result handling, and cursor lifecycle with fake-backed tests.
3. **P1 named binding and preflight**: Add lexical marker recognition and full-script missing-name validation, with tests proving no SQL executes when a required value is absent.
4. **P2 transaction, errors, and logs**: Add transaction-control preflight, the `in_transaction` precondition for `commit=True`, no-auto-rollback behavior, affected-row counts, diagnostics/chaining, safe DEBUG logs, mocked tests, and opt-in real-driver transaction integration tests against disposable MySQL.
5. **P3 packaging and documentation**: Add `docs/database.md`, update README discovery, synchronize `uv.lock`, and verify base/email installation without the optional extra and database installation with it.
6. **Cross-cutting verification**: Run pytest and coverage, Ruff check/format, strict mypy with database dependencies available, and Hatchling wheel/sdist build. Review the additive API's SemVer impact before release.

## Complexity Tracking

No constitution violations or additional architectural layers are proposed. No complexity exceptions require justification.
