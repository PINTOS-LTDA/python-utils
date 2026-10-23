"""Small XML readers for inspecting generated Excel workbooks in tests."""

from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"main": MAIN_NS}


def workbook_xml(payload: bytes, member: str) -> ET.Element:
    with ZipFile(BytesIO(payload)) as archive:
        return ET.fromstring(archive.read(member))


def worksheet_name(payload: bytes) -> str:
    root = workbook_xml(payload, "xl/workbook.xml")
    sheet = root.find("main:sheets/main:sheet", NS)
    assert sheet is not None
    return sheet.attrib["name"]


def cell_value(payload: bytes, reference: str) -> str | None:
    sheet = workbook_xml(payload, "xl/worksheets/sheet1.xml")
    cell = sheet.find(f".//main:c[@r='{reference}']", NS)
    if cell is None:
        return None

    value = cell.find("main:v", NS)
    if cell.attrib.get("t") == "s" and value is not None:
        strings = workbook_xml(payload, "xl/sharedStrings.xml")
        entries = strings.findall("main:si", NS)
        index = int(value.text or "0")
        return "".join(
            text.text or "" for text in entries[index].findall(".//main:t", NS)
        )
    if cell.attrib.get("t") == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", NS))
    return None if value is None else value.text


def table_xml(payload: bytes) -> ET.Element | None:
    with ZipFile(BytesIO(payload)) as archive:
        if "xl/tables/table1.xml" not in archive.namelist():
            return None
        return ET.fromstring(archive.read("xl/tables/table1.xml"))


def cell_number_format(payload: bytes, reference: str) -> str | None:
    sheet = workbook_xml(payload, "xl/worksheets/sheet1.xml")
    cell = sheet.find(f".//main:c[@r='{reference}']", NS)
    if cell is None:
        return None

    style_index = int(cell.attrib.get("s", "0"))
    styles = workbook_xml(payload, "xl/styles.xml")
    cell_formats = styles.find("main:cellXfs", NS)
    assert cell_formats is not None
    format_id = int(cell_formats[style_index].attrib.get("numFmtId", "0"))
    number_formats = {
        int(item.attrib["numFmtId"]): item.attrib["formatCode"]
        for item in styles.findall("main:numFmts/main:numFmt", NS)
    }
    return number_formats.get(format_id)
