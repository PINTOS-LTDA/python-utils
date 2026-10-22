# Quickstart: Polars DataFrame Database Integration

This is the planned consumer workflow for the feature. The source implementation and package extras are produced later from the approved task list.

## Install

```bash
python -m pip install "pintos-utils[mysql,polars]"
```

The base package remains usable without either extra. The application creates, owns, and closes its MySQL connection.

## Query SQL into a Polars DataFrame

```python
import os

import mysql.connector

from pintos_utils.database import query_dataframe

connection = mysql.connector.connect(
    host=os.environ["MYSQL_HOST"],
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
    database=os.environ["MYSQL_DATABASE"],
)

try:
    products = query_dataframe(
        connection,
        "SELECT sku, quantity FROM products WHERE store_id = :store_id",
        params={"store_id": 18},
    )
    print(products)
finally:
    connection.close()
```

The query operation owns and commits its transaction after materializing a single result set. It rejects an already-active transaction, SQL transaction controls, implicit-commit statement forms, stored procedure calls, and multiple statements. An additional result set causes failure before commit and rollback is attempted. A single statement may change data and return rows, such as a `SELECT` that calls a data-modifying MySQL stored function. The consumer must ensure those side effects affect only transactional tables in the same connection; effects on nontransactional tables or external systems are outside the rollback guarantee. The operation leaves the connection open. Empty results retain column names and order; their dtypes are not part of the guarantee.

## Import with APPEND

```python
import polars as pl

from pintos_utils.database import ImportMode, import_dataframe

incoming = pl.DataFrame(
    {
        "sku": ["A-100", "B-200"],
        "quantity": [12, 7],
    }
)
result = import_dataframe(
    connection,
    incoming,
    "products",
    mode=ImportMode.APPEND,
    batch_size=1000,
)
print(result.rows_processed, result.batches_processed)
```

APPEND sends bounded, parameterized batches inside one transaction and commits once after all batches succeed. A failed batch rolls back the full import.

## Import with UPSERT

```python
updates = pl.DataFrame(
    {
        "sku": ["A-100", "C-300"],
        "quantity": [15, 4],
    }
)
result = import_dataframe(
    connection,
    updates,
    "products",
    mode=ImportMode.UPSERT,
    key_columns=["sku"],
)
```

The target must be an existing transaction-capable base table, and `sku` must be a complete primary or unique key. UPSERT rejects null or duplicate input keys. It stages rows in a session temporary table, updates rows matched by the supplied key, inserts unmatched rows, drops staging, and commits once. Other unique-key conflicts fail and roll back; the operation does not retry concurrency conflicts.

## Boundaries

- Use the connection's selected schema and pass an unqualified target table name.
- Import columns map by exact name. Omitted target columns use their MySQL defaults and constraints.
- Values that could be truncated or converted lossily fail before commit. Nested/object values, timezone-aware datetimes, and non-microsecond temporal values are not supported by the initial conversion policy.
- Query results are fully materialized in memory. Do not use this operation for unbounded result sets.
- Query rollback covers changes that participate in the operation-owned transaction. Ensure any data-changing statement or stored-function side effect uses transactional tables in the same connection; nontransactional and external effects cannot be rolled back by this API.
- Do not pass a connection with an active caller transaction; finish that work before invoking the feature.
