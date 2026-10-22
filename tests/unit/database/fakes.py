"""Fake MySQL connection and cursor objects for deterministic tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FakeStatementResult:
    """Outcome configured for one fake cursor execution."""

    rows: list[dict[str, Any]] | None = None
    rowcount: int = -1
    execute_error: BaseException | None = None
    fetch_error: BaseException | None = None


@dataclass(slots=True)
class FakeCursor:
    """Cursor that records SQL and returns configured statement outcomes."""

    results: Sequence[FakeStatementResult] = ()
    close_error: BaseException | None = None
    events: list[str] = field(default_factory=list)
    calls: list[tuple[str, Mapping[str, Any] | None]] = field(default_factory=list)
    closed: bool = False
    with_rows: bool = False
    rowcount: int = -1
    _current_result: FakeStatementResult | None = None

    def execute(
        self,
        operation: str,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        """Record a call and apply the next configured outcome."""
        self.calls.append((operation, params))
        self.events.append(f"execute:{operation}")
        result_index = len(self.calls) - 1
        result = (
            self.results[result_index]
            if result_index < len(self.results)
            else FakeStatementResult()
        )
        self._current_result = result
        self.with_rows = result.rows is not None
        self.rowcount = result.rowcount
        if result.execute_error is not None:
            raise result.execute_error

    def fetchall(self) -> list[dict[str, Any]]:
        """Return the configured rows or raise its configured error."""
        result = self._current_result
        if result is None:
            return []
        if result.fetch_error is not None:
            raise result.fetch_error
        return [dict(row) for row in result.rows or []]

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
    close_error: BaseException | None = None
    cursor_close_error: BaseException | None = None
    created_cursors: list[FakeCursor] = field(default_factory=list)
    cursor_options: list[bool] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    closes: int = 0

    def cursor(self, *, dictionary: bool = False) -> FakeCursor:
        """Create and retain a fake cursor with the requested options."""
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
