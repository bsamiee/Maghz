"""Receipt owner: the closed `Receipt` evidence family and the one process-global `Signals` service.

`Receipt` is a shape-polymorphic `@tagged_union`: `Receipt.of(owner, evidence)` discriminates on the
concrete evidence shape (`BoundaryFault`, `(DrainReceipt, rss)`, `(phase, subject, facts)`), and
`project` folds each case to a `(level, event_dict)` pair via total `match`/`assert_never`. `Signals`
is a `ClassVar`-backed singleton — `configure` owns the one structlog pipeline (stderr-only; the CLI
`Envelope` keeps stdout), and `emit`/`emit_async` dispatch the projected level by name straight onto
the `FilteringBoundLogger` (`info`/`ainfo`/...), so a new level is one `_LEVEL_NUMBER` row, not a table.
`@receipted` wraps a `ReceiptContributor`-returning op and emits an `emitted`-phase receipt on return;
`@drained` wraps a drain, probes `psutil` RSS, and emits a `drained` receipt. `@drained` is outermost.
"""

from collections.abc import Awaitable, Callable
import functools
import inspect
import sys
from typing import assert_never, ClassVar, Final, Literal, Protocol, runtime_checkable

from expression import case, tag, tagged_union
from expression.collections import Map
import msgspec
import psutil
import structlog

from admin.runtime.lanes import DrainReceipt
from admin.runtime.rails import BoundaryFault


# --- [TYPES] ---------------------------------------------------------------------------

type Phase = Literal["admitted", "retry", "emitted"]
type ReceiptTag = Literal["fact", "rejected", "drained"]
type LogLevel = Literal["debug", "info", "warning", "error"]
type Contributing[**P] = Callable[P, ReceiptContributor | Awaitable[ReceiptContributor]]
type Draining[**P] = Callable[P, Awaitable[DrainReceipt]]
type Redaction = frozenset[str]


# --- [CONSTANTS] -----------------------------------------------------------------------

_LOGGER_NAME = "maghz.runtime"
_COUNTER_SLOTS: Final = ("accepted", "completed", "cancelled", "rejected", "hit")


# --- [MODELS] --------------------------------------------------------------------------


@runtime_checkable
class ReceiptContributor(Protocol):
    """The structural contract a domain operation satisfies to feed `@receipted` its evidence."""

    def contribute(self) -> tuple[str, dict[str, object]]:
        """Return the `(subject, facts)` pair the receipt aspect stamps into an `emitted` receipt."""
        ...


@tagged_union(frozen=True)
class Receipt:
    """The closed evidence family minted by `Receipt.of` and folded to a log event by `project`."""

    tag: ReceiptTag = tag()
    fact: tuple[Phase, str, str, dict[str, object]] = case()
    rejected: tuple[str, BoundaryFault] = case()
    drained: tuple[str, DrainReceipt, int] = case()

    @classmethod
    def of(cls, owner: str, evidence: object) -> Receipt:
        """Mint a receipt for `owner`, discriminating on the concrete shape of `evidence`.

        Args:
            owner: The owning subject stamped into the receipt's owner slot.
            evidence: A `BoundaryFault` -> `rejected`, a `(DrainReceipt, rss)` -> `drained`, or a
                `(phase, subject, facts)` -> `fact`.

        Returns:
            The matching `Receipt` case.

        Raises:
            TypeError: `evidence` is none of the three admitted shapes — a caller contract violation,
                never folded into a domain fault.
        """
        match evidence:
            case BoundaryFault():
                return cls(rejected=(owner, evidence))
            case (DrainReceipt() as receipt, int() as rss):
                return cls(drained=(owner, receipt, rss))
            case (str() as phase, str() as subject, dict() as facts):
                return cls(fact=(phase, owner, subject, facts))
            case _:
                msg = f"Receipt.of admits BoundaryFault, (DrainReceipt, int), or (phase, subject, facts); got {type(evidence).__name__}"
                raise TypeError(msg)

    def project(self) -> tuple[LogLevel, dict[str, object]]:
        """Fold this receipt to a `(level, event_dict)` pair for the structlog pipeline.

        Returns:
            The log level and the event dict; `rejected` -> `warning` with the fault facts, `fact`
            -> the phase level with its facts, `drained` -> `info` with the drain counters and RSS.
        """
        match self.tag:
            case "rejected":
                owner, fault = self.rejected
                return "warning", {"event": "rejected", "owner": owner, **fault.facts()}
            case "fact":
                phase, owner, subject, facts = self.fact
                return PHASE_LEVEL[phase], {"event": phase, "owner": owner, "subject": subject, **facts}
            case "drained":
                owner, receipt, rss_bytes = self.drained
                counters = {slot: getattr(receipt, slot) for slot in _COUNTER_SLOTS}
                return "info", {"event": "drained", "owner": owner, "rss_bytes": rss_bytes, **counters}
            case _ as unreachable:  # pragma: no cover
                assert_never(unreachable)


# --- [SERVICES] ------------------------------------------------------------------------


