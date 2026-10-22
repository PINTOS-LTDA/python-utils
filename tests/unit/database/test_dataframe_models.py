"""Contract tests for public DataFrame database result models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pintos_utils.database.models import DataFrameImportResult, ImportMode


def test_import_mode_is_a_string_enum() -> None:
    assert ImportMode.APPEND.value == "APPEND"
    assert ImportMode.UPSERT.value == "UPSERT"
    assert isinstance(ImportMode.APPEND, str)


def test_import_result_reports_rows_and_batches() -> None:
    result = DataFrameImportResult(rows_processed=7, batches_processed=3)

    assert result.rows_processed == 7
    assert result.batches_processed == 3


def test_import_result_is_immutable() -> None:
    result = DataFrameImportResult(rows_processed=1, batches_processed=1)

    with pytest.raises(FrozenInstanceError):
        result.rows_processed = 2  # type: ignore[misc]
