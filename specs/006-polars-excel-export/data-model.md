# Data Model: Polars Excel Export

This feature introduces no persistent state or database schema. It maps one
caller-owned Polars DataFrame to one worksheet in a new Excel workbook.

## Polars DataFrame

| Property | Rule |
|---|---|
| Columns | Preserve names, order, and supported values. No synthetic column is added. |
| Rows | Preserve input order and values. A frame may have zero rows. |
| Schema | Date, datetime, time, integer, float, and decimal types use the formats in the public contract. Other types use Polars' normal Excel representation or raise an observable error. |
| Mutation | Export does not modify the input frame. |
| Bounds | A table header plus data must fit 1,048,576 worksheet rows; width must be at most 16,384 columns. |

## Excel Workbook

Each operation creates one new workbook and one worksheet. File output writes
to the caller's path. Bytes output finalizes the same workbook format in memory
and returns its complete archive bytes.

## Worksheet

The worksheet name is the supplied `aba` value or `Dados`. A frame with known
columns but no rows keeps its headings. A frame with no columns yields an empty
worksheet and no artificial table range. When a table range exists, the table
uses Medium 2, autofit, and filtering. In either case, the first worksheet row
is frozen and gridlines are hidden.
