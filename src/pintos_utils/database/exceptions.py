"""Exceptions raised by database utilities."""

from __future__ import annotations

from typing import Literal


class SqlScriptError(Exception):
    """Describe a SQL script failure and any available statement context.

    ``statement_index`` is one-based when a particular statement failed.
    ``original_exception`` retains the underlying exception, which is also
    chained as ``__cause__`` by the executor when it wraps a runtime failure.
    """

    def __init__(
        self,
        message: str,
        *,
        statement_index: int | None = None,
        statement: str | None = None,
        original_exception: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.statement_index = statement_index
        self.statement = statement
        self.original_exception = original_exception


class DataFrameDatabaseError(Exception):
    """Describe a DataFrame database operation failure without source values."""

    def __init__(
        self,
        message: str,
        *,
        operation: Literal["query", "import"],
        original_exception: BaseException | None = None,
        cleanup_exception: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.original_exception = original_exception
        self.cleanup_exception = cleanup_exception
