# Research: SQL Script Results as Polars DataFrames

**Date**: 2026-10-23

**Scope**: Existing SQL script execution, Polars conversion, public API compatibility, and transaction ordering.

## Decisions

### 1. Add a standalone converter and additive executor methods

Expose `sql_script_result_to_dataframe(result)` in `pintos_utils.database`, and add `execute_dataframe(...)` and `execute_file_dataframe(...)` to `SqlScriptExecutor`. Keep `SqlScriptResult` as the intermediate, provider-independent result contract rather than adding a Polars method to the model. This gives callers with an already materialized result a direct conversion API while keeping the executor's existing result APIs intact.

**Rationale**: A module-level function matches the package's existing `query_dataframe` and `import_dataframe` style. DataFrame counterparts make the same SQL string/file features available without making the caller manually convert. A model method would couple a transport-neutral model to an optional library.

**Alternatives considered**: Add only `SqlScriptResult.to_polars()` (unnecessarily couples the model); add only a standalone function (does not provide the requested direct executor return path); replace `execute`/`execute_file` return values (breaks callers and violates the spec).

### 2. Append ordered column metadata to `SqlScriptResult`

Add `columns: list[str]` as the final dataclass field with an empty-list factory, preserving current positional construction of `SqlScriptResult(statements_executed, rows, affected_rows)`. The executor records names in cursor-description order whenever `cursor.with_rows` is true, including empty result sets. Later statements with no row result do not overwrite the last result schema.

**Rationale**: The existing model retains result rows but not result metadata, so empty SELECT results cannot otherwise retain their schema. MySQL Connector/Python exposes ordered `column_names` and cursor `description`; `with_rows` distinguishes an empty result set from an operation that has no row result. This is an additive model change.

**Alternatives considered**: Infer names only from non-empty rows (fails for empty results); store Polars schema/dtypes in the model (introduces optional dependency/provider metadata); redesign rows as tuples (changes existing consumer contract).

References: [Connector/Python `column_names`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-column-names.html), [Connector/Python `description`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-description.html), [Connector/Python `with_rows`](https://dev.mysql.com/doc/connectors/en/connector-python-api-mysqlcursor-with-rows.html).

### 3. Convert eagerly, preserve order, and reject ambiguous or lossy values

Load Polars lazily and construct a `polars.DataFrame` from the result row mappings with the ordered column-name schema, strict value handling, and full-input inference. Validate that each row has exactly the expected keys, and reuse the existing `_ensure_query_values_lossless` comparison where applicable. A manually constructed non-empty `SqlScriptResult` without `columns` uses the first row's insertion order. Empty results with known names return zero rows and those columns; an empty result with no names returns a zero-by-zero frame. Empty-result dtypes are not promised.

Reject duplicate output names for DataFrame conversion. The executor uses a dictionary cursor, so duplicate SQL labels cannot be represented as separate values in each row dictionary; silently accepting them could discard data. Consumers can assign unique SQL aliases. Reject inconsistent row shapes and any value that fails round-trip validation. Wrap failures in a generic public message and emit only static default log messages so row values are not disclosed.

**Rationale**: Polars accepts an ordered schema and strict construction; the existing query implementation already checks source values after materialization. Full-input inference avoids relying on only an initial row sample. The specification requires preserved order and failure rather than silent conversion loss.

**Alternatives considered**: Infer from only the first N rows (can miss later incompatible values); coerce mismatches (violates losslessness); rebuild values column by column (more conversion code and duplicated inference behavior); change executor rows to tuples (larger compatibility change).

References: [Polars DataFrame API](https://docs.pola.rs/api/python/stable/reference/dataframe/index.html), [Polars schema API](https://docs.pola.rs/api/python/stable/reference/schema/index.html).

### 4. Share execution internals and convert before commit

Factor a private execution path that keeps parsing, parameter binding, statement accounting, cursor lifecycle, and final result selection common to both return modes. The DataFrame methods check that Polars is available before SQL execution, execute and close the cursor, convert the final result, then commit once if requested. For conversion failure with `commit=True`, attempt rollback and attach any rollback error as cleanup context. For `commit=False`, issue neither commit nor rollback. Do not add rollback for SQL/fetch/cursor-close failures; the existing methods do not roll back those failures, and the clarification limits the new rollback rule to conversion failure.

The pre-existing `commit=True` check for an already active caller transaction remains in force. Existing `execute` and `execute_file` retain their SQL, error, commit, and rollback behavior. MySQL can implicitly commit some statements, and rollback cannot undo writes to non-transactional tables; the rollback attempt is therefore a best-effort transaction boundary, not a universal undo guarantee.

**Rationale**: Calling `execute(..., commit=True)` and converting afterward would commit before conversion, contrary to the user's clarification. A shared private path avoids divergent SQL semantics. Connector/Python exposes explicit `commit()` and `rollback()` operations; MySQL documents implicit-commit statements as a transaction limitation.

**Alternatives considered**: Convert after calling the public `execute` method (commit too early); duplicate SQL execution code in the DataFrame methods (risks semantic drift); roll back every failure (changes current behavior beyond the approved conversion rule).

References: [Connector/Python `commit()`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-commit.html), [Connector/Python `rollback()`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-rollback.html), [MySQL statements that cause implicit commits](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html).

### 5. Keep Polars optional and use actionable typed errors

Keep the existing `polars` extra and import Polars only at the operation boundary. The standalone converter requires `pintos-utils[polars]`; the MySQL DataFrame execution methods require `pintos-utils[mysql,polars]`. Extend `DataFrameDatabaseError.operation` with `"convert"` for standalone conversion failures and conversion failures from the executor; SQL execution failures continue to use `SqlScriptError`.

**Rationale**: The repository already uses lazy imports and `DataFrameDatabaseError` for optional DataFrame operations. A precise operation discriminator avoids labeling a conversion as a query or import. Existing APIs remain importable when Polars is absent.

**Alternatives considered**: Make Polars a base dependency (breaks the optional integration principle); raise raw `ImportError` (does not provide the package's actionable error convention); classify conversion as `query` (misstates the operation).

## Verification scope for implementation

- Unit tests use the existing fake cursor metadata and connection event log; no live database is required.
- Cover row and empty-result shape/order, manually constructed results, inconsistent/duplicate columns, representative SQL scalar round trips (`None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes), unsupported/out-of-range values, missing Polars, and row-content redaction.
- Cover last-result-set selection, SQL file encoding and binding, conversion-before-commit, rollback attempt and cleanup error on conversion failure, no automatic rollback on SQL/fetch/cursor-close failures, no automatic action for `commit=False`, and unchanged existing method behavior.
- Update `docs/database.md` and the README reference cards/export list. Run repository static checks and package checks during implementation; no new extra is required.
