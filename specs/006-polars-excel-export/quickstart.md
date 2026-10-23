# Quickstart: Validate Polars Excel Export

## Prerequisites

- Python 3.11 or newer
- The repository checkout with the feature implementation
- The `dev` dependency group and `polars` extra

From the repository root, install the locked development environment:

```bash
uv sync --locked --group dev --extra polars
```

## Exercise both output modes

Use a DataFrame with at least one column and row. The following consumer calls
cover a path and in-memory workbook using the same optional worksheet name:

```python
from pathlib import Path

import polars as pl

from pintos_utils.polars_excel import exportar_excel, exportar_excel_bytes

frame = pl.DataFrame({"produto": ["Café"], "quantidade": [3]})
exportar_excel(frame, Path("relatorio.xlsx"), aba="Resumo")
payload = exportar_excel_bytes(frame, aba="Resumo")
```

Expected outcome: `relatorio.xlsx` exists; `payload` is a complete `.xlsx`
archive; both contain the same row, columns, worksheet name, table style, and
formats. The bytes call creates no additional file. Omitting `aba` produces a
worksheet named `Dados`.

## Run deterministic feature checks

```bash
uv run pytest tests/unit/test_polars_excel_file.py tests/unit/test_polars_excel_formatting.py tests/unit/test_polars_excel_bytes.py tests/unit/database/test_dataframe_optional.py
uv run ruff check src/pintos_utils/polars_excel.py tests/unit/test_polars_excel_file.py tests/unit/test_polars_excel_formatting.py tests/unit/test_polars_excel_bytes.py
uv run mypy src
```

The feature tests should inspect the workbook ZIP/XML contents using the
standard library and cover file and bytes outputs, `str` and `Path`
destinations, worksheet settings, number formats, empty frames,
unsupported-value and invalid-input errors, and the unchanged input frame in
both output modes.
They must not require Excel desktop software or network access.

## Run the repository quality gate

```bash
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/release_preflight.py
uv build --no-sources
```

Expected outcome: unit tests, static checks, and package build pass with the
optional extra installed; package metadata keeps Polars and XlsxWriter out of
the base dependency list.
