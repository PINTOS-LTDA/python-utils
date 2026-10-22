# Research: MySQL SQL Script Execution

## Decision 1: Split statements with `sqlparse`

**Decision**: Use `sqlparse.split()` to split ordinary SQL scripts, reject MySQL executable comments before comment filtering, then discard whitespace-only and ordinary-comment-only fragments. Execute retained statements individually in source order.

**Rationale**: The feature needs semicolon-aware splitting across quoted strings and ordinary comments. `sqlparse` exposes a statement-splitting API and is already suitable for the project's Python 3.11 minimum. It is a non-validating parser without a MySQL dialect model, so syntax and database semantics remain the server's responsibility. V1 excludes stored routines, triggers, executable comments, and client-side `DELIMITER` scripts.

**Alternatives considered**:

- Plain `str.split(';')`: rejected because it splits inside SQL strings and comments.
- Regex-only splitting: rejected because SQL quoting and comment states cannot be represented safely by a single delimiter expression.
- A full MySQL grammar/parser: rejected as unnecessary for the conventional statements in scope and disproportionate for this library module.

**References**: [sqlparse split/parse API](https://sqlparse.readthedocs.io/en/stable/api.html), [sqlparse parsing limits](https://sqlparse.readthedocs.io/en/stable/).

## Decision 2: Use a small lexical scanner for markers and transaction-control preflight

**Decision**: Before discarding comment-only fragments, lexically reject actual MySQL executable comments such as `/*!...*/` that occur outside strings and quoted identifiers. Then scan each statement with explicit normal, quoted-string, quoted-identifier, and ordinary-comment states. Recognize `:name` markers and transaction-control syntax only in normal SQL text. Reject the listed transaction commands and any `SET` assignment whose target is the system variable `autocommit`, including supported scope qualifiers and all targets in multi-assignment forms. Validate the complete script before creating a cursor or sending SQL.

**Rationale**: Public markers must not change inside strings, ordinary comments, or identifiers. The same lexical boundary information can identify prohibited commands while avoiding false positives from words inside those contexts. MySQL executable comments are rejected because the server executes their contents, so treating them as inert comments could bypass marker or transaction-command checks. Their delimiter is considered executable only when it occurs in SQL comment context, not inside a string or quoted identifier. The scanner recognizes the documented transaction-control forms and public marker grammar; it is not a general SQL grammar validator. The entire script is preflighted so a prohibited later statement cannot follow already-executed earlier statements.

**Alternatives considered**:

- Global regular-expression replacement or keyword search: rejected because it can rewrite markers or reject commands inside literals, ordinary comments, or quoted identifiers.
- Rewriting SQL through a general parser: not selected because `sqlparse` does not validate MySQL grammar; using it for boundaries and a focused scanner for the small public lexical rules keeps the responsibilities clear.

## Decision 3: Bind values with Connector/Python's named mapping style

**Decision**: Translate each recognized public marker to Connector/Python's `%(name)s` marker and pass a filtered mapping to `cursor.execute()`. Values are never formatted into SQL text.

**Rationale**: Connector/Python documents `%s` and `%(name)s` binding and conversion of supported Python values such as `datetime.date`. A per-statement mapping contains only that statement's referenced names and handles repeated markers without string interpolation.

**Alternatives considered**:

- SQL string formatting/interpolation: rejected because it does not provide driver-bound values.
- Positional binding: rejected because the public API promises named markers and repeated names.

**Reference**: [MySQL Connector/Python `cursor.execute()`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-execute.html).

## Decision 4: Execute sequentially on one dictionary cursor

**Decision**: Create one dictionary cursor from the supplied connection per non-empty script, execute each statement separately on that cursor, consume each result before continuing, retain only the last result-producing statement's rows, and close the cursor on every path.

**Rationale**: One connection and session preserve `USE` and temporary-table state. A dictionary cursor directly supports `list[dict[str, Any]]`. Sequential calls also preserve statement-level indexes and error context; the implementation does not depend on Connector/Python's former `execute(..., multi=True)` behavior, removed in Connector/Python 9.2.

**Alternatives considered**:

- One connection per statement: rejected because it loses session and temporary-table state and violates the public contract.
- Retaining all intermediate result sets: rejected because only the last is required and retaining them would increase memory use.
- Driver multi-statement execution: rejected because it complicates per-statement parameter binding, diagnostics, and result consumption, and the old `multi=True` API was removed.

**References**: [dictionary cursor](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursordict.html), [Connector/Python multiple-statement changes](https://dev.mysql.com/doc/connector-python/en/connector-python-multi.html).

## Decision 5: Keep transaction ownership with the consumer

**Decision**: Never close the supplied connection, change its autocommit setting, or issue an automatic rollback. With `commit=False`, do not call `commit()`. For a non-empty script with `commit=True`, inspect `connection.in_transaction` before SQL execution; if it is true, raise `SqlScriptError` without executing, committing, or rolling back. Otherwise, call `commit()` once after all statements succeed. Empty/ordinary-comment-only scripts remain no-ops; executable comments are rejected.

**Rationale**: Connector/Python exposes `in_transaction` as a boolean that covers transactions started through the API or SQL. Rejecting pre-existing work avoids committing changes made by the consumer before this executor call. Avoiding automatic rollback likewise prevents the executor from discarding work it does not own. SQL transaction commands in the script are rejected separately by Decision 6.

**Alternatives considered**:

- Commit the connection's current transaction even if it predates the call: rejected because it could commit unrelated consumer work.
- Roll back after failures: rejected because the executor cannot know which pending work belongs to the consumer.
- Begin an internal transaction: rejected because MySQL does not provide nested transactions and starting one can implicitly commit an existing transaction.

**References**: [Connector/Python `in_transaction`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-in-transaction.html), [Connector/Python `commit()`](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-commit.html).

## Decision 6: Reject explicit transaction-control SQL before executing the script

**Decision**: Preflight the entire script and reject transaction-control syntax as detailed in Decision 2, including supported `SET TRANSACTION` scopes and any assignment to system `autocommit`. Reject MySQL executable comments before filtering or execution. No SQL statement, commit, or rollback is sent for a rejected script.

**Rationale**: Such commands would bypass or undermine the public `commit` option and caller ownership. Classification must use lexical tokens in normal SQL context, not substring matching. Executable comments must not be treated as inert comments because MySQL evaluates their contents. This rule does not promise that every SQL command is transactionally harmless: MySQL DDL and some other statements can commit implicitly. Documentation must preserve that limitation, including the special non-rollbackable behavior of temporary-table DDL.

**Alternatives considered**:

- Execute transaction commands as ordinary script statements: rejected because the script could commit or roll back independently of `commit`.
- Reject every statement with any server-side transaction effect: rejected as too broad for a non-validating, MySQL-specific v1 parser; implicit-commit limitations are documented separately.

**References**: [MySQL transaction syntax](https://dev.mysql.com/doc/refman/8.4/en/commit.html), [savepoints](https://dev.mysql.com/doc/refman/8.4/en/savepoint.html), [statements that cause an implicit commit](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html).

## Decision 7: Keep the module provider-specific and proportionate

**Decision**: Expose `SqlScriptExecutor`, `SqlScriptResult`, and `SqlScriptError` from `pintos_utils.database`; do not add a generic database-provider protocol, connection factory, registry, or forwarding service in v1.

**Rationale**: This feature targets one driver and one narrow operation. The consumer supplies the connection, and fakes provide deterministic tests. No second provider has a concrete contract requiring a shared abstraction.

**Alternatives considered**:

- Add a generic cross-database provider hierarchy immediately: rejected as speculative and likely to constrain MySQL cursor and transaction semantics without a second implementation.
- Couple the database module to the email module: rejected because the responsibilities and optional dependencies are independent.

## Decision 8: Declare both runtime dependencies in the `mysql` extra

**Decision**: Add `mysql-connector-python` and `sqlparse` to `[project.optional-dependencies].mysql`; keep the base dependency list unchanged and refresh `uv.lock` for development.

**Rationale**: SQL splitting is needed by installed consumers at runtime, while MySQL script execution is an optional capability. The PyPA metadata standard represents extras through `project.optional-dependencies`, enabling `pip install "pintos-utils[mysql]"` without affecting the base package or email module.

**Alternatives considered**:

- Make either dependency mandatory: rejected because consumers without database use should not install them.
- Put `sqlparse` only in the development group: rejected because installed consumers need statement splitting.

**References**: [PyPA `pyproject.toml` guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/), [optional-dependencies specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/).

## Research risks and boundaries

- `sqlparse` splits and tokenizes SQL but does not validate MySQL syntax. Tests and the server remain responsible for behavior beyond the documented conventional subset.
- MySQL executable comments can contain server-executed SQL; v1 rejects actual executable-comment tokens before splitting/filtering rather than treating their contents as ordinary comments. The same character sequence inside strings and quoted identifiers is not a comment token.
- The no-op rule applies to ordinary comment-only input. An executable-comment-only script is rejected during preflight.
- `connection.in_transaction` detects an active transaction at the preflight boundary; it does not make the complete script atomic.
- MySQL can implicitly commit for DDL and other statements. `CREATE TEMPORARY TABLE` and `DROP TEMPORARY TABLE` do not ordinarily cause an implicit commit, but their effects are not rolled back. The executor must document rather than conceal these server rules.
- The module must not import optional dependencies through `pintos_utils` or the email package. The implementation should keep database support isolated and produce an actionable error if execution is attempted without the `mysql` extra.
