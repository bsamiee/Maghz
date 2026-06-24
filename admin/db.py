"""pg8000 ledger boundary: one `QueryResult` owner and one `query` rail over the maghz database.

pg8000 is pure-Python and blocking, so every statement rides one `anyio.to_thread.run_sync` offload
bounded by the shared `_DB_LANE.limiter` (the substrate-memoised `CapacityLimiter` keyed on the frozen
`LanePolicy` identity, so a second `LanePolicy(capacity=8)` anywhere borrows the one bound) and wrapped
— retry, span, and terminal fault-lift — by the single `guarded(RetryClass.DB, ...)` resilience
envelope. The `BoundaryFault` lift therefore happens exactly once, inside `guarded`'s `async_boundary`:
this owner mints no fault, re-spells no rail, and interior code never sees a raised driver exception.
The connection is request-scoped — the native `with pg8000.native.Connection(...)` bracket releases it
on success, fault, and cancellation. `Exec` keys `_EXEC`, the one `frozendict` of pg8000 callables: a
new execution modality (copy, transaction) is one member plus one row, never a parallel
`query_one`/`query_script`/`query_prepared` family.

The retry disposition is the SQLSTATE transient/terminal partition, not the coarse `RetryClass.DB`
`(pg8000.Error, OSError)` target alone: connection-level faults (`InterfaceError`, an `OSError` re-dial)
and the transient in-flight classes (`_DB_TRANSIENT` — connection-exception `08`, serialization/deadlock
`40001`/`40P01`, admin-shutdown/cannot-connect `57P01`/`57P03`, insufficient-resources `53`, lock-not-
available `55P03`) replay within the canonical DB budget, while a terminal in-flight `DatabaseError`
(syntax `42`, integrity `23`, data `22`) re-raises through `_classified` as the `_TerminalError` marker
— a plain `Exception` outside the `RetryClass.DB` target — so it surfaces on the FIRST attempt rather
than burning four backoff retries on a fault no re-dial clears (and a non-idempotent write never re-
applies). `_TerminalError` carries the clean `sqlstate: message` projection off the response dict, so
`BoundaryFault(boundary)` names the SQLSTATE cause rather than the raw `{'C': ..., 'M': ...}` repr. This
is the consumer half of the substrate `RetryClass.DB` contract: that row retries a connection-loss flap,
and the in-flight query fault is tagged non-retryably here so it never reaches `guard`.
"""

# --- [RUNTIME_PRELUDE] -----------------------------------------------------------------

from collections.abc import Callable, Mapping
from contextlib import closing
from enum import StrEnum
from typing import Final

from anyio.to_thread import run_sync
from frozendict import frozendict
import msgspec
from pg8000 import DatabaseError
from pg8000.core import Context
import pg8000.native

from admin.runtime import guarded, LanePolicy, RetryClass, RuntimeRail
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------

type Scalar = str | int | float | bool | bytes | None
type Params = Mapping[str, Scalar]
# Each arm returns the pg8000 result `Context` (typed `Context | None`, the driver's own `_context`
# slot type) whose `columns`/`rows`/`row_count` `_materialize` projects off ONE owner. The
# `Connection.columns`/`row_count` properties read `Connection._context`, which the extended-query
# protocol leaves unset on the prepared path — `PreparedStatement.run` binds the result context onto
# the statement, not the connection — so the RUN/SCRIPT arms yield `Connection._context` and the
# PREPARED arm yields `PreparedStatement._context`, and the one materializer reads the live context
# that actually ran the statement rather than a stale connection field, the `None` floor absorbing a
# context the driver never bound.
type ExecFn = Callable[[pg8000.native.Connection, str, Params], Context | None]


class Exec(StrEnum):
    """The closed statement-execution modality `query` discriminates on, one `_EXEC` row each.

    `RUN` binds named `:param` placeholders for the single-statement one-shot; `SCRIPT` runs a
    parameter-free multi-statement string (DDL/migration files) — both ride `Connection.run`, whose
    `len(params) == 0` route sends a parameter-free string through the simple-query protocol so a whole
    DDL file executes in one round trip while a parameterized statement takes the extended protocol, so
    the two intents share one closure; `PREPARED` parses once into a reusable `PreparedStatement` closed
    inside the request bracket. The modality is a behavior-carrying value keying `_EXEC`, never a flag
    the body re-derives.
    """

    RUN = "run"
    SCRIPT = "script"
    PREPARED = "prepared"


# --- [CONSTANTS] -----------------------------------------------------------------------

# The transient in-flight SQLSTATE partition: the prefixes whose `DatabaseError` is worth a retry under
# the canonical DB budget because a re-dial or re-issue can clear it — `08` (connection exception),
# `40001`/`40P01` (serialization failure / deadlock detected, retryable for an idempotent statement),
# `57P01`/`57P03` (admin shutdown / cannot-connect-now, the server cycling), `53` (insufficient
# resources), `55P03` (lock not available). Every other class — `42` syntax, `23` integrity, `22` data —
# is a deterministic fault no retry clears, tagged terminal so it never reaches `guard`. This is the
# pg8000 analog of the substrate `SSH_TRANSIENT`/`SSH_TERMINAL` partition: one frozenset owns "which DB
# fault is retryable", read once by `_transient` so a fault can never be retry here and terminal there.
_DB_TRANSIENT: Final[frozenset[str]] = frozenset({"08", "40001", "40P01", "57P01", "57P03", "53", "55P03"})


