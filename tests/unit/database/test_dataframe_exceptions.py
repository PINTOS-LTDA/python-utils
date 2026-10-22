"""Contract tests for DataFrame database errors."""

from __future__ import annotations

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
