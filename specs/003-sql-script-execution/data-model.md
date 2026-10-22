# Data Model: MySQL SQL Script Execution

This feature defines transient execution inputs and results. It does not introduce persistent library-owned storage or database schema.

## `SqlScriptResult`

Represents a completed script execution.

| Field | Type | Meaning |
|---|---|---|
| `statements_executed` | `int` | Number of non-empty statements that completed successfully. |
| `rows` | `list[dict[str, Any]]` | Rows from only the last result-producing statement; empty when no statement produced rows or the last result set was empty. |
| `affected_rows` | `int` | Sum of non-negative affected-row counts reported by successful DML statements. |

Rows are materialized in memory. Earlier result sets are consumed and discarded before the next statement. The result model is not intended for unbounded final result sets.

## SQL Script

An input is either a Python `str` or text decoded from a `str | Path` using the requested encoding. It can contain conventional MySQL statements, ordinary comments, string literals, quoted identifiers, and named value markers. Non-empty statements are processed in source order. Empty/ordinary-comment-only input is a no-op and does not create a cursor or commit. MySQL executable comments are rejected before comment-only filtering.

Before any SQL is sent, the complete script is split and checked for missing parameter names and prohibited transaction-control statements. Thus a missing value or prohibited command in a later statement cannot cause earlier statements to run.

## SQL Statement

A non-empty statement identified from the script in source order. The executor assigns a one-based index for diagnostics, retains source SQL for a statement-related error, and binds only the named values referenced by that statement. A statement counts as executed only after its SQL call and required result consumption complete successfully.

## Named Value Marker

| Attribute | Rule |
|---|---|
| Public syntax | `:name` |
| Name | `[A-Za-z_][A-Za-z0-9_]*` |
| Context | Recognized only in normal SQL text, not in strings, ordinary comments, or quoted identifiers. MySQL executable comments are rejected during preflight. |
| Repetition | Multiple occurrences use the same supplied mapping value. |
| Binding | Sent separately through MySQL Connector/Python's named binding API. |
| Missing value | Detected across the complete script before SQL execution. |
| Extra supplied value | Ignored if no SQL marker references it. |
| Identifiers | Cannot be substituted with bound markers; table/column identifiers remain SQL text. |
| Value types | Compatible values such as `str`, `int`, `float`, `Decimal`, `date`, `datetime`, and `None` pass to the driver without library string conversion. |

## Caller-Owned Connection

The consumer creates/configures a MySQL Connector/Python connection and passes it to the executor. The executor uses that connection and session for all statements, creates/closes its own cursor, and never closes the connection or changes `autocommit`.

| Request | Required behavior |
|---|---|
| `commit=False` | Do not call `connection.commit()`; never issue automatic rollback. |
| `commit=True`, empty or ordinary-comment-only script | No-op; do not inspect for a commit or call `commit()`. |
| `commit=True`, non-empty script, active transaction before execution | Raise `SqlScriptError` before SQL; leave the connection and transaction untouched. |
| `commit=True`, non-empty script, no active transaction | Execute all statements and call `connection.commit()` once after success. |
| Script contains transaction-control SQL | Reject the entire script before SQL, regardless of the `commit` argument. |
| Any execution failure | Stop; do not issue automatic rollback or close the supplied connection. |

Explicit transaction-control statements include `START TRANSACTION`, `BEGIN [WORK]`, `COMMIT [WORK]`, `ROLLBACK [WORK]`, `SAVEPOINT`, `RELEASE SAVEPOINT`, and `SET [GLOBAL | SESSION] TRANSACTION`. Reject any `SET` assignment whose target is the server system variable `autocommit`, regardless of its assigned value or scope. Recognize unqualified, `GLOBAL`, `SESSION`, `LOCAL`, `PERSIST`, `PERSIST_ONLY`, and corresponding `@@` forms, using either `=` or `:=`; inspect every assignment target in a multi-assignment statement. A single-`@` user variable is not the system variable. Matching words inside strings, ordinary comments, or quoted identifiers do not count as such statements.

Actual MySQL executable comments such as `/*!...*/` outside strings and quoted identifiers are rejected during preflight rather than treated as inert comments. They can contain SQL that the server executes, so allowing them to pass as comments could bypass transaction-command checks and named-marker processing. The same character sequence inside a string or quoted identifier is preserved; ordinary comments remain opaque.

The connection's `in_transaction` state is read before SQL when a non-empty script requests `commit=True`. Connector/Python documents this property for transactions begun through its API or SQL. The executor does not take ownership of an already-open consumer transaction.

MySQL may commit implicitly for DDL and other server statements. Temporary-table DDL may avoid an implicit commit while still not being rollbackable. Therefore the API does not promise script-level atomicity.

## `SqlScriptError`

The public exception represents file, input/preflight, cursor, SQL statement, result-consumption, or commit failures.

| Diagnostic | Availability |
|---|---|
| Human-readable message | Always. |
| One-based `statement_index` | Present when a specific statement is known; otherwise absent/`None`. |
| Related SQL statement | Present when a statement is known; otherwise absent/`None`. |
| `original_exception` | Exposes the underlying exception when one exists. |
| Exception chaining | Original runtime failures are chained with `raise ... from ...`; a library precondition rejection need not invent an underlying cause. |

Default logs and messages must not include bound parameter values. SQL text may be attached to a diagnostic exception as required by the public contract.
