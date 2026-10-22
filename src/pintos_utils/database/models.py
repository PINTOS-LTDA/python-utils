"""Provider-independent result models for database utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


@dataclass(slots=True)
class SqlScriptResult:
    """Summary of a SQL script execution.

    ``rows`` contains the last result set produced by the script. Rows are
    materialized in memory, so this model is not intended for unbounded results.
    """

    statements_executed: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)
    affected_rows: int = 0


class ImportMode(StrEnum):
    """Supported operations for importing a DataFrame into MySQL."""

    APPEND = "APPEND"
    UPSERT = "UPSERT"


@dataclass(frozen=True, slots=True)
class DataFrameImportResult:
    """Summary of a successfully committed DataFrame import."""

    rows_processed: int
    batches_processed: int
