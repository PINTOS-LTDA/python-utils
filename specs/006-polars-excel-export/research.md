# Research: Polars Excel Export

## Decision: Use Polars `DataFrame.write_excel` with XlsxWriter

**Rationale**: The supplied helper already delegates value serialization to
`DataFrame.write_excel` and passes a caller-owned XlsxWriter workbook. Polars
documents support for a path, a binary IO object such as `BytesIO`, or an open
XlsxWriter `Workbook`. This matches the file and memory destinations without a
second serialization path. Polars also documents XlsxWriter as an additional
dependency for Excel writing.

**Alternatives considered**:

- Write every cell directly through XlsxWriter: rejected because it would
  duplicate Polars dtype conversion and table-writing behavior.
- Use an Excel-reading feature group: rejected because this feature only writes
  workbooks and does not need spreadsheet reader packages.

**Sources**:

- [Polars `DataFrame.write_excel` API](https://docs.pola.rs/api/python/version/1/reference/api/polars.DataFrame.write_excel.html)
- [Polars Excel user guide](https://docs.pola.rs/user-guide/io/excel/)
- [XlsxWriter: Working with Polars](https://xlsxwriter.readthedocs.io/working_with_polars.html)

## Decision: Extend the existing optional `polars` extra

**Rationale**: `pyproject.toml` already declares `polars>=1.0,<3` in the
`polars` extra. Add `xlsxwriter>=3.0.8,<4` to that same extra. Polars' current
implementation requires XlsxWriter 3.0.8 or newer for `autofit=True`. This keeps
both runtime dependencies out of the base installation and avoids pulling
unneeded Excel readers.

**Alternatives considered**:

- Add a second `polars-excel` extra: rejected because the existing extra is the
  project's installation group for Polars APIs and CI already installs it.
- Use an unconstrained XlsxWriter dependency or Polars' broader `excel` feature
  group: rejected because the first omits the documented autofit minimum and
  the second includes read-side engines outside scope.

**Sources**:

- [Polars 2.0 `write_excel` implementation](https://github.com/pola-rs/polars/blob/py-2.0.0/py-polars/src/polars/dataframe/frame.py)
- [Polars optional feature guidance](https://docs.pola.rs/user-guide/installation/#feature-flags)
- [XlsxWriter package metadata](https://pypi.org/project/XlsxWriter/)

## Decision: Finalize the workbook before returning bytes

**Rationale**: An `.xlsx` file is a ZIP archive. Use the same XlsxWriter context
for both output modes, pass `BytesIO` for memory output, close the workbook, and
then return `buffer.getvalue()`. This follows the source helper's shared-writer
shape and prevents returning an unfinished archive.

**Alternatives considered**:

- Create a separate formatting implementation for bytes: rejected because it
  could diverge from file output.
- Return the workbook object: rejected because the public spec requires complete
  `bytes`.

**Sources**:

- [Polars `DataFrame.write_excel` API](https://docs.pola.rs/api/python/version/1/reference/api/polars.DataFrame.write_excel.html)
- [XlsxWriter workbook lifecycle](https://xlsxwriter.readthedocs.io/workbook.html)

## Decision: Treat zero-column frames and Excel bounds explicitly

**Rationale**: A zero-row frame with known columns can still write its header
table. A zero-column frame has no valid table range, so create a named empty
worksheet directly and do not invent a column. XlsxWriter documents worksheet
limits of 1,048,576 rows by 16,384 columns. Because this feature writes a table
header, reject more than 1,048,575 data rows or 16,384 columns before writing;
this avoids silently producing an incomplete workbook.

For the zero-column case, table styling, filtering, and column sizing are
inapplicable because there is no table range. The first worksheet row can still
be frozen and gridlines hidden. This is the design interpretation of the spec's
requirement for a valid empty worksheet and no invented columns.

**Alternatives considered**:

- Silently truncate a frame that is larger than Excel's bounds: rejected because
  it violates FR-004.
- Add a placeholder column for a zero-column frame: rejected because it invents
  data structure absent from the input.

**Sources**:

- [Polars 2.0 `write_excel` implementation](https://github.com/pola-rs/polars/blob/py-2.0.0/py-polars/src/polars/dataframe/frame.py)
- [XlsxWriter worksheet limits](https://xlsxwriter.readthedocs.io/working_with_cell_notation.html)

## Known limitation

Polars' `autofit=True` estimates column widths; XlsxWriter documents that
autofitting scans populated cells and has font and number-format limitations.
The feature preserves this behavior because the source helper and FR-006 require
it. The project makes no performance or pixel-perfect width guarantee.

**Source**: [XlsxWriter worksheet autofit](https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-autofit)
