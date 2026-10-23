from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import pytest
from _polars_excel_xml import (
    NS,
    cell_number_format,
    cell_value,
    table_xml,
    workbook_xml,
    worksheet_name,
)

from pintos_utils.polars_excel import exportar_excel, exportar_excel_bytes


@pytest.mark.parametrize("worksheet", [None, "Resumo"])
def test_bytes_output_is_complete_and_uses_default_or_custom_name(
    worksheet: str | None,
) -> None:
    frame = pl.DataFrame({"produto": ["Café"], "quantidade": [3]})

    payload = (
        exportar_excel_bytes(frame)
        if worksheet is None
        else exportar_excel_bytes(frame, aba=worksheet)
    )

    with ZipFile(BytesIO(payload)) as archive:
        assert archive.testzip() is None
    assert worksheet_name(payload) == (worksheet or "Dados")
    assert cell_value(payload, "A2") == "Café"
    assert cell_value(payload, "B2") == "3"
    assert table_xml(payload) is not None


def test_bytes_output_matches_file_output_without_creating_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = pl.DataFrame(
        {
            "produto": ["A-1"],
            "data": [date(2024, 1, 2)],
            "data_hora": [datetime(2024, 1, 2, 3, 4, 5)],
            "hora": [time(3, 4, 5)],
            "quantidade": pl.Series([1234], dtype=pl.Int32),
            "preco": pl.Series([12.345], dtype=pl.Float64),
            "decimal": pl.Series(
                [Decimal("1.25")], dtype=pl.Decimal(precision=10, scale=2)
            ),
        }
    )
    original = frame.clone()
    path = tmp_path / "arquivo.xlsx"
    exportar_excel(frame, path, aba="Produtos")

    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    payload = exportar_excel_bytes(frame, aba="Produtos")

    assert set(tmp_path.iterdir()) == before
    assert worksheet_name(payload) == worksheet_name(path.read_bytes()) == "Produtos"
    cells = ("A2", "B2", "C2", "D2", "E2", "F2", "G2")
    assert [cell_value(payload, cell) for cell in cells] == [
        cell_value(path.read_bytes(), cell) for cell in cells
    ]
    byte_table = table_xml(payload)
    file_table = table_xml(path.read_bytes())
    assert byte_table is not None and file_table is not None
    byte_style = byte_table.find("main:tableStyleInfo", NS)
    file_style = file_table.find("main:tableStyleInfo", NS)
    assert byte_style is not None and file_style is not None
    assert byte_style.attrib["name"] == file_style.attrib["name"] == "TableStyleMedium2"
    assert byte_table.find("main:autoFilter", NS) is not None

    expected_formats = {
        "B2": "dd/mm/yyyy",
        "C2": "dd/mm/yyyy hh:mm:ss",
        "D2": "hh:mm:ss",
        "E2": "#,##0",
        "F2": "#,##0.00",
        "G2": "#,##0.00",
    }
    for cell, expected in expected_formats.items():
        assert cell_number_format(payload, cell) == expected
        assert cell_number_format(payload, cell) == cell_number_format(
            path.read_bytes(), cell
        )

    sheet = workbook_xml(payload, "xl/worksheets/sheet1.xml")
    sheet_view = sheet.find("main:sheetViews/main:sheetView", NS)
    assert sheet_view is not None and sheet_view.attrib["showGridLines"] == "0"
    pane = sheet_view.find("main:pane", NS)
    assert pane is not None and pane.attrib["state"] == "frozen"

    assert frame.equals(original)


def test_empty_dataframe_bytes_are_a_valid_empty_workbook() -> None:
    payload = exportar_excel_bytes(pl.DataFrame())

    with ZipFile(BytesIO(payload)) as archive:
        assert archive.testzip() is None
    assert worksheet_name(payload) == "Dados"
    assert table_xml(payload) is None
    worksheet = workbook_xml(payload, "xl/worksheets/sheet1.xml")
    assert worksheet.find("main:sheetData/main:row", NS) is None


def test_unsupported_binary_values_raise_in_bytes_mode() -> None:
    frame = pl.DataFrame({"conteudo": [b"bytes"]})

    with pytest.raises(TypeError):
        exportar_excel_bytes(frame)


def test_bytes_output_does_not_mutate_input_dataframe() -> None:
    frame = pl.DataFrame({"produto": ["A-1"], "preco": [12.5]})
    original = frame.clone()

    exportar_excel_bytes(frame)

    assert frame.equals(original)
