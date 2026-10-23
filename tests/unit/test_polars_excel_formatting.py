from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
import xlsxwriter
from _polars_excel_xml import (
    NS,
    cell_number_format,
    cell_value,
    table_xml,
    workbook_xml,
)

import pintos_utils.polars_excel as polars_excel
from pintos_utils.polars_excel import exportar_excel


def formatted_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "data": [date(2024, 1, 2)],
            "data_hora": [datetime(2024, 1, 2, 3, 4, 5)],
            "hora": [time(3, 4, 5)],
            "int8": pl.Series([12], dtype=pl.Int8),
            "int16": pl.Series([1234], dtype=pl.Int16),
            "int32": pl.Series([12345], dtype=pl.Int32),
            "int64": pl.Series([123456], dtype=pl.Int64),
            "uint8": pl.Series([12], dtype=pl.UInt8),
            "uint16": pl.Series([1234], dtype=pl.UInt16),
            "uint32": pl.Series([12345], dtype=pl.UInt32),
            "uint64": pl.Series([123456], dtype=pl.UInt64),
            "float32": pl.Series([1234.5], dtype=pl.Float32),
            "float64": pl.Series([1234.5], dtype=pl.Float64),
            "decimal": pl.Series(
                [Decimal("1234.50")], dtype=pl.Decimal(precision=10, scale=2)
            ),
        }
    )


def test_applies_number_formats_table_style_autofit_and_worksheet_settings(
    tmp_path: Path,
) -> None:
    path = tmp_path / "formatos.xlsx"
    frame = formatted_frame()
    original = frame.clone()

    exportar_excel(frame, path)
    payload = path.read_bytes()

    expected_formats = {
        "A2": "dd/mm/yyyy",
        "B2": "dd/mm/yyyy hh:mm:ss",
        "C2": "hh:mm:ss",
        "D2": "#,##0",
        "E2": "#,##0",
        "F2": "#,##0",
        "G2": "#,##0",
        "H2": "#,##0",
        "I2": "#,##0",
        "J2": "#,##0",
        "K2": "#,##0",
        "L2": "#,##0.00",
        "M2": "#,##0.00",
        "N2": "#,##0.00",
    }
    assert {
        cell: cell_number_format(payload, cell) for cell in expected_formats
    } == expected_formats

    table = table_xml(payload)
    assert table is not None
    style = table.find("main:tableStyleInfo", NS)
    assert style is not None and style.attrib["name"] == "TableStyleMedium2"
    assert table.find("main:autoFilter", NS) is not None

    worksheet = workbook_xml(payload, "xl/worksheets/sheet1.xml")
    sheet_view = worksheet.find("main:sheetViews/main:sheetView", NS)
    assert sheet_view is not None and sheet_view.attrib["showGridLines"] == "0"
    pane = sheet_view.find("main:pane", NS)
    assert pane is not None
    assert pane.attrib["state"] == "frozen"
    assert pane.attrib["ySplit"] == "1"
    columns = worksheet.findall("main:cols/main:col", NS)
    assert columns
    assert any(float(column.attrib["width"]) > 10 for column in columns)
    assert frame.equals(original)


def test_zero_row_frame_retains_headings_and_table(tmp_path: Path) -> None:
    path = tmp_path / "sem_linhas.xlsx"
    frame = pl.DataFrame(schema={"produto": pl.String, "quantidade": pl.Int64})

    exportar_excel(frame, path)

    payload = path.read_bytes()
    assert cell_value(payload, "A1") == "produto"
    assert cell_value(payload, "B1") == "quantidade"
    assert cell_value(payload, "A2") is None
    assert table_xml(payload) is not None


def test_zero_column_frame_has_empty_sheet_without_table_and_keeps_sheet_settings(
    tmp_path: Path,
) -> None:
    path = tmp_path / "vazio.xlsx"

    exportar_excel(pl.DataFrame(), path)

    payload = path.read_bytes()
    assert table_xml(payload) is None
    worksheet = workbook_xml(payload, "xl/worksheets/sheet1.xml")
    assert worksheet.find("main:sheetData/main:row", NS) is None
    sheet_view = worksheet.find("main:sheetViews/main:sheetView", NS)
    assert sheet_view is not None and sheet_view.attrib["showGridLines"] == "0"
    pane = sheet_view.find("main:pane", NS)
    assert pane is not None and pane.attrib["state"] == "frozen"
    assert pane.attrib["ySplit"] == "1"


def test_invalid_destination_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "relatorio.xlsx"

    with pytest.raises(xlsxwriter.exceptions.FileCreateError):
        exportar_excel(pl.DataFrame({"a": [1]}), path)


def test_invalid_worksheet_name_is_reported(tmp_path: Path) -> None:
    with pytest.raises(xlsxwriter.exceptions.InvalidWorksheetName):
        exportar_excel(pl.DataFrame({"a": [1]}), tmp_path / "bad.xlsx", aba="bad/name")


def test_rejects_too_many_rows_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(polars_excel, "_MAX_WORKSHEET_ROWS", 2)
    path = tmp_path / "too_many_rows.xlsx"

    with pytest.raises(ValueError, match="Excel"):
        exportar_excel(pl.DataFrame({"a": [1, 2]}), path)

    assert not path.exists()


def test_rejects_too_many_columns_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(polars_excel, "_MAX_WORKSHEET_COLUMNS", 1)
    path = tmp_path / "too_many_columns.xlsx"

    with pytest.raises(ValueError, match="Excel"):
        exportar_excel(pl.DataFrame({"a": [1], "b": [2]}), path)

    assert not path.exists()


def test_unsupported_binary_values_raise_an_observable_error(tmp_path: Path) -> None:
    frame = pl.DataFrame({"conteudo": [b"bytes"]})

    with pytest.raises(TypeError):
        exportar_excel(frame, tmp_path / "binary.xlsx")


def test_export_does_not_mutate_input_dataframe(tmp_path: Path) -> None:
    frame = formatted_frame()
    original = frame.clone()

    exportar_excel(frame, tmp_path / "imutavel.xlsx")

    assert frame.equals(original)
