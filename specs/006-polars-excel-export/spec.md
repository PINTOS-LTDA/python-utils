# Feature Specification: Polars Excel Export

**Feature Branch**: `006-polars-excel-export`
**Created**: 2026-10-23
**Status**: Draft
**Input**: User request: "Incorporate the functions from `/home/ivaneyvieira/git/processaResultadoOneBeat/polars_excel.py` into the project."

## Clarifications

### Session 2026-10-23

- Q: Qual módulo público deve conter e expor `exportar_excel` e `exportar_excel_bytes`? → A: As duas funções ficam disponíveis no módulo público `pintos_utils.polars_excel` (opção A).

## User Scenarios & Testing

### User Story 1 - Export a Polars DataFrame to an Excel file (Priority: P1)

As an application developer, I can export a Polars DataFrame to an `.xlsx` file so that I can share or archive the tabular data in a spreadsheet with useful formatting.

**Why this priority**: A file on disk is the primary export flow and covers users who need a standalone workbook.

**Independent Test**: Export a DataFrame containing representative values to a temporary `.xlsx` file, then inspect the workbook to verify its worksheet, rows, columns, and displayed number formats.

**Acceptance Scenarios**:

1. **Given** a DataFrame with columns and rows, **When** the user exports it to a file, **Then** the resulting workbook opens and contains all input rows and columns in their original order.
2. **Given** the user omits the worksheet name, **When** the user exports the DataFrame, **Then** the worksheet is named `Dados`.
3. **Given** the user supplies a valid worksheet name, **When** the user exports the DataFrame, **Then** the workbook uses that name.
4. **Given** date, datetime, time, integer, floating-point, or decimal columns, **When** the workbook is opened, **Then** their cells use the corresponding date, time, or numeric display format defined by the supplied source behavior.
5. **Given** an accessible destination path already contains a file, **When** the user exports to that path, **Then** the destination contains the newly generated workbook.
6. **Given** a DataFrame with one or more columns, **When** the user opens its generated workbook, **Then** it has a Medium 2 table style, columns sized to their contents, and filtering controls. The first worksheet row is frozen and gridlines are hidden in both output modes.
7. **Given** a DataFrame with headings and no rows, **When** the user exports it, **Then** the workbook retains those headings without inventing data rows.

### User Story 2 - Obtain an Excel workbook as bytes (Priority: P2)

As an application developer, I can obtain the same kind of Excel workbook as bytes so that my application can pass it to another component without first creating a temporary file.

**Why this priority**: In-memory output supports applications that decide themselves how to store, send, or deliver the generated workbook.

**Independent Test**: Export a DataFrame to bytes, confirm the result is a complete readable workbook with the same data and formatting as file output, and verify that the operation creates no file.

**Acceptance Scenarios**:

1. **Given** a DataFrame with columns and rows, **When** the user requests the workbook as bytes, **Then** the result contains a complete `.xlsx` workbook with all input rows and columns in their original order.
2. **Given** the user omits or supplies a worksheet name, **When** the user requests bytes, **Then** the workbook uses the same default or supplied name as file output.
3. **Given** the user requests bytes, **When** the operation completes, **Then** no destination file is created as a side effect.
4. **Given** either output mode, **When** the input contains values unsupported by the workbook format, **Then** the operation reports an error instead of silently omitting data.
5. **Given** a consumer installs the documented optional spreadsheet capability, **When** the consumer imports and calls either export operation, **Then** the feature is available without adding spreadsheet dependencies to the base installation.
6. **Given** a consumer follows the package documentation, **When** they choose either output mode, **Then** they can find an example, the optional installation instructions, and the default and custom worksheet behavior.
7. **Given** a consumer imports the export operations, **When** they import both names from `pintos_utils.polars_excel`, **Then** both public operations are available from that module.

### Edge Cases