class Signals:
    """The process-global structured-log service: configured once, emits receipts to stderr."""

    _logger: ClassVar[structlog.BoundLogger] = structlog.get_logger(_LOGGER_NAME)

    @classmethod
    def configure(cls, fmt: Literal["json", "console"], *, level: LogLevel = "info") -> None:
        """Configure the one structlog pipeline: stderr sink, with the resolved level and renderer.

        Args:
            fmt: `json` selects the deterministic `msgspec`-serialized `JSONRenderer` over a bytes
                sink; `console` selects the dev `ConsoleRenderer` over a stderr print sink.
            level: The minimum level the filtering bound logger admits; sub-threshold calls no-op.
        """
        encoder = msgspec.json.Encoder(enc_hook=repr, order="deterministic")
        json_chain = (structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer(serializer=lambda event, **_: encoder.encode(event)))
        console_chain = (structlog.dev.ConsoleRenderer(colors=False),)
        prelude = (structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"))
        structlog.configure(
            processors=[*prelude, *(json_chain if fmt == "json" else console_chain)],
            wrapper_class=structlog.make_filtering_bound_logger(_LEVEL_NUMBER[level]),
            logger_factory=structlog.BytesLoggerFactory(file=sys.stderr.buffer) if fmt == "json" else structlog.PrintLoggerFactory(file=sys.stderr),
            cache_logger_on_first_use=True,
        )
        cls._logger = structlog.get_logger(_LOGGER_NAME)

    @classmethod
    def emit(cls, receipt: Receipt, *, redact: Redaction | None = None) -> None:
        """Project `receipt` and write one structured line at its level, omitting any `redact` keys.

        Args:
            receipt: The evidence to project and emit.
            redact: Field keys to drop from the event dict before emission.
        """
        level, event = receipt.project()
        getattr(cls._logger, level)(str(event.pop("event")), **_redacted(event, redact))

    @classmethod
    async def emit_async(cls, receipt: Receipt, *, redact: Redaction | None = None) -> None:
        """Project `receipt` and await one structured line at its level, omitting any `redact` keys.

        Args:
            receipt: The evidence to project and emit.
            redact: Field keys to drop from the event dict before emission.
        """
        level, event = receipt.project()
        await getattr(cls._logger, f"a{level}")(str(event.pop("event")), **_redacted(event, redact))


# --- [OPERATIONS] ----------------------------------------------------------------------


def _redacted(event: dict[str, object], redact: Redaction | None) -> dict[str, object]:
    """Drop the `redact` keys from an event dict; `None` redaction returns it unchanged."""
    return event if redact is None else {key: value for key, value in event.items() if key not in redact}


def _probe_rss() -> int:
    """Snapshot the own-process RSS in bytes in one syscall; access denial folds to `0`."""
    try:
        process = psutil.Process()
        with process.oneshot():
            return process.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0


def _synchronous(produced: ReceiptContributor | Awaitable[ReceiptContributor]) -> ReceiptContributor:
    """Narrow a sync `@receipted` op result to its contributor; an awaitable here is a misuse."""
    if inspect.isawaitable(produced):
        msg = "a sync @receipted op must not return an awaitable contributor"
        raise TypeError(msg)
    return produced


def receipted[**P](owner: str, phase: Phase, *, redact: Redaction | None = None) -> Callable[[Contributing[P]], Contributing[P]]:
    """Wrap a `ReceiptContributor`-returning op to emit one `fact`-phase receipt on return.

    Args:
        owner: The owning subject stamped into the minted receipt.
        phase: The receipt phase emitted on a successful return.
        redact: Field keys to drop from the emitted event dict.

    Returns:
        A parameter-shape-preserving decorator; `inspect.iscoroutinefunction` selects the async body.
    """

    def _decorate(op: Contributing[P]) -> Contributing[P]:
        if inspect.iscoroutinefunction(op):

            @functools.wraps(op)
            async def _async(*args: P.args, **kwargs: P.kwargs) -> ReceiptContributor:
                produced = op(*args, **kwargs)
                contributor = await produced if inspect.isawaitable(produced) else produced
                subject, facts = contributor.contribute()
                await Signals.emit_async(Receipt.of(owner, (phase, subject, facts)), redact=redact)
                return contributor

            return _async

        @functools.wraps(op)
        def _sync(*args: P.args, **kwargs: P.kwargs) -> ReceiptContributor:
            produced = op(*args, **kwargs)
            contributor = _synchronous(produced)
            subject, facts = contributor.contribute()
            Signals.emit(Receipt.of(owner, (phase, subject, facts)), redact=redact)
            return contributor

        return _sync

    return _decorate


def drained[**P](owner: str, *, redact: Redaction | None = None) -> Callable[[Draining[P]], Draining[P]]:
    """Wrap a drain-calling `async def` to probe RSS and emit one `drained` receipt on exit.

    Args:
        owner: The owning subject stamped into the minted `drained` receipt.
        redact: Field keys to drop from the emitted event dict.

    Returns:
        A parameter-shape-preserving decorator; outermost when stacked with `@receipted`.
    """

    def _decorate(op: Draining[P]) -> Draining[P]:
        @functools.wraps(op)
        async def _async(*args: P.args, **kwargs: P.kwargs) -> DrainReceipt:
            receipt = await op(*args, **kwargs)
            await Signals.emit_async(Receipt.of(owner, (receipt, _probe_rss())), redact=redact)
            return receipt

        return _async

    return _decorate


# --- [TABLES] --------------------------------------------------------------------------

# Phase -> log level, and level -> stdlib numeric threshold the filtering bound logger admits. The
# level NAME is itself the dispatch key: `emit` calls `getattr(logger, level)` and `emit_async`
# `getattr(logger, f"a{level}")`, so the FilteringBoundLogger owns the sync/async method pair and a
# new level is one `_LEVEL_NUMBER`/`LogLevel` entry rather than a hand-paired lambda row.
_LEVEL_NUMBER: Final[Map[LogLevel, int]] = Map.of_seq([("debug", 10), ("info", 20), ("warning", 30), ("error", 40)])
PHASE_LEVEL: Final[Map[Phase, LogLevel]] = Map.of_seq([("admitted", "debug"), ("retry", "warning"), ("emitted", "info")])


# --- [COMPOSITION] ---------------------------------------------------------------------

__all__ = ["PHASE_LEVEL", "Phase", "Receipt", "ReceiptContributor", "Redaction", "Signals", "drained", "receipted"]
