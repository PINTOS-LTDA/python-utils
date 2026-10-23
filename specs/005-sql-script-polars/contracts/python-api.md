# Python API Contract

All names below are public exports from `pintos_utils.database`. Polars remains a lazy optional dependency.

## Standalone conversion

```python
def sql_script_result_to_dataframe(
    result: SqlScriptResult,
) -> polars.DataFrame: ...
```

- Requires the `polars` extra: `python -m pip install "pintos-utils[polars]"`.
- Converts only `result.rows` and `result.columns`; counts are not added as frame columns.
- Uses ordered `result.columns`. If rows exist and the list is empty, infer names from the first row's insertion order.
- Returns a zero-by-zero frame when there are no rows or known columns. Known columns with no rows remain in order; their dtypes are unspecified.
- Raises `DataFrameDatabaseError(operation="convert")` with a value-free message if Polars is missing or data cannot be represented faithfully.
- Rejects duplicate names and row mappings with missing or unexpected keys.
- Representative SQL scalar values (`None`, booleans, integers, floats including NaN, strings, `Decimal`, dates, naive datetimes, `datetime.time`, `datetime.timedelta`, and bytes) retain their Python type and value. Byte-like values compare by byte content, NaN remains NaN, and unsupported or out-of-range values fail rather than being coerced. MySQL `TIME` values from Connector/Python are durations and use `datetime.timedelta`.

## SQL string execution

```python
class SqlScriptExecutor:
    def execute_dataframe(
        self,
        script: str,
        params: Mapping[str, Any] | None = None,
        commit: bool = False,
    ) -> polars.DataFrame: ...
```

Runs the same sequential script and `:name` parameter binding as `execute()`, returning the rows and columns of its last result-producing statement. A script with no result-producing statement returns a zero-by-zero frame. SQL failures remain `SqlScriptError`; conversion failures use `DataFrameDatabaseError(operation="convert")`.

## SQL file execution

```python
class SqlScriptExecutor:
    def execute_file_dataframe(
        self,
        file_path: str | pathlib.Path,
        params: Mapping[str, Any] | None = None,
        commit: bool = False,
        encoding: str = "utf-8",
    ) -> polars.DataFrame: ...
```

Reads the file using `encoding` and then follows `execute_dataframe()` semantics. File-read and SQL errors use the existing `SqlScriptError` contract.

## Result scope and execution metadata

DataFrame-returning methods expose only the last result set's rows and columns. They do not expose `statements_executed`, `affected_rows`, or other `SqlScriptResult` metadata. When that metadata is needed, call `execute()` or `execute_file()` and pass the returned result to `sql_script_result_to_dataframe()` separately.

## Ownership and transaction rules

- The caller supplies and owns the connection. The executor closes its cursor only and never closes or replaces the connection.
- `commit=True` is rejected before SQL if the connection already has an active transaction.
- An empty or comment-only script remains a no-op and does not commit.
- DataFrame methods finish SQL execution and close the cursor, convert the result, and then commit once on success.
- If conversion fails with `commit=True`, attempt rollback before raising. Preserve rollback failure in `DataFrameDatabaseError.cleanup_exception` without replacing the conversion failure.
- With `commit=False`, do not commit or roll back, including when conversion fails.
- SQL execution, fetch, and cursor-close failures retain existing executor rollback behavior (none). Existing `execute()` and `execute_file()` continue returning `SqlScriptResult`.
- MySQL implicit commits and non-transactional tables can limit rollback effectiveness.

## Optional dependencies

Importing `pintos_utils.database`, using `SqlScriptResult`, the standalone model, and the existing non-Polars script methods must not import Polars. DataFrame executor methods require both extras: `python -m pip install "pintos-utils[mysql,polars]"`.

## Compatibility review

- `SqlScriptResult.columns` is appended after the three existing fields with an independent empty-list default. Existing three-argument positional construction is covered and retains its original meaning.
- `execute()` and `execute_file()` still return `SqlScriptResult`; they only add ordered column metadata for the last result-producing statement. Existing commit and rollback behavior is unchanged.
- `sql_script_result_to_dataframe`, `execute_dataframe`, and `execute_file_dataframe` are additive exports/API methods. Polars remains lazily imported, and the `DataFrameDatabaseError.operation` type adds `convert` while retaining `query` and `import`.
- Review outcome: no breaking API or dependency change was found. The feature is suitable for a compatible minor release.
