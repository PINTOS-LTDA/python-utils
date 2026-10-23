from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import polars as pl
import pytest
from _polars_excel_xml import cell_value, worksheet_name

from pintos_utils.polars_excel import exportar_excel


def sample_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "produto": ["Café", "A-002"],
            "quantidade": [3, 7],
        }
    )


@pytest.mark.parametrize("path_type", [str, Path])
def test_file_output_preserves_rows_columns_and_values(
    tmp_path: Path, path_type: type[str] | type[Path]
) -> None:
    path = tmp_path / "relatorio.xlsx"
    destination = path_type(path) if path_type is str else path

    exportar_excel(sample_frame(), destination)

    assert path.is_file()
    payload = path.read_bytes()
    assert worksheet_name(payload) == "Dados"
    assert [cell_value(payload, cell) for cell in ("A1", "B1")] == [
        "produto",
        "quantidade",
    ]
    assert [cell_value(payload, cell) for cell in ("A2", "B2", "A3", "B3")] == [
        "Café",
        "3",
        "A-002",
        "7",
    ]


def test_file_output_uses_custom_worksheet_name(tmp_path: Path) -> None:
    path = tmp_path / "relatorio.xlsx"

    exportar_excel(sample_frame(), path, aba="Resumo")

    assert worksheet_name(path.read_bytes()) == "Resumo"


def test_file_output_replaces_existing_destination(tmp_path: Path) -> None:
    path = tmp_path / "relatorio.xlsx"
    path.write_bytes(b"old content")

    exportar_excel(sample_frame(), path)

    with ZipFile(path) as archive:
        assert archive.testzip() is None
    assert cell_value(path.read_bytes(), "A2") == "Café"
