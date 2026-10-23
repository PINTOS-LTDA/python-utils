"""Export Polars DataFrames to formatted Excel workbooks."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, cast

import polars as pl
import xlsxwriter  # type: ignore[import-untyped]

_MAX_WORKSHEET_ROWS = 1_048_576
_MAX_WORKSHEET_COLUMNS = 16_384

_FORMATS = {
    pl.Date: "dd/mm/yyyy",
    pl.Datetime: "dd/mm/yyyy hh:mm:ss",
    pl.Time: "hh:mm:ss",
    pl.Int8: "#,##0",
    pl.Int16: "#,##0",
    pl.Int32: "#,##0",
    pl.Int64: "#,##0",
    pl.UInt8: "#,##0",
    pl.UInt16: "#,##0",
    pl.UInt32: "#,##0",
    pl.UInt64: "#,##0",
    pl.Float32: "#,##0.00",
    pl.Float64: "#,##0.00",
    pl.Decimal: "#,##0.00",
}


def _validate_dimensions(df: pl.DataFrame) -> None:
    if df.width > _MAX_WORKSHEET_COLUMNS:
        raise ValueError(
            f"DataFrame has {df.width} columns; Excel worksheets support at most "
            f"{_MAX_WORKSHEET_COLUMNS}."
        )

    data_row_limit = _MAX_WORKSHEET_ROWS - (1 if df.width else 0)
    if df.height > data_row_limit:
        raise ValueError(
            f"DataFrame has {df.height} rows; Excel worksheets support at most "
            f"{data_row_limit} data rows with a heading row."
        )


def _column_formats(df: pl.DataFrame) -> dict[str, str]:
    return {
        name: _FORMATS[dtype.base_type()]
        for name, dtype in df.schema.items()
        if dtype.base_type() in _FORMATS
    }


def _write_excel(
    df: pl.DataFrame,
    destination: str | Path | BytesIO,
    worksheet_name: str,
) -> None:
    _validate_dimensions(df)

    with xlsxwriter.Workbook(destination) as workbook:
        if df.width == 0:
            worksheet = workbook.add_worksheet(worksheet_name)
            worksheet.freeze_panes(1, 0)
            worksheet.hide_gridlines(2)
            return

        df.write_excel(
            workbook=workbook,
            worksheet=worksheet_name,
            table_style="Table Style Medium 2",
            column_formats=cast(Any, _column_formats(df)),
            autofit=True,
            autofilter=True,
            freeze_panes=(1, 0),
            hide_gridlines=True,
            float_precision=2,
        )


def exportar_excel(
    df: pl.DataFrame,
    arquivo: str | Path,
    aba: str = "Dados",
) -> None:
    """Exporta um DataFrame Polars para um arquivo Excel no disco."""
    _write_excel(df, arquivo, aba)


def exportar_excel_bytes(
    df: pl.DataFrame,
    aba: str = "Dados",
) -> bytes:
    """Retorna o workbook Excel completo como bytes, sem criar arquivo."""
    buffer = BytesIO()
    _write_excel(df, buffer, aba)
    return buffer.getvalue()
