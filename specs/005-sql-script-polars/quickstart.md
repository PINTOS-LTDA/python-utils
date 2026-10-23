# Quickstart: SQL Script Results as Polars DataFrames

This guide defines implementation-time checks for the feature. It uses offline unit fakes and does not require MySQL to be running.

## Prerequisites

From the repository root, install the development dependencies and the optional database extras:

```bash
uv sync --locked --group dev --extra mysql --extra polars
```

## Validate the conversion and executor contracts

The implementation should provide focused tests for standalone results and executor behavior:

```bash
uv run --extra mysql --extra polars pytest \
  tests/unit/database/test_sql_script_result_dataframe.py \
  tests/unit/database/test_sql_script_executor_dataframe.py
```

Expected coverage includes:

- Populated rows with preserved row and column order.
- Empty results with known columns and empty results without schema.
- A manually constructed result whose columns come from the first row's keys.
- Inconsistent rows, duplicate names, and a value Polars cannot preserve faithfully.
- Missing-Polars error messages and safe logs without row contents.
- A script with multiple statements where a later non-result statement does not erase the final result set.
- SQL file encoding and bound parameters.
- `commit=True` ordering: conversion before commit; rollback attempt on conversion failure.
- `commit=False` performs neither commit nor rollback; existing script APIs retain their contract.

The successful populated conversion should have the same columns, order, row count, and values as the source result. A known-schema empty result should have shape `(0, number_of_columns)`. An empty result without columns should have shape `(0, 0)`.

## Run repository checks

```bash
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/release_preflight.py
uv build --no-sources
```

The shared quality workflow in `.github/workflows/_quality.yml` also verifies wheel and source distribution metadata. The unit suite includes package metadata and subprocess checks that Polars remains optional and imports remain safe when Polars cannot be imported. These are implementation gates; they were not run as part of planning.
