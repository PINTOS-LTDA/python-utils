# Quickstart: Validate SQL Script Execution

This guide describes checks to run after implementation. It does not require access to a production database.

## Prerequisites

- Python 3.11 or newer and uv.
- Repository development dependencies and optional MySQL support.
- Default unit tests use fakes and do not need a MySQL server or network access.
- Optional integration tests require an explicitly configured disposable MySQL instance. Never point them at a corporate or production database.

## Install the optional feature dependencies

From a consumer environment:

```bash
pip install "pintos-utils[mysql]"
```

From the source checkout for implementation validation:

```bash
uv sync --group dev --extra mysql
```

## Consumer usage shape

The consumer creates a MySQL Connector/Python connection with application-owned configuration and secrets, then passes that connection to the executor:

```python
from pintos_utils.database import SqlScriptExecutor

executor = SqlScriptExecutor(connection)
result = executor.execute(
    "SELECT * FROM products WHERE store_id = :store_id;",
    params={"store_id": 18},
)
```

`execute_file()` accepts a `str` or `Path`, optional parameter mapping, `commit`, and text encoding. Both methods return `SqlScriptResult`. See [database-python-api.md](contracts/database-python-api.md) for the full public contract.

## Offline validation

After implementation, run the project's unit tests and static/build checks:

```bash
uv run pytest
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src/pintos_utils
uv build
```

Expected outcome: tests complete without network access; Ruff, mypy, and the Hatchling package build succeed. Fake connection/cursor tests should verify same-session statement order and transaction boundaries. These checks do not prove compatibility with a live server.

## Transaction scenarios to verify

- `commit=False` never calls `commit()` and never triggers automatic rollback.
- A non-empty `commit=True` request with `connection.in_transaction` already true raises before cursor creation or SQL execution; the transaction and connection remain untouched.
- A non-empty `commit=True` request with no transaction active executes all statements and calls `commit()` once after success.
- An empty/ordinary-comment-only script performs no SQL and does not commit; MySQL executable comments are rejected.
- A script containing explicit transaction-control SQL, a `SET` assignment to system `autocommit`, or an actual MySQL executable comment is rejected in preflight before any SQL statement, regardless of the `commit` argument. Test recognized scope qualifiers and assignment operators, and verify that ordinary strings, ordinary comments, quoted identifiers, `@autocommit`, and the `/*!` sequence inside a string do not trigger false positives.
- A statement failure stops later statements; the executor does not roll back or close the consumer's connection.
- The executor closes its cursor on success and failure.

## Optional disposable-MySQL verification

Configure a local or ephemeral MySQL database with credentials supplied only through local environment or a secret manager. Run the integration test path explicitly. Create a temporary table in one statement and query it in a later statement on the same connection. Verify with the actual driver that an active transaction is rejected before SQL for `commit=True` and remains active, successful DML is committed once for `commit=True`, and `commit=False` does not commit; keep a second connection available to observe committed visibility and use caller rollback for cleanup. Use DML for the transaction assertions so DDL implicit commits do not distort them. Never target a production or corporate database.

MySQL DDL can implicitly commit, and temporary-table changes may not be rollbackable. Read [MySQL implicit-commit rules](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html) before interpreting an integration result as evidence of atomicity; the executor does not promise script-level atomicity.
