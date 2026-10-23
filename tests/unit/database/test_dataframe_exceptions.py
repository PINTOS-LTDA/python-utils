"""Contract tests for DataFrame database errors."""

from __future__ import annotations

from typing import get_args, get_type_hints

from pintos_utils.database.exceptions import DataFrameDatabaseError


def test_dataframe_error_retains_primary_and_cleanup_causes() -> None:
    original = RuntimeError("driver failed")
    cleanup = OSError("rollback failed")
    error = DataFrameDatabaseError(
        "DataFrame query failed",
        operation="query",
        original_exception=original,
        cleanup_exception=cleanup,
    )

    assert str(error) == "DataFrame query failed"
    assert error.operation == "query"
    assert error.original_exception is original
    assert error.cleanup_exception is cleanup


def test_dataframe_error_allows_missing_failure_context() -> None:
    error = DataFrameDatabaseError("Invalid import request", operation="import")

    assert error.original_exception is None
    assert error.cleanup_exception is None


def test_dataframe_error_accepts_conversion_operation() -> None:
    error = DataFrameDatabaseError("Unable to convert SQL result", operation="convert")
    operation_type = get_type_hints(DataFrameDatabaseError.__init__)["operation"]

    assert error.operation == "convert"
    assert error.original_exception is None
    assert error.cleanup_exception is None
    assert set(get_args(operation_type)) == {"query", "import", "convert"}
