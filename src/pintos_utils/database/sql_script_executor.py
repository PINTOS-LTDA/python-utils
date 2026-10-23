"""Execute conventional SQL scripts on a consumer-owned MySQL connection."""

from __future__ import annotations

import importlib
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pintos_utils.database.dataframe import sql_script_result_to_dataframe
from pintos_utils.database.exceptions import DataFrameDatabaseError, SqlScriptError
from pintos_utils.database.models import SqlScriptResult

if TYPE_CHECKING:
    import polars as pl
    from mysql.connector.connection import MySQLConnection as _MySQLConnection
else:
    _MySQLConnection = Any

_LOGGER = logging.getLogger(__name__)
_DML_START_WORDS = frozenset({"DELETE", "INSERT", "REPLACE", "UPDATE"})
_CTE_STATEMENT_START_WORDS = _DML_START_WORDS | {"SELECT"}
_SYSTEM_VARIABLE_SCOPES = frozenset(
    {"GLOBAL", "LOCAL", "PERSIST", "PERSIST_ONLY", "SESSION"}
)


@dataclass(frozen=True, slots=True)
class _Token:
    """Small lexical token used only for script preflight."""

    kind: str
    value: str


@dataclass(frozen=True, slots=True)
class _LexedSql:
    """SQL text after marker translation and its lexical metadata."""

    translated: str
    markers: tuple[str, ...]
    tokens: tuple[_Token, ...]
    has_sql: bool


