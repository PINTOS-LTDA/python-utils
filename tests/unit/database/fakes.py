"""Fake MySQL connection and cursor objects for deterministic tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FakeStatementResult:
    """Outcome configured for one fake cursor execution."""

    rows: Sequence[Any] | None = None
    columns: Sequence[str] | None = None
    rowcount: int = -1
    execute_error: BaseException | None = None
    fetch_error: BaseException | None = None
    executemany_error: BaseException | None = None
    extra_result_sets: int = 0


@dataclass(slots=True)
class FakeCursor:
    """Cursor that records SQL and returns configured statement outcomes."""

    results: Sequence[FakeStatementResult] = ()
    close_error: BaseException | None = None
    events: list[str] = field(default_factory=list)
    calls: list[tuple[str, Mapping[str, Any] | Sequence[Any] | None]] = field(
        default_factory=list
    )
    many_calls: list[tuple[str, Sequence[Sequence[Any]]]] = field(default_factory=list)
    closed: bool = False
    with_rows: bool = False
    rowcount: int = -1
    description: Sequence[tuple[Any, ...]] | None = None
    _current_result: FakeStatementResult | None = None
    _result_index: int = 0
    _extra_result_sets_remaining: int = 0

    def execute(
        self,
        operation: str,
        params: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> None:
        """Record a call and apply the next configured outcome."""
        self.calls.append((operation, params))
        self.events.append(f"execute:{operation}")
        result_index = self._result_index
        self._result_index += 1
        result = (
            self.results[result_index]
            if result_index < len(self.results)
            else FakeStatementResult()
        )
        self._current_result = result
        self.with_rows = result.rows is not None
        self.rowcount = result.rowcount
        self.description = (
            [(name, None, None, None, None, None, None) for name in result.columns]
            if result.columns is not None
            else None
        )
        self._extra_result_sets_remaining = result.extra_result_sets
        if result.execute_error is not None:
            raise result.execute_error

    def executemany(self, operation: str, seq_params: Sequence[Sequence[Any]]) -> None:
        """Record a bounded batch and optionally fail it."""
        self.many_calls.append((operation, seq_params))
        self.events.append(f"executemany:{operation}")
        result_index = self._result_index
        self._result_index += 1
        result = (
            self.results[result_index]
            if result_index < len(self.results)
            else FakeStatementResult()
        )
        self._current_result = result
        self.rowcount = result.rowcount
        if result.executemany_error is not None:
            raise result.executemany_error

    def fetchall(self) -> list[Any]:
        """Return the configured rows or raise its configured error."""
        result = self._current_result
        if result is None:
            return []
        if result.fetch_error is not None:
            raise result.fetch_error
        return list(result.rows or [])

    def nextset(self) -> bool | None:
        """Expose configured additional result sets."""
        if self._extra_result_sets_remaining <= 0:
            return None
        self._extra_result_sets_remaining -= 1
        self.with_rows = True
        return True

    def close(self) -> None:
        """Record cursor cleanup, optionally failing for error-path tests."""
        self.closed = True
        self.events.append("cursor.close")
        if self.close_error is not None:
            raise self.close_error


@dataclass(slots=True)
class FakeConnection:
    """Connection fake that tracks session and transaction lifecycle calls."""

    results: Sequence[FakeStatementResult] = ()
    in_transaction: bool = False
    cursor_error: BaseException | None = None
    commit_error: BaseException | None = None
    rollback_error: BaseException | None = None
    start_transaction_error: BaseException | None = None
    close_error: BaseException | None = None
    cursor_close_error: BaseException | None = None
    created_cursors: list[FakeCursor] = field(default_factory=list)
    cursor_options: list[bool] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    closes: int = 0

    def cursor(self, *, dictionary: bool = False, **kwargs: Any) -> FakeCursor:
        """Create and retain a fake cursor with the requested options."""
        del kwargs
        self.cursor_options.append(dictionary)
        self.events.append("cursor.create")
        if self.cursor_error is not None:
            raise self.cursor_error
        cursor = FakeCursor(
            results=self.results,
            close_error=self.cursor_close_error,
            events=self.events,
        )
        self.created_cursors.append(cursor)
        return cursor

    def start_transaction(self) -> None:
        """Start an operation-owned transaction explicitly."""
        self.events.append("start_transaction")
        if self.start_transaction_error is not None:
            raise self.start_transaction_error
        if self.in_transaction:
            raise RuntimeError("Transaction already active")
        self.in_transaction = True

    def commit(self) -> None:
        """Record a commit and simulate Connector/Python transaction state."""
        self.commits += 1
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error
        self.in_transaction = False

    def rollback(self) -> None:
        """Record rollback calls so tests can assert none were made."""
        self.rollbacks += 1
        self.events.append("rollback")
        if self.rollback_error is not None:
            raise self.rollback_error
        self.in_transaction = False

    def close(self) -> None:
        """Record connection closure so tests can assert caller ownership."""
        self.closes += 1
        self.events.append("connection.close")
        if self.close_error is not None:
            raise self.close_error
