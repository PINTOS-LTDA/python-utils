# Data Model: SQL Script Results as Polars DataFrames

## `SqlScriptResult`

Provider-independent, mutable summary returned by `SqlScriptExecutor`.

| Field | Type | Default | Meaning |
|---|---|---:|---|
| `statements_executed` | `int` | `0` | Count of successfully executed statements. |
| `rows` | `list[dict[str, Any]]` | empty list | Materialized rows from the last result-producing statement. |
| `affected_rows` | `int` | `0` | Sum of known non-negative DML row counts. |
| `columns` | `list[str]` | empty list | Ordered names from the last result-producing statement, including an empty result set. |

`columns` is appended after the current fields to preserve existing positional constructors. A statement for which the cursor reports no row result does not replace either `rows` or `columns`. If no statement produces a result set, both remain empty. The model does not store SQL types or Polars dtypes.

## `polars.DataFrame`

The eager conversion target for the one result set represented by `SqlScriptResult`.

- Rows retain source order; columns retain `SqlScriptResult.columns` order.
- For a manually created result with rows and no column metadata, the first mapping's key order defines columns.
- Every row must expose exactly the same column names as the selected schema.
- Duplicate column names are rejected because dictionary rows cannot preserve multiple values under the same key.
- Values that Polars cannot represent faithfully cause conversion failure.
- Offline tests characterize scalar round trips for `None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes. Values retain type and value; byte-like values compare by content, and unsupported or out-of-range values fail rather than being coerced. Connector/Python represents MySQL `TIME` results as `datetime.timedelta`.
- Known columns with no rows produce a zero-row frame with those names; the dtypes are unspecified. No rows and no names produce a zero-row, zero-column frame.
- The DataFrame is fully materialized. No streaming or chunking lifecycle is introduced.

## Error model

`DataFrameDatabaseError` gains the operation value `"convert"` in addition to existing values `"query"` and `"import"`. It carries a sanitized message, the original conversion exception, and optional cleanup exception. Default logs contain only generic operation messages. SQL script failures continue to use `SqlScriptError` with their existing statement context.

## Transaction state for DataFrame execution

| Call state | SQL execution | Conversion | Commit | Rollback |
|---|---|---|---|---|
| `commit=False`, execution succeeds | Runs | Runs | None | None |
| `commit=False`, conversion fails | Runs | Fails | None | None |
| `commit=True`, execution and conversion succeed | Runs | Runs | Once, after conversion | None |
| `commit=True`, conversion fails | Runs | Fails | None | Attempted once; a failure is retained as cleanup context |
| SQL, fetch, or cursor-close failure | Uses existing script path | Not reached or incomplete | None | None, matching current executor behavior |
| `commit=True` with active caller transaction | Rejected before SQL | Not reached | None | None |

Rollback remains subject to MySQL implicit commits and non-transactional storage behavior.
