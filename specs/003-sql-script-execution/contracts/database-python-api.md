# Public Python API Contract: Database Script Execution

## Public imports

```python
from pintos_utils.database import (
    SqlScriptError,
    SqlScriptExecutor,
    SqlScriptResult,
)
```

These names form the documented public API for this feature. Result and error models do not expose provider SDK types. The consumer supplies the MySQL Connector/Python connection.

Install optional database support with:

```bash
pip install "pintos-utils[mysql]"
```

## Construction

```python
executor = SqlScriptExecutor(connection)
```

`connection` is created and configured by the consumer. The executor never opens/closes it or changes its autocommit configuration. All statements in one call use the same connection/session. The executor closes its own cursor.

## Execution methods

```python
execute(
    script: str,
    params: Mapping[str, Any] | None = None,
    commit: bool = False,
) -> SqlScriptResult

execute_file(
    file_path: str | Path,
    params: Mapping[str, Any] | None = None,
    commit: bool = False,
    encoding: str = "utf-8",
) -> SqlScriptResult
```

Public value markers use `:name`, where the name matches `[A-Za-z_][A-Za-z0-9_]*`. Repeated names are supported. Values are bound separately using Connector/Python's named parameter style; missing values are detected before any statement runs, extra mapping keys are ignored, and markers cannot stand in for table or column identifiers. Marker-like content inside strings, ordinary comments, or quoted identifiers is preserved. Actual MySQL executable comments `/*!...*/` outside strings and quoted identifiers are rejected before execution; the same sequence in a string or quoted identifier is preserved.

Statements execute in source order on one dictionary cursor. Empty or ordinary-comment-only statements are skipped. MySQL executable comments are rejected. Procedures, triggers, and client-side `DELIMITER` directives are not supported.

## Result

`SqlScriptResult` exposes:

```python
statements_executed: int
rows: list[dict[str, Any]]
affected_rows: int
```

`statements_executed` counts successful statements. `affected_rows` sums non-negative counts reported for DML. `rows` contains only the last result set, or an empty list if none was produced. Rows are materialized in memory; large/unbounded result sets are outside the intended use.

## Errors

`SqlScriptError` is the library exception boundary. A statement-related error exposes the one-based `statement_index`, SQL statement, a diagnostic message, and the original exception when one exists; the original runtime error is chained as `__cause__`. Preflight rejections and other failures without a driver exception are still `SqlScriptError` but do not invent an original cause.

Bound values are excluded from default logs and error messages. SQL text may be attached to an exception for diagnosis.

## Transaction ownership

- `commit=False`: the executor does not call `commit()` and does not issue automatic rollback.
- `commit=True` with empty/ordinary-comment-only input: return a no-op result without committing. MySQL executable comments are rejected before filtering.
- `commit=True` with a non-empty script and an already-active connection transaction: raise `SqlScriptError` before SQL, leaving the transaction untouched.
- `commit=True` with a non-empty script and no active transaction: call `commit()` once after all statements succeed.
- Scripts containing explicit transaction-control SQL are rejected before any statement executes. This includes `START TRANSACTION`, `BEGIN [WORK]`, `COMMIT [WORK]`, `ROLLBACK [WORK]`, `SAVEPOINT`, `RELEASE SAVEPOINT`, `SET [GLOBAL | SESSION] TRANSACTION`, and any `SET` assignment to the system variable `autocommit` (including qualified and multi-assignment forms, with `=` or `:=`). Ordinary strings, ordinary comments, and quoted identifiers do not trigger rejection. Actual MySQL executable comments outside strings and quoted identifiers are rejected as unsupported input.
- The executor never closes the supplied connection. The consumer decides whether and when to roll back after an error.
- MySQL DDL and some other statements can commit implicitly. Temporary-table DDL may be non-rollbackable even where it avoids an implicit commit; script-level atomicity is not promised.

## Supported input boundary

Conventional `USE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TEMPORARY TABLE`, and `DROP TEMPORARY TABLE` statements are in scope. Stored procedures, triggers, `DELIMITER`, explicit transaction-control commands, and MySQL executable comments are outside v1.