class SqlScriptExecutor:
    """Run SQL statements sequentially using one existing MySQL connection.

    The consumer creates and owns ``connection``. This executor only creates
    and closes cursors; it never closes the connection or rolls it back.
    """

    def __init__(self, connection: _MySQLConnection) -> None:
        """Create an executor around a consumer-owned Connector/Python connection."""
        self._connection = connection

    def execute(
        self,
        script: str,
        params: Mapping[str, Any] | None = None,
        commit: bool = False,
    ) -> SqlScriptResult:
        """Execute a SQL string and return its final result set and row counts.

        Public ``:name`` markers are bound by the MySQL driver. Missing names
        and prohibited transaction-control statements are rejected before any
        cursor is created. Only rows from the last result-producing statement
        are retained in memory.
        """
        _LOGGER.debug("Starting SQL script execution")
        if not isinstance(script, str):
            raise SqlScriptError("SQL script must be a string")

        try:
            whole_script = _lex_sql(script)
            statements = _split_sql(script) if whole_script.has_sql else []
            lexed_statements: list[tuple[str, _LexedSql]] = []
            for statement in statements:
                lexed = _lex_sql(statement)
                if lexed.has_sql:
                    lexed_statements.append((statement, lexed))
        except SqlScriptError:
            _LOGGER.debug("SQL script rejected during preflight")
            raise
        except Exception as error:
            _LOGGER.debug("SQL script could not be parsed")
            raise SqlScriptError(
                "Unable to parse SQL script", original_exception=error
            ) from error

        _LOGGER.debug("Identified %d SQL statements", len(lexed_statements))
        if not lexed_statements:
            _LOGGER.debug("SQL script execution completed without statements")
            return SqlScriptResult()

        supplied_params = params if params is not None else {}
        statement_params: list[dict[str, Any]] = []
        for statement_index, (statement, lexed) in enumerate(lexed_statements, 1):
            if _has_forbidden_transaction_control(lexed.tokens):
                _LOGGER.debug("SQL script rejected during transaction preflight")
                raise SqlScriptError(
                    "SQL script contains unsupported transaction-control SQL",
                    statement_index=statement_index,
                    statement=statement,
                )

            missing = next(
                (name for name in lexed.markers if name not in supplied_params), None
            )
            if missing is not None:
                _LOGGER.debug("SQL script rejected because a parameter is missing")
                raise SqlScriptError(
                    f"Missing required SQL parameter: {missing}",
                    statement_index=statement_index,
                    statement=statement,
                )

            names = dict.fromkeys(lexed.markers)
            statement_params.append({name: supplied_params[name] for name in names})

        if commit:
            try:
                if self._connection.in_transaction:
                    _LOGGER.debug("SQL script rejected because a transaction is active")
                    raise SqlScriptError(
                        "Cannot execute with commit=True while a transaction is active"
                    )
            except SqlScriptError:
                raise
            except Exception as error:
                _LOGGER.debug("Unable to inspect the MySQL transaction state")
                raise SqlScriptError(
                    "Unable to inspect the MySQL transaction state",
                    original_exception=error,
                ) from error

        try:
            cursor = self._connection.cursor(dictionary=True)
        except Exception as error:
            _LOGGER.debug("Unable to create a MySQL cursor")
            raise SqlScriptError(
                "Unable to create a MySQL cursor", original_exception=error
            ) from error

        result = SqlScriptResult()
        primary_error: BaseException | None = None
        try:
            for statement_index, ((statement, lexed), bindings) in enumerate(
                zip(lexed_statements, statement_params, strict=True), 1
            ):
                _LOGGER.debug("Executing SQL statement %d", statement_index)
                started_at = time.perf_counter()
                try:
                    if bindings:
                        cursor.execute(lexed.translated, bindings)
                    else:
                        cursor.execute(lexed.translated)

                    if cursor.with_rows:
                        fetched_rows = cast(Any, cursor.fetchall())
                        result.rows = [dict(row) for row in fetched_rows]
                        description = cursor.description or ()
                        result.columns = [str(column[0]) for column in description]

                    rowcount = cursor.rowcount
                    if (
                        _is_dml_statement(lexed.tokens)
                        and isinstance(rowcount, int)
                        and not isinstance(rowcount, bool)
                    ):
                        if rowcount >= 0:
                            result.affected_rows += rowcount
                    result.statements_executed += 1
                except Exception as error:
                    elapsed = time.perf_counter() - started_at
                    _LOGGER.debug(
                        "SQL statement %d failed after %.6f seconds",
                        statement_index,
                        elapsed,
                    )
                    raise SqlScriptError(
                        f"SQL statement {statement_index} failed",
                        statement_index=statement_index,
                        statement=statement,
                        original_exception=error,
                    ) from error
                elapsed = time.perf_counter() - started_at
                _LOGGER.debug(
                    "SQL statement %d completed in %.6f seconds",
                    statement_index,
                    elapsed,
                )
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                cursor.close()
            except Exception as close_error:
                if primary_error is not None:
                    _LOGGER.debug(
                        "Cursor close failed while preserving an earlier error"
                    )
                else:
                    _LOGGER.debug("Unable to close the MySQL cursor")
                    raise SqlScriptError(
                        "Unable to close the MySQL cursor",
                        original_exception=close_error,
                    ) from close_error

        if commit:
            try:
                self._connection.commit()
            except Exception as error:
                _LOGGER.debug("Unable to commit the SQL script")
                raise SqlScriptError(
                    "Unable to commit the SQL script", original_exception=error
                ) from error

        _LOGGER.debug(
            "SQL script execution completed: %d statements, %d affected rows",
            result.statements_executed,
            result.affected_rows,
        )
        return result

    def execute_dataframe(
        self,
        script: str,
        params: Mapping[str, Any] | None = None,
        commit: bool = False,
    ) -> pl.DataFrame:
        """Execute a SQL script and return its last result set as a Polars frame."""
        _require_script_polars()
        has_sql = isinstance(script, str) and _lex_sql(script).has_sql
        if commit and has_sql:
            self._ensure_no_active_transaction()

        result = self.execute(script, params=params, commit=False)
        try:
            dataframe = sql_script_result_to_dataframe(result)
        except DataFrameDatabaseError as error:
            cleanup_error: BaseException | None = None
            if commit and result.statements_executed:
                try:
                    self._connection.rollback()
                except BaseException as rollback_error:
                    cleanup_error = rollback_error
            raise DataFrameDatabaseError(
                str(error),
                operation="convert",
                original_exception=error.original_exception or error,
                cleanup_exception=cleanup_error,
            ) from error

        if commit and result.statements_executed:
            try:
                self._connection.commit()
            except Exception as error:
                _LOGGER.debug("Unable to commit the SQL script")
                raise SqlScriptError(
                    "Unable to commit the SQL script", original_exception=error
                ) from error
        return dataframe

    def execute_file(
        self,
        file_path: str | Path,
        params: Mapping[str, Any] | None = None,
        commit: bool = False,
        encoding: str = "utf-8",
    ) -> SqlScriptResult:
        """Read and execute a SQL file using the requested text encoding."""
        try:
            script = Path(file_path).read_text(encoding=encoding)
        except (OSError, UnicodeError, LookupError) as error:
            _LOGGER.debug("Unable to read SQL script file")
            raise SqlScriptError(
                f"Unable to read SQL script file: {file_path}",
                original_exception=error,
            ) from error
        return self.execute(script, params=params, commit=commit)

    def execute_file_dataframe(
        self,
        file_path: str | Path,
        params: Mapping[str, Any] | None = None,
        commit: bool = False,
        encoding: str = "utf-8",
    ) -> pl.DataFrame:
        """Read a SQL file and return its last result set as a Polars frame."""
        _require_script_polars()
        try:
            script = Path(file_path).read_text(encoding=encoding)
        except (OSError, UnicodeError, LookupError) as error:
            _LOGGER.debug("Unable to read SQL script file")
            raise SqlScriptError(
                f"Unable to read SQL script file: {file_path}",
                original_exception=error,
            ) from error
        return self.execute_dataframe(script, params=params, commit=commit)

    def _ensure_no_active_transaction(self) -> None:
        try:
            if self._connection.in_transaction:
                _LOGGER.debug("SQL script rejected because a transaction is active")
                raise SqlScriptError(
                    "Cannot execute with commit=True while a transaction is active"
                )
        except SqlScriptError:
            raise
        except Exception as error:
            _LOGGER.debug("Unable to inspect the MySQL transaction state")
            raise SqlScriptError(
                "Unable to inspect the MySQL transaction state",
                original_exception=error,
            ) from error