- A DataFrame with zero rows but known columns exports a valid workbook that retains the column headings.
- An empty DataFrame with no columns exports a valid worksheet without a synthetic column; table styling, filtering, and column autofit do not apply without a table range, while the first worksheet row remains frozen and gridlines are hidden.
- A path that cannot be opened for writing or an invalid worksheet name produces an observable error; the operation does not report success or return an incomplete workbook.
- Values or types unsupported by the spreadsheet writer produce an observable error rather than silently dropping rows or columns.
- Exporting a DataFrame does not modify the caller's DataFrame.

## Requirements

### Functional Requirements

- **FR-001**: The package MUST expose a public operation named `exportar_excel` from `pintos_utils.polars_excel`; it writes a Polars DataFrame to an `.xlsx` destination supplied as a string or path.
- **FR-002**: The package MUST expose a public operation named `exportar_excel_bytes` from `pintos_utils.polars_excel`; it returns the generated `.xlsx` workbook as `bytes` without requiring a destination path.
- **FR-003**: Both operations MUST accept an optional worksheet name, default it to `Dados`, and apply the selected name to the workbook's single worksheet.
- **FR-004**: Both output modes MUST contain the DataFrame's columns and rows in source order and MUST NOT silently omit data.
- **FR-005**: Excel display formats MUST follow the supplied source behavior: dates as `dd/mm/yyyy`, datetimes as `dd/mm/yyyy hh:mm:ss`, times as `hh:mm:ss`, signed and unsigned 8-, 16-, 32-, and 64-bit integers with grouped thousands and no decimal places, and 32- and 64-bit floating-point or decimal values with grouped thousands and two decimal places.
- **FR-006**: When the DataFrame has one or more columns, the workbook MUST use the Medium 2 table style, automatically size columns to their contents, and include filtering controls. In both output modes, the workbook MUST freeze the first worksheet row and hide worksheet gridlines.
- **FR-007**: The bytes-returning operation MUST finalize and return a complete workbook that can be opened independently of any file export.
- **FR-008**: The operations MUST NOT mutate the input DataFrame.
- **FR-009**: Export support MUST remain optional; installing or importing the package's base capabilities MUST NOT require spreadsheet-export dependencies. The supported optional installation path MUST be documented.
- **FR-010**: Public documentation MUST show file and in-memory examples, the default and custom worksheet name, optional installation requirements, and the behavior for unsupported data or destinations.

### Key Entities

- **Polars DataFrame**: The input table whose column names, order, values, and row order are represented in the workbook.
- **Excel workbook**: A spreadsheet document containing one worksheet for the DataFrame, with its headings, data, and presentation settings.
- **Worksheet name**: The name chosen by the consumer or the default `Dados` for the workbook's worksheet.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In both output modes, 100% of tested supported input rows and columns appear in the workbook in the same order and with their values preserved.
- **SC-002**: In 100% of tested cases, an omitted worksheet name produces `Dados` and a valid supplied name is used.
- **SC-003**: Every tested date, datetime, time, integer, floating-point, and decimal column displays using the format specified in FR-005.
- **SC-004**: In-memory export returns a workbook that can be opened and inspected, without creating a filesystem output file.
- **SC-005**: Existing users can use the package without opting into spreadsheet exports, and users who opt in can use both output modes.
- **SC-006**: Users can complete either export workflow with one documented function call and no manual conversion step.

## Assumptions

- The user-provided `polars_excel.py` is the behavioral reference for both export operations, including their public function names, worksheet default, formats, and workbook presentation.
- Exporting to an existing writable destination replaces that destination with the new workbook, matching the supplied function's behavior.
- The feature exports one DataFrame to one worksheet per operation; importing workbooks, adding multiple worksheets, and customizing workbook styles are outside this feature.
- Spreadsheet export dependencies remain optional and will be grouped into a documented installation extra during planning; the base package remains dependency-free at runtime.
- Data types not covered by the supplied formatting rules use the spreadsheet writer's normal representation, while unsupported values must fail visibly rather than be silently discarded.
- The public API addition is backward-compatible; release compatibility and version impact will be reviewed under the project's Semantic Versioning policy.
