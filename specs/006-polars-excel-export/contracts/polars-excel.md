# Public Contract: Polars Excel Export

## Module and installation

Import both functions from `pintos_utils.polars_excel`. The module requires the
optional `polars` extra:

```bash
python -m pip install "pintos-utils[polars]"
```

The base package has no runtime dependencies and does not import this optional
module automatically.

## Functions

```python
def exportar_excel(
    df: polars.DataFrame,
    arquivo: str | pathlib.Path,
    aba: str = "Dados",
) -> None: ...

def exportar_excel_bytes(
    df: polars.DataFrame,
    aba: str = "Dados",
) -> bytes: ...
```

Both functions create a workbook with one worksheet and leave `df` unchanged.
The file operation replaces an existing writable destination. The bytes
operation creates no filesystem destination and returns a complete `.xlsx`
archive after the workbook is finalized.

## Workbook behavior

- Preserve input column and row order and values; do not silently omit data.
- Use `Dados` when `aba` is omitted; otherwise use the supplied valid worksheet
  name.
- Apply `dd/mm/yyyy` to dates, `dd/mm/yyyy hh:mm:ss` to datetimes, `hh:mm:ss`
  to times, `#,##0` to signed and unsigned integers, and `#,##0.00` to floats
  and decimals.
- When the DataFrame has one or more columns, use `Table Style Medium 2`,
  autofit columns, and enable filtering. In either case, freeze the first
  worksheet row and hide gridlines.
- Keep headings for a zero-row frame with known columns. For a frame with no
  columns, return an empty worksheet without adding a synthetic column; table
  style, filtering, and column-width settings are inapplicable without a table
  range.
- Reject a data shape that exceeds Excel's 1,048,576-row or 16,384-column
  worksheet bounds. The table header leaves 1,048,575 rows for DataFrame rows.

## Errors

Invalid destinations, worksheet names, dimensions, or unsupported values must
raise an observable exception. The API does not wrap these failures in a new
public exception type or report success with an incomplete workbook.

## Compatibility

### Compatibility review

Reviewed the public API index in `README.md`, the existing `email` and
`database` module APIs, `src/pintos_utils/polars_excel.py`, and the package
dependency metadata.

- The feature adds `pintos_utils.polars_excel.exportar_excel(df, arquivo,
  aba="Dados") -> None` and
  `pintos_utils.polars_excel.exportar_excel_bytes(df, aba="Dados") -> bytes`.
- The new names remain in the clarified module; no existing module, public name,
  or call signature changes.
- Polars and XlsxWriter are confined to the optional `polars` extra. The base
  `project.dependencies` list remains empty, and the optional module is not
  imported automatically by the package root.
- The functions propagate writer errors and introduce no public exception type.

**Review outcome**: The API addition is backward-compatible and suitable for a
minor release under Constitution II. No major-version change is required.