def _require_script_polars() -> None:
    """Check the optional dependency before SQL execution begins."""
    try:
        importlib.import_module("polars")
    except ImportError as error:
        raise DataFrameDatabaseError(
            "SQL script DataFrame execution requires pintos-utils[mysql,polars]",
            operation="convert",
            original_exception=error,
        ) from error


def _split_sql(script: str) -> list[str]:
    """Split SQL without treating semicolons in quoted text as boundaries."""
    try:
        import sqlparse
    except ImportError as error:
        raise SqlScriptError(
            "SQL execution requires the optional 'mysql' extra; install "
            "pintos-utils[mysql]",
            original_exception=error,
        ) from error
    return sqlparse.split(script)


def _lex_sql(script: str) -> _LexedSql:
    """Recognize markers, comments, quotes, and preflight tokens lexically."""
    markers: list[str] = []
    replacements: list[tuple[int, int, str]] = []
    tokens: list[_Token] = []
    has_sql = False
    index = 0
    length = len(script)

    while index < length:
        character = script[index]
        next_character = script[index + 1] if index + 1 < length else ""

        if character.isspace():
            index += 1
            continue

        if character in "'\"`":
            has_sql = True
            quote = character
            index += 1
            while index < length:
                if script[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                if script[index] == quote:
                    if index + 1 < length and script[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            continue

        if character == "#":
            index = _after_line_comment(script, index)
            continue

        if (
            character == "-"
            and next_character == "-"
            and (index + 2 == length or ord(script[index + 2]) <= 32)
        ):
            index = _after_line_comment(script, index)
            continue

        if character == "/" and next_character == "*":
            if index + 2 < length and script[index + 2] == "!":
                raise SqlScriptError(
                    "MySQL executable comments are not supported in SQL scripts"
                )
            end = script.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue

        if character == ":" and next_character == "=":
            has_sql = True
            tokens.append(_Token("symbol", ":="))
            index += 2
            continue

        if (
            character == ":"
            and _is_name_start(next_character)
            and (index == 0 or script[index - 1] != ":")
        ):
            end = index + 2
            while end < length and _is_name_continue(script[end]):
                end += 1
            name = script[index + 1 : end]
            markers.append(name)
            replacements.append((index, end, name))
            tokens.append(_Token("marker", name))
            has_sql = True
            index = end
            continue

        if _is_name_start(character):
            end = index + 1
            while end < length and _is_name_continue(script[end]):
                end += 1
            tokens.append(_Token("word", script[index:end]))
            has_sql = True
            index = end
            continue

        if character != ";":
            has_sql = True
        tokens.append(_Token("symbol", character))
        index += 1

    translated_parts: list[str] = []
    previous_end = 0
    for start, end, name in replacements:
        translated_parts.append(script[previous_end:start])
        translated_parts.append(f"%({name})s")
        previous_end = end
    translated_parts.append(script[previous_end:])

    return _LexedSql(
        translated="".join(translated_parts),
        markers=tuple(markers),
        tokens=tuple(tokens),
        has_sql=has_sql,
    )


def _after_line_comment(script: str, start: int) -> int:
    """Return the position following a ``--`` or ``#`` line comment."""
    newline = script.find("\n", start)
    return len(script) if newline < 0 else newline + 1


def _is_name_start(character: str) -> bool:
    """Check the ASCII start characters accepted in public marker names."""
    return len(character) == 1 and (
        "A" <= character <= "Z" or "a" <= character <= "z" or character == "_"
    )


def _is_name_continue(character: str) -> bool:
    """Check the ASCII continuation characters accepted in marker names."""
    return _is_name_start(character) or ("0" <= character <= "9")


def _has_forbidden_transaction_control(tokens: tuple[_Token, ...]) -> bool:
    """Check normal SQL tokens for transaction commands and autocommit writes."""
    if not tokens or tokens[0].kind != "word":
        return False

    first = tokens[0].value.upper()
    if first in {"BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT"}:
        return True
    if (
        first == "START"
        and len(tokens) > 1
        and tokens[1].kind == "word"
        and tokens[1].value.upper() == "TRANSACTION"
    ):
        return True
    if (
        first == "RELEASE"
        and len(tokens) > 1
        and tokens[1].kind == "word"
        and tokens[1].value.upper() == "SAVEPOINT"
    ):
        return True
    if first != "SET":
        return False

    set_tokens = tokens[1:]
    if _starts_with_set_transaction(set_tokens):
        return True
    return any(
        _is_autocommit_assignment(segment)
        for segment in _assignment_segments(set_tokens)
    )


def _starts_with_set_transaction(tokens: tuple[_Token, ...]) -> bool:
    """Recognize SET TRANSACTION and its GLOBAL/SESSION scope forms."""
    if not tokens or tokens[0].kind != "word":
        return False
    first = tokens[0].value.upper()
    if first == "TRANSACTION":
        return True
    return (
        first in {"GLOBAL", "LOCAL", "SESSION"}
        and len(tokens) > 1
        and tokens[1].kind == "word"
        and tokens[1].value.upper() == "TRANSACTION"
    )


def _assignment_segments(tokens: tuple[_Token, ...]) -> list[tuple[_Token, ...]]:
    """Split SET assignments on commas outside parenthesized expressions."""
    segments: list[tuple[_Token, ...]] = []
    start = 0
    depth = 0
    for index, token in enumerate(tokens):
        if token.value == "(":
            depth += 1
        elif token.value == ")":
            depth = max(0, depth - 1)
        elif token.value == "," and depth == 0:
            segments.append(tokens[start:index])
            start = index + 1
    segments.append(tokens[start:])
    return segments


def _is_autocommit_assignment(tokens: tuple[_Token, ...]) -> bool:
    """Check whether a SET assignment targets the system autocommit variable."""
    depth = 0
    target_end: int | None = None
    for index, token in enumerate(tokens):
        if token.value == "(":
            depth += 1
        elif token.value == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and token.value in {"=", ":="}:
            target_end = index
            break
    if target_end is None:
        return False

    target = tokens[:target_end]
    target_words = [token.value.upper() for token in target if token.kind == "word"]
    if len(target) == 1 and target_words == ["AUTOCOMMIT"]:
        return True
    if (
        len(target) == 2
        and target[0].kind == "word"
        and target[0].value.upper() in _SYSTEM_VARIABLE_SCOPES
        and target_words[1:] == ["AUTOCOMMIT"]
    ):
        return True

    if len(target) < 3 or target[0].value != "@" or target[1].value != "@":
        return False
    remainder = target[2:]
    if len(remainder) == 1:
        return (
            remainder[0].kind == "word" and remainder[0].value.upper() == "AUTOCOMMIT"
        )
    if (
        len(remainder) == 3
        and remainder[0].kind == "word"
        and remainder[0].value.upper() in _SYSTEM_VARIABLE_SCOPES
        and remainder[1].value == "."
        and remainder[2].kind == "word"
    ):
        return remainder[2].value.upper() == "AUTOCOMMIT"
    return False


def _is_dml_statement(tokens: tuple[_Token, ...]) -> bool:
    """Return whether a statement starts with a supported DML form.

    MySQL permits a ``WITH`` clause before ``UPDATE`` and ``DELETE``. Inspect
    top-level words after CTE bodies and stop at the outer statement verb so
    clauses such as ``SELECT ... FOR UPDATE`` are not classified as DML.
    """
    if not tokens or tokens[0].kind != "word":
        return False

    first = tokens[0].value.upper()
    if first in _DML_START_WORDS:
        return True
    if first != "WITH":
        return False

    depth = 0
    closed_group = False
    for token in tokens[1:]:
        if token.value == "(":
            depth += 1
        elif token.value == ")":
            depth = max(0, depth - 1)
            if depth == 0:
                closed_group = True
        elif (
            closed_group
            and depth == 0
            and token.kind == "word"
            and token.value.upper() in _CTE_STATEMENT_START_WORDS
        ):
            return token.value.upper() in _DML_START_WORDS
    return False
