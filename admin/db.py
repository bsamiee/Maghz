"""pg8000 boundary: the single connection and query surface over the maghz ledger.

pg8000 is pure-Python and blocking; every call offloads to a worker thread bounded by one
`CapacityLimiter` so the anyio event loop stays responsive and the connection fan-out is
capped. Driver faults are lifted to a typed `DbFault` rail at this boundary; interior code
never sees a raised database exception. Transient connection loss is retried at the canonical
`guard(RetryClass.DB)` resilience boundary before the final fault escapes to the rail.
"""

from collections.abc import Mapping
from typing import Literal

import anyio
from anyio.to_thread import run_sync
from expression import Error, Ok, Result
import msgspec
import pg8000
import pg8000.native

from admin.core import Envelope, fault
from admin.runtime import guard, RetryClass
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------

type Scalar = str | int | float | bool | bytes | None
type Boundary = Literal["connect", "query", "heptabase", "process"]


# --- [MODELS] --------------------------------------------------------------------------


class QueryResult(msgspec.Struct, frozen=True, gc=False):
    """Column names plus the materialized rows of one statement."""

    columns: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]


# --- [ERRORS] --------------------------------------------------------------------------


class DbFault(msgspec.Struct, frozen=True, gc=False):
    """A boundary failure tagged by the operation that raised it, projecting to one fault envelope."""

    op: Boundary
    message: str

    def envelope(self, **context: str) -> Envelope:
        """Project this boundary failure to a `fault` envelope, merging any extra context."""
        return fault(self.message, {"op": self.op, **context})


# --- [SERVICES] ------------------------------------------------------------------------

# One process-wide limiter caps the pg8000 worker-thread fan-out at 8 concurrent blocking
# connections; every `run_sync` offload borrows it so the ledger boundary is bounded rather
# than spawning an unbounded thread per concurrent query. This is the pre-runtime bootstrap
# owner; the runtime LanePolicy supersedes it in place without a second limiter.
_DB_LIMITER: anyio.CapacityLimiter = anyio.CapacityLimiter(8)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _connect(cfg: MaghzSettings) -> pg8000.native.Connection:
    dsn = cfg.database.dsn
    host = dsn.hosts()[0]  # PostgresDsn is a MultiHostUrl: components live under hosts(), not as attributes
    return pg8000.native.Connection(
        user=host["username"] or "maghz",
        host=host["host"] or "127.0.0.1",
        port=host["port"] or 15435,
        database=(dsn.path or "/maghz").removeprefix("/"),
        password=host["password"],
        timeout=cfg.database.connect_timeout,
    )


def _run_blocking(cfg: MaghzSettings, sql: str, params: Mapping[str, Scalar]) -> Result[QueryResult, DbFault]:
    # `_connect` is OUTSIDE the try: a transient `pg8000.Error`/`OSError` on connection loss
    # raises out of this offload un-tagged, so `guard(RetryClass.DB)` retries the whole unit at
    # the canonical resilience boundary and a survivor of the budget is tagged `connect` in
    # `query`'s outer catch — never here. Once connected, an in-flight execution fault is NOT
    # transient: the try below tags it `query` and returns it on the rail without retry.
    conn = _connect(cfg)

    def _release(outcome: Result[QueryResult, DbFault]) -> Result[QueryResult, DbFault]:
        # A close() raise must not mask the query outcome; the handle is released
        # best-effort. A close-time driver fault surfaces only when the query itself
        # succeeded — an in-flight query fault always wins the channel.
        try:
            conn.close()
        except (pg8000.Error, OSError) as exc:
            return outcome if outcome.is_error() else Error(DbFault(op="query", message=str(exc)))
        return outcome

    try:
        rows = conn.run(sql, **params)
        columns = tuple(column["name"] for column in conn.columns)
        return _release(Ok(QueryResult(columns=columns, rows=tuple(tuple(row) for row in rows))))
    except (pg8000.Error, OSError) as exc:
        return _release(Error(DbFault(op="query", message=str(exc))))


async def query(sql: str, cfg: MaghzSettings, /, **params: Scalar) -> Result[QueryResult, DbFault]:
    """Run one statement on the ledger off the event loop, lifting faults to a rail.

    The blocking connect-and-run unit is the retry target: `guard(RetryClass.DB)` drives the
    `_DB_LIMITER`-bounded `run_sync` offload and replays a transient `pg8000.Error`/`OSError`
    connect flap within the canonical DB budget, so a flaky connect converges rather than
    surfacing on the first failure. A connect fault that survives the budget is re-raised by
    `guard` and folds here to the `connect` rail; an in-flight query fault never escapes the
    offload — `_run_blocking` already returns it on the `query` rail without retry.

    Args:
        sql: The statement to execute with named `:param` placeholders.
        cfg: The validated settings owning the DSN and connect timeout.
        params: The named parameter bindings for the statement.

    Returns:
        `Ok(QueryResult)` on success, `Error(DbFault)` tagged `connect` when the connection
        cannot be established within the retry budget, or `query` when execution fails.
    """

    async def _offload() -> Result[QueryResult, DbFault]:
        return await run_sync(lambda: _run_blocking(cfg, sql, params), limiter=_DB_LIMITER)

    try:
        return await guard(RetryClass.DB)(_offload)
    except (pg8000.Error, OSError) as exc:
        return Error(DbFault(op="connect", message=str(exc)))


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Boundary", "DbFault", "QueryResult", "Scalar", "query"]