# --- [MODELS] --------------------------------------------------------------------------


class QueryResult(msgspec.Struct, frozen=True, gc=False):
    """Column names, materialized rows, and the affected-row count of one statement.

    `affected` carries the statement context's `row_count` so a write-path consumer reads the affected
    count off this canonical owner rather than re-querying; it is `-1` when the backend reports none
    (a `SCRIPT` or a row-returning select). `columns` is empty for a no-result statement. `gc=False`
    is sound because every field bottoms out in immutable `Scalar` leaves (no struct/object ref can form
    a reference cycle through the nested scalar tuples), the high-allocation query path's GC elision.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]
    affected: int = -1


# --- [ERRORS] --------------------------------------------------------------------------


class _TerminalError(Exception):
    """The non-retryable in-flight marker: a deterministic `DatabaseError` re-spelled outside the retry target.

    `RetryClass.DB.target` is the coarse `(pg8000.Error, OSError)` tuple, so a raw terminal
    `DatabaseError` (syntax/integrity/data) would `isinstance`-match and burn four backoff retries. This
    marker is a plain `Exception` the target tuple cannot match, so `guard` passes it straight through on
    the first attempt; the `rails` `CLASSIFY` `(Exception,)` catch-all then lifts it to
    `BoundaryFault(boundary)` carrying the clean `sqlstate: message` detail this marker holds — richer
    than the raw `{'C': ..., 'M': ...}` response-dict repr `str(DatabaseError)` would surface.
    """


# --- [OPERATIONS] ----------------------------------------------------------------------


def _connect(cfg: MaghzSettings) -> pg8000.native.Connection:
    # PostgresDsn is a MultiHostUrl: components live under `hosts()`, not as flat attributes. `host`/
    # `port`/`database`/`user` carry the settings DSN defaults; the `or` floors only fire for a DSN
    # that omits the optional component.
    dsn = cfg.database.dsn
    host = dsn.hosts()[0]
    return pg8000.native.Connection(
        user=host["username"] or "maghz",
        host=host["host"] or "127.0.0.1",
        port=host["port"] or 15435,
        database=(dsn.path or "/maghz").removeprefix("/"),
        password=host["password"],
        timeout=cfg.database.connect_timeout,
    )


def _materialize(ctx: Context | None) -> QueryResult:
    """Project one pg8000 result `Context` into the frozen `QueryResult`.

    `columns`/`rows`/`row_count` all read off the single live context the statement bound, so the
    prepared path reads the statement's own context rather than the connection's unset field; `columns`
    is empty for a no-result statement, a `None` context (one the driver never bound) folds to the empty
    result, and `affected` is `-1` when the backend reports no row count.

    Returns:
        The frozen `QueryResult` carrying the context's column names, materialized rows, and row count.
    """
    if ctx is None:
        return QueryResult(columns=(), rows=())
    return QueryResult(
        columns=tuple(column["name"] for column in ctx.columns or ()),
        rows=tuple(tuple(row) for row in ctx.rows or ()),
        affected=ctx.row_count,
    )


def _transient(cause: DatabaseError) -> bool:
    """Whether an in-flight `DatabaseError` is a retryable transient, keyed on its SQLSTATE prefix.

    pg8000 raises the backend error-response dict in `args[0]`, its `'C'` slot the five-character
    SQLSTATE. A fault is transient when its SQLSTATE matches a `_DB_TRANSIENT` prefix (the class `08`,
    the full `40001`/`40P01`/`57P01`/`57P03`/`55P03`, or the class `53`); a response dict missing the
    `'C'` slot is treated terminal rather than guessed retryable.

    Returns:
        `True` when the SQLSTATE is in the transient partition, else `False`.
    """
    detail = cause.args[0] if cause.args else None
    sqlstate = detail.get("C") if isinstance(detail, Mapping) else None
    return sqlstate is not None and (sqlstate in _DB_TRANSIENT or sqlstate[:2] in _DB_TRANSIENT)


def _classified(exec_fn: ExecFn, conn: pg8000.native.Connection, sql: str, params: Params) -> Context | None:
    """Drive one `_EXEC` arm, re-raising a terminal in-flight `DatabaseError` as the `_TerminalError` marker.

    The single point the SQLSTATE partition is spent: a transient `DatabaseError` (and every connection-
    level `pg8000.Error`/`OSError`, which never reaches this `except`) propagates unchanged so `guard`
    retries it; a terminal one re-raises as `_TerminalError(f"{sqlstate}: {message}")` — outside the
    `RetryClass.DB` target — so it surfaces on the first attempt with the clean SQLSTATE cause. The raise
    chains the original via `from cause`, preserving the driver traceback for the span the lift records.

    Returns:
        The pg8000 result `Context` (or `None`) the arm bound, for `_materialize`.

    Raises:
        DatabaseError: A transient in-flight fault (`_DB_TRANSIENT` SQLSTATE), re-raised for `guard` to retry.
        _TerminalError: A deterministic in-flight fault, re-spelled outside the retry target to lift once.
    """
    try:
        return exec_fn(conn, sql, params)
    except DatabaseError as cause:
        if _transient(cause):
            raise
        detail = cause.args[0] if cause.args else {}
        sqlstate, message = (detail.get("C", "?"), detail.get("M", str(cause))) if isinstance(detail, Mapping) else ("?", str(cause))
        raise _TerminalError(f"{sqlstate}: {message}") from cause


def _run(conn: pg8000.native.Connection, sql: str, params: Params) -> Context | None:
    # RUN and SCRIPT share this arm: `Connection.run` routes a param-bearing statement through the
    # extended protocol and a param-free string (a multi-statement DDL/migration file) through the
    # simple-query protocol in one round trip, binding the result onto `Connection._context`.
    conn.run(sql, **params)
    return conn._context  # noqa: SLF001 - the pg8000 result context this boundary owns reading


def _run_prepared(conn: pg8000.native.Connection, sql: str, params: Params) -> Context | None:
    # Parsed once and the server-side handle released inside this bracket, never leaked past it.
    # `PreparedStatement.run` binds the result context onto the statement, so the materializer reads
    # `statement._context` — `Connection._context` stays unset across the extended-protocol exec.
    with closing(conn.prepare(sql)) as statement:
        statement.run(**params)
        return statement._context  # noqa: SLF001 - the pg8000 result context this boundary owns reading


# --- [TABLES] --------------------------------------------------------------------------

# One callable per `Exec` member over the shared `(connection, sql, params)` signature, each running
# inside the request-scoped connection bracket and returning the result `Context` for `_materialize`.
# RUN and SCRIPT bind the one `_run` arm (the simple-vs-extended protocol split is internal to
# `Connection.run`); the key set equals `Exec` exactly, so `_EXEC[mode]` subscription is total — a new
# modality is one member plus one row, never an `if mode ==` ladder.
_EXEC: Final[frozendict[Exec, ExecFn]] = frozendict({
    Exec.RUN: _run,
    Exec.SCRIPT: _run,
    Exec.PREPARED: _run_prepared,
})


# --- [COMPOSITION] ---------------------------------------------------------------------

# The pg8000 worker-thread fan-out rides the substrate-memoised `CapacityLimiter` keyed on this frozen
# `LanePolicy` identity (`LanePolicy.limiter` -> `lanes._limiter`, `functools.cache`-bound), so every
# `run_sync` offload across the process — and any identical `LanePolicy(capacity=8)` elsewhere —
# borrows the one bound pool the runtime drain limiter keys on, never a second uncoordinated allocator.
_DB_LANE: Final[LanePolicy] = LanePolicy(capacity=8)


async def query(sql: str, cfg: MaghzSettings, /, *, exec: Exec = Exec.RUN, **params: Scalar) -> RuntimeRail[QueryResult]:
    """Run one statement on the ledger off the event loop, lifting any driver fault to the rail once.

    The blocking connect-execute-release unit rides one `guarded(RetryClass.DB, run_sync, ...)` call:
    `guarded` drives the memoised retry caller around the `_DB_LANE.limiter`-bounded `run_sync` offload
    inside one resilience span and lifts the terminal `pg8000.Error`/`OSError`/`_TerminalError` through
    `async_boundary` exactly once. A transient connect flap or a `_DB_TRANSIENT` SQLSTATE replays within
    the canonical DB budget; a deterministic in-flight `DatabaseError` is re-spelled `_TerminalError` by
    `_classified` so it surfaces on the first attempt as one `Error(BoundaryFault(boundary))` naming the
    `sqlstate: message` cause, never four wasted retries. The connection is request-scoped: the native
    `with` bracket releases it on success, fault, and cancellation. `exec` selects the execution modality
    from `_EXEC`; the default `RUN` binds the named `:param` placeholders in `params`.

    Args:
        sql: The statement, with named `:param` placeholders for `RUN`/`PREPARED`.
        cfg: The validated settings owning the DSN and connect timeout.
        exec: The statement-execution modality keying `_EXEC` (`RUN`/`SCRIPT`/`PREPARED`).
        params: The named parameter bindings for the statement.

    Returns:
        `Ok(QueryResult)` on success, or `Error(BoundaryFault(boundary=(subject, detail)))` when the
        connect-or-execute unit fails (a terminal query fault on the first attempt, a transient one past
        the retry budget).
    """

    def _unit() -> QueryResult:
        with _connect(cfg) as conn:
            return _materialize(_classified(_EXEC[exec], conn, sql, params))

    return await guarded(RetryClass.DB, run_sync, _unit, subject=f"db.{exec.value}", limiter=_DB_LANE.limiter)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Exec", "Params", "QueryResult", "Scalar", "query"]
