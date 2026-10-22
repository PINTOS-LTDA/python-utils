"""Private SQL preflight helpers for DataFrame database operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_SUPPORTED_STARTS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE"})
_CTE_STATEMENT_STARTS = _SUPPORTED_STARTS


@dataclass(frozen=True, slots=True)
class PreparedQuery:
    """One preflighted SQL statement and its separate named bindings."""

    sql: str
    params: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str


def prepare_query(query: str, params: Mapping[str, Any] | None) -> PreparedQuery:
    """Translate ``:name`` markers and reject unsafe or unsupported statements."""
    if not isinstance(query, str):
        raise ValueError("SQL query must be a string")
    if params is not None and not isinstance(params, Mapping):
        raise ValueError("SQL parameters must be a mapping")

    values = params if params is not None else {}
    tokens: list[_Token] = []
    replacements: list[tuple[int, int, str]] = []
    markers: list[str] = []
    semicolon_seen = False
    has_sql = False
    index = 0
    length = len(query)

    while index < length:
        char = query[index]
        next_char = query[index + 1] if index + 1 < length else ""

        if char.isspace():
            index += 1
            continue

        if char in "'\"`":
            quote = char
            start = index
            index += 1
            closed = False
            while index < length:
                if query[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                if query[index] == quote:
                    if index + 1 < length and query[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            if not closed:
                raise ValueError("SQL query contains an unterminated quoted value")
            has_sql = True
            if not semicolon_seen:
                tokens.append(
                    _Token(
                        "literal" if quote != "`" else "identifier", query[start:index]
                    )
                )
            elif query[start:index].strip():
                raise ValueError("Multiple SQL statements are not supported")
            continue

        if char == "#" or (
            char == "-"
            and next_char == "-"
            and (index + 2 == length or ord(query[index + 2]) <= 32)
        ):
            newline = query.find("\n", index)
            index = length if newline < 0 else newline + 1
            continue

        if char == "/" and next_char == "*":
            if index + 2 < length and query[index + 2] == "!":
                raise ValueError("MySQL executable comments are not supported")
            end = query.find("*/", index + 2)
            if end < 0:
                raise ValueError("SQL query contains an unterminated comment")
            index = end + 2
            continue

        if char == ";":
            if semicolon_seen:
                raise ValueError("Multiple SQL statements are not supported")
            semicolon_seen = True
            index += 1
            continue

        if semicolon_seen:
            raise ValueError("Multiple SQL statements are not supported")

        if char == ":" and next_char == "=":
            tokens.append(_Token("symbol", ":="))
            has_sql = True
            index += 2
            continue

        if (
            char == ":"
            and _is_name_start(next_char)
            and (index == 0 or query[index - 1] != ":")
        ):
            end = index + 2
            while end < length and _is_name_continue(query[end]):
                end += 1
            name = query[index + 1 : end]
            markers.append(name)
            replacements.append((index, end, name))
            tokens.append(_Token("marker", name))
            has_sql = True
            index = end
            continue

        if _is_name_start(char):
            end = index + 1
            while end < length and _is_name_continue(query[end]):
                end += 1
            tokens.append(_Token("word", query[index:end]))
            has_sql = True
            index = end
            continue

        tokens.append(_Token("symbol", char))
        has_sql = True
        index += 1

    if not has_sql or not any(
        token.kind in {"word", "literal", "identifier"} for token in tokens
    ):
        raise ValueError("SQL query must contain one statement")

    missing = next((name for name in markers if name not in values), None)
    if missing is not None:
        raise ValueError(f"Missing required SQL parameter: {missing}")

    statement_kind = _statement_kind(tokens)
    if statement_kind not in _SUPPORTED_STARTS:
        raise ValueError("SQL statement type is not supported for DataFrame queries")
    upper_words = [token.value.upper() for token in tokens if token.kind == "word"]
    if ":=" in (token.value for token in tokens) or "INTO" in upper_words:
        raise ValueError("SQL query contains an unsupported side-effect form")

    names = dict.fromkeys(markers)
    bindings = {name: values[name] for name in names}
    translated: list[str] = []
    previous_end = 0
    for start, end, name in replacements:
        translated.append(query[previous_end:start])
        translated.append(f"%({name})s")
        previous_end = end
    translated.append(query[previous_end:])
    return PreparedQuery("".join(translated), bindings)


def _statement_kind(tokens: list[_Token]) -> str | None:
    """Return the outer statement verb, including a supported CTE form."""
    if not tokens or tokens[0].kind != "word":
        return None
    first = tokens[0].value.upper()
    if first != "WITH":
        return first

    depth = 0
    closed_cte = False
    for token in tokens[1:]:
        if token.value == "(":
            depth += 1
        elif token.value == ")":
            depth = max(0, depth - 1)
            if depth == 0:
                closed_cte = True
        elif (
            closed_cte
            and depth == 0
            and token.kind == "word"
            and token.value.upper() in _CTE_STATEMENT_STARTS
        ):
            return token.value.upper()
    return None


def _is_name_start(character: str) -> bool:
    return len(character) == 1 and (
        "A" <= character <= "Z" or "a" <= character <= "z" or character == "_"
    )


def _is_name_continue(character: str) -> bool:
    return _is_name_start(character) or ("0" <= character <= "9")
