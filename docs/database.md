# Database script execution

`pintos_utils.database.SqlScriptExecutor` runs conventional MySQL statements
sequentially through a connection created by the consuming application. A call
uses one connection and session, so `USE` and temporary tables remain available
to later statements in the same script.

## Installation

Install the optional MySQL driver and SQL statement splitter from PyPI:

```bash
python -m pip install "pintos-utils[mysql]"
```

For a local editable checkout:

```bash
uv pip install -e ".[mysql]"
```

For a private Git repository, configure SSH access in the consuming environment
and use a tag or commit reference. Do not embed credentials in the URL:

```bash
uv pip install "pintos-utils[mysql] @ git+ssh://git@<git-host>/<org>/pintos-utils.git@<tag-or-commit>"
```

The base package and email module do not import MySQL dependencies. Importing
`pintos_utils.database` is also possible without the extra; executing a non-empty
script requires it.

## Create and own the connection

The application supplies the connection and credentials. The executor does not
open or close connections, change `autocommit`, or perform automatic rollback.

```python
import os

import mysql.connector

from pintos_utils.database import SqlScriptExecutor

connection = mysql.connector.connect(
    host=os.environ["MYSQL_HOST"],
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
    database=os.environ["MYSQL_DATABASE"],
)

try:
    executor = SqlScriptExecutor(connection)
    result = executor.execute(
        "SELECT sku, quantity FROM products WHERE store_id = :store_id;",
        params={"store_id": 18},
    )
    for row in result.rows:
        print(row)
finally:
    connection.close()
```

## Execute a SQL file

`execute_file()` accepts a `str` or `Path`, a parameter mapping, a commit option,
and a text encoding (UTF-8 by default):

```python
from datetime import date
from pathlib import Path

result = executor.execute_file(
    Path("reports/replenishments.sql"),
    params={"data": date(2026, 10, 1), "loja": 18},
)
```

Every non-empty statement runs in source order using the same connection. For
example, a script may create a temporary table and then query it:

```sql
CREATE TEMPORARY TABLE report_items (
    sku VARCHAR(120) PRIMARY KEY,
    quantity INT NOT NULL
);

INSERT INTO report_items (sku, quantity)
VALUES (:sku, :quantity);

SELECT sku, quantity FROM report_items;
```

The executor returns only the rows from the last statement that produced a
result set. It consumes earlier result sets before the next statement. All rows
from the last result set are materialized in memory, so avoid unbounded or very
large queries.

`SqlScriptResult` exposes:

- `statements_executed`: number of statements that completed successfully.
- `rows`: rows from the last result-producing statement, or an empty list.
- `affected_rows`: sum of non-negative row counts reported for DML statements.

## Named values and safety

Use `:name` markers for values. Names follow
`[A-Za-z_][A-Za-z0-9_]*`; repeated markers use the same supplied value.
Values are passed separately to Connector/Python and are never interpolated
into SQL text. Supported Python values such as strings, numbers, `Decimal`,
`date`, `datetime`, and `None` are left for the driver to convert.

```python
result = executor.execute(
    "SELECT * FROM products WHERE updated_at >= :since AND store_id = :store;",
    params={"since": date(2026, 10, 1), "store": 18},
)
```

Markers represent values only. They cannot replace table or column names;
identifiers must remain fixed in SQL or be selected by the caller from a safe
allowlist. Text resembling a marker inside a quoted string, a backtick
identifier, or an ordinary SQL comment is left unchanged. Extra mapping keys
that are not referenced by the script are ignored. Missing values are detected
before any statement runs.

The v1 parser rejects actual MySQL executable comments such as
`/*!80000 SET autocommit=0 */` before sending any SQL. The same character
sequence inside a string or quoted identifier is preserved. Do not use
executable comments as a workaround for the parser boundary.

## Transactions and errors

- `commit=False` never calls `connection.commit()` and never issues rollback.
- `commit=True` with an empty or ordinary-comment-only script is a no-op.
- For a non-empty script with `commit=True`, an already-active transaction is
  rejected before any SQL is sent. The consumer must finish that transaction
  before retrying.
- Otherwise, `commit=True` calls `connection.commit()` once after every
  statement succeeds.
- If a statement, result read, cursor operation, or commit fails, execution
  stops. The executor does not roll back or close the supplied connection; the
  consumer decides whether and when to roll back.
- Scripts cannot issue `START TRANSACTION`, `BEGIN`, `COMMIT`, `ROLLBACK`,
  `SAVEPOINT`, `RELEASE SAVEPOINT`, `SET TRANSACTION`, or assignments to the
  server system variable `autocommit`. These commands are rejected before any
  statement executes.

`SqlScriptError` is the public exception type. When a statement is known, it
exposes its one-based `statement_index` and source `statement`. Driver failures
are available through `original_exception` and the chained `__cause__`. Default
logs and exception messages do not include bound values; SQL text may be
attached to the error for diagnosis.

`commit=True` does not guarantee script-level atomicity. MySQL can implicitly
commit DDL and other statements. Temporary-table DDL may avoid an implicit
commit but its effects are not necessarily rollbackable. `commit=False` cannot
override server-side implicit commits.

## Supported input and limitations

The v1 executor supports conventional `USE`, `SELECT`, `INSERT`, `UPDATE`,
`DELETE`, `CREATE TEMPORARY TABLE`, and `DROP TEMPORARY TABLE` statements. It
uses `sqlparse` to split statements and a small lexical scanner for named
markers and transaction preflight; it is not a MySQL syntax validator.

Stored procedures, trigger bodies, client-side `DELIMITER` directives, and
MySQL executable comments are not supported. The parser does not promise correct
handling of compound statements that require a client-side delimiter command.

The module uses Python's standard `logging` logger and does not configure the
consuming application's logging system. DEBUG records report execution progress
and durations without logging SQL text or parameter values.

## Optional MySQL integration tests

Unit tests use fakes and do not need a server. The integration tests are opt-in
and require an explicitly configured disposable database whose name starts with
`test_` or ends with `_test`. Set these environment variables in a local test
environment:

```text
PINTOS_UTILS_MYSQL_TEST_DISPOSABLE=1
PINTOS_UTILS_MYSQL_TEST_HOST=127.0.0.1
PINTOS_UTILS_MYSQL_TEST_PORT=3306
PINTOS_UTILS_MYSQL_TEST_USER=...
PINTOS_UTILS_MYSQL_TEST_PASSWORD=...
PINTOS_UTILS_MYSQL_TEST_DATABASE=test_pintos_utils
```

Then run:

```bash
uv run --extra mysql pytest tests/integration/database/test_sql_script_executor_mysql.py
```

Never point these tests at a corporate or production database. The tests create
temporary tables and a uniquely named disposable table, then remove the table
after transaction visibility checks.
