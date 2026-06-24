"""Receipt owner: the self-projecting `Receipt` evidence union and the `Signals` log service.

`Receipt` is the one tagged-union evidence family over `fact`/`rejected`/`drained`; `Receipt.of`
is the shape-polymorphic factory minting each case by discriminating its input evidence, and
`Receipt.project` is the total `match` folding every case to a `(LogLevel, EventDict)` pair, so
`Signals.emit` is a renderer-agnostic fold over the union rather than three hand-built dict arms.

`Signals` owns the one `structlog` chain — `trace_context` injects the active span ids and the
chain-resident `redact` processor applies the per-emit `Redaction` to the fully-assembled line
(receipt facts plus the ambient `merge_contextvars` context) so a `bind_contextvars`-sourced
classified field cannot bypass it. `emit`/`emit_async` are the renderer-agnostic sink pair: one
`_render` fold yields a `(LevelBinding, name, fields)` triple per receipt off the closed
`LEVEL_METHOD` table, `emit` driving the sync selector and `emit_async` awaiting the loop-friendly
`a*` mirror so a high-volume async path offloads render-and-sink to a worker thread.

`ReceiptContributor` is the streamed evidence port siblings implement to yield a receipt sequence;
`@receipted` harvests that stream and emits on exit, and `@drained` wraps a raw drain into a
`drained` receipt — receipt production is a decorator rail, never inline `emit` calls.
"""

from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from functools import wraps
from hashlib import blake2b
from inspect import isawaitable, iscoroutinefunction
import sys
from typing import assert_never, Final, Literal, Protocol, runtime_checkable, Self

from expression import case, Option, tag, tagged_union
from expression.collections import Map
import msgspec
from opentelemetry import trace
import psutil
import structlog

from admin.runtime.lanes import DRAIN_COLUMNS, DrainReceipt
from admin.runtime.rails import BoundaryFault


# --- [TYPES] ---------------------------------------------------------------------------

type Phase = Literal["admitted", "retry", "emitted"]
type ReceiptTag = Literal["fact", "rejected", "drained"]
type LogLevel = Literal["debug", "info", "warning", "error"]
type Format = Literal["json", "console"]
type Classification = Literal["drop", "mask", "hash"]
type EventDict = dict[str, object]
type Evidence = tuple[Phase, str, dict[str, object]] | BoundaryFault | DrainReceipt[object]
type RedactionSpec = Redaction | Map[str, Classification] | frozenset[str]
type Streamable = Receipt | Iterable[Receipt] | ReceiptContributor
type Contributing[**P, R: ReceiptContributor] = Callable[P, R] | Callable[P, Awaitable[R]]
type Draining[**P] = Callable[P, Awaitable[DrainReceipt[object]]]
type ProcessorEvent = structlog.typing.EventDict
type Processor = structlog.typing.Processor
type WrappedLogger = structlog.typing.WrappedLogger
type BoundLogger = SinkLogger
type LevelSelector[R] = Callable[[BoundLogger], Callable[..., R]]
type LevelBinding = tuple[LevelSelector[object], LevelSelector[Awaitable[object]]]
# Per-format render tail + sink factory read once off `_FORMAT[fmt]`: the renderer-last processors and a
# thunk minting the matching structlog logger factory ride one row so `configure` reads the json/console
# axis once, not twice. The factory thunk defers `sys.stderr` capture to configure time.
type LoggerFactory = Callable[..., WrappedLogger]
type FormatBinding = tuple[tuple[Processor, ...], Callable[[], LoggerFactory]]


# --- [CONSTANTS] -----------------------------------------------------------------------

_LOGGER_NAME: Final = "maghz.runtime"

REDACTED: Final[str] = "***"

# The reserved event key the per-emit `Redaction` rides on so the chain-resident `redact` processor
# scrubs the whole assembled line (receipt facts + the ambient merge_contextvars context), not just
# the receipt's own projected facts; stripped by `apply` before the line renders.
_REDACTION: Final[str] = "_redaction"

# One renderer/redaction encoder: `enc_hook=repr` degrades any value outside the native JSON set to
# its repr so a bound domain object never raises on the hot logging path, and `order="deterministic"`
# makes the `hash` class canonical so the same structured secret yields the same blake2b correlation
# token across lines regardless of mapping insertion order — the one encoder serves both surfaces.
_ENCODE: Final[Callable[[object], bytes]] = msgspec.json.Encoder(enc_hook=repr, order="deterministic").encode

# Own-process handle minted once; the drained point-fact reads RSS off it rather than re-minting a
# `Process()` per projection. A dead-process race folds to an omitted slot, never a raised emit.
_PROCESS: Final[psutil.Process] = psutil.Process()
_PROCESS_FAULTS: Final[tuple[type[psutil.Error], ...]] = (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied)


# --- [MODELS] --------------------------------------------------------------------------


@tagged_union(frozen=True)
class Receipt:
    """The one closed evidence family minted by `Receipt.of` and folded to a log event by `project`.

    The three lifecycle phases share one `fact` case routing a `Phase` literal — `admitted`/`retry`/
    `emitted` are a value the case carries, not three identical-payload siblings; `rejected` and
    `drained` are distinct cases because their payloads differ. A new phase is one `PHASE_LEVEL` row,
    a new distinct-payload kind one case plus its `project`/`of` arm.
    """

    tag: ReceiptTag = tag()
    fact: tuple[Phase, str, str, dict[str, object]] = case()
    rejected: tuple[str, BoundaryFault] = case()
    drained: tuple[str, DrainReceipt[object]] = case()

    @staticmethod
    def of(owner: str, evidence: Evidence) -> Receipt:
        """Mint a receipt for `owner`, discriminating on the concrete shape of `evidence`.

        A `BoundaryFault` mints `rejected` carrying the owner plus the whole fault (the subject deferred
        to `facts()` at projection rather than pre-extracted into a redundant slot), a `DrainReceipt`
        mints `drained`, and a `(phase, subject, facts)` triple mints `fact`. A new evidence shape is
        one `match` arm here, never a hand-built case constructor at a call site.

        Returns:
            The matching `Receipt` case for the discriminated evidence shape.
        """
        match evidence:
            case BoundaryFault() as fault:
                return Receipt(rejected=(owner, fault))
            case DrainReceipt() as drain:
                return Receipt(drained=(owner, drain))
            case (phase, subject, facts):
                return Receipt(fact=(phase, owner, subject, facts))
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed Evidence alias
                assert_never(unreachable)

    def project(self) -> tuple[LogLevel, EventDict]:
        """Fold this receipt to a `(level, event_dict)` pair for the structlog pipeline.

        The `fact` case keys its level off `PHASE_LEVEL` with no phase branch; `rejected` spreads the
        `BoundaryFault.facts()` projection rather than a private fault walk so the log line's slot set
        stays in lockstep with the fault owner; `drained` reads the five outcome counts per-column off
        the typed `DrainReceipt` plus the RSS fact, never a full `asdict` allocating its containers.

        Returns:
            The `(level, event_dict)` pair the renderer-agnostic `emit` fold drives.
        """
        match self.tag:
            case "fact":
                phase, owner, subject, facts = self.fact
                return PHASE_LEVEL[phase], {"event": phase, "owner": owner, "subject": subject, **facts}
            case "rejected":
                owner, fault = self.rejected
                return "warning", {"event": "rejected", "owner": owner, **fault.facts()}
            case "drained":
                owner, drain = self.drained
                return "info", {"event": "drained", "owner": owner, **_rss(), **{column: getattr(drain, column) for column in DRAIN_COLUMNS}}
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed ReceiptTag literal
                assert_never(unreachable)


@runtime_checkable
class SinkLogger(Protocol):
    """The structural sink port `_render` drives: a bound logger exposing the four levels and their `a*` mirrors.

    Names exactly the capability `LEVEL_METHOD` selects and `_sink` binds — the `(sync, async)` level-method
    pair per `LogLevel` plus `bind`. A `structlog` `FilteringBoundLogger` and a `testing.capture_logs`/
    `wrap_logger` sink both satisfy it structurally, whereas the broad `structlog.typing.FilteringBoundLogger`
    Protocol declares an `err` member the generated filtering logger omits, so the package beartype claw
    rejects a real bound logger against it — this owner-local port names only the consumed methods and is the
    contract the claw can admit at the `_sink` boundary.
    """

    def bind(self, **kwargs: object) -> Self: ...
    def debug(self, event: str, **kwargs: object) -> object: ...
    def info(self, event: str, **kwargs: object) -> object: ...
    def warning(self, event: str, **kwargs: object) -> object: ...
    def error(self, event: str, **kwargs: object) -> object: ...
    def adebug(self, event: str, **kwargs: object) -> Awaitable[object]: ...
    def ainfo(self, event: str, **kwargs: object) -> Awaitable[object]: ...
    def awarning(self, event: str, **kwargs: object) -> Awaitable[object]: ...
    def aerror(self, event: str, **kwargs: object) -> Awaitable[object]: ...


@runtime_checkable
class ReceiptContributor(Protocol):
    """The streamed evidence port a sibling implements to yield its typed receipts into the pipeline.

    `contribute` yields an `Iterable[Receipt]` so a multi-phase contributor streams several facts
    rather than forcing one receipt per call; `@receipted` harvests the stream on the op's exit.
    """

    def contribute(self) -> Iterable[Receipt]:
        """Yield this owner's typed receipt stream into the pipeline."""
        ...


class Redaction(msgspec.Struct, frozen=True):
    """The `Classification`-keyed field-policy table the chain-resident `redact` processor applies.

    `classified` maps a field key to its `drop`/`mask`/`hash` transform; `apply` scrubs the assembled
    line, dropping a field by yielding zero pairs, masking to the fixed sentinel, or hashing to a
    truncated keyed `blake2b` correlation token over the deterministic encoding of the value — so two
    lines carrying the same secret correlate by token without leaking it. An un-classified field keeps
    through the structural `Nothing` of `try_find`, so `_reduce` stays total over the closed vocabulary.
    """

    classified: Map[str, Classification]
    salt: bytes = b"maghz"

    @staticmethod
    def of(spec: RedactionSpec) -> Redaction:
        """Normalize a redaction spec to one `Redaction` so every aspect head admits the union once.

        A `frozenset[str]` is the dominant "drop these field keys" modality folded to a `drop`-classified
        table; a `Map[str, Classification]` is the explicit per-field classification; a `Redaction` passes
        through. A consumer states `redaction=frozenset({"rss_bytes"})` at its call site rather than hand-building
        `Redaction(classified=Map.of_seq([("rss_bytes", "drop")]))`, and a new policy modality is one match arm.

        Returns:
            The matching `Redaction` for the discriminated spec shape.
        """
        match spec:
            case Redaction():
                return spec
            case frozenset():
                return Redaction(classified=Map.of_seq([(str(key), "drop") for key in spec]))
            case Map():
                return Redaction(classified=spec)
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed RedactionSpec union
                assert_never(unreachable)

    def apply(self, facts: Mapping[str, object]) -> EventDict:
        """Scrub `facts` per the classification table, stripping the `_REDACTION` carrier key.

        Returns:
            A fresh event dict with classified fields dropped, masked, or hashed and the carrier removed.
        """
        return {key: redacted for key, value in facts.items() if key != _REDACTION for redacted in self._classify(key, value)}

    def _classify(self, key: str, value: object) -> tuple[object, ...]:
        return self.classified.try_find(key).map(lambda cls: self._reduce(cls, value)).default_value((value,))

    def _reduce(self, classification: Classification, value: object) -> tuple[object, ...]:
        match classification:
            case "drop":
                return ()
            case "mask":
                return (REDACTED,)
            case "hash":
                return (blake2b(_ENCODE(value), key=self.salt, digest_size=8).hexdigest(),)
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed Classification set
                assert_never(unreachable)


# The keep-all policy the chain-resident `redact` folds a line carrying no bound `Redaction` through;
# depends on the `Redaction` model so it anchors here, never top-level [CONSTANTS].
_OPEN: Final[Redaction] = Redaction(classified=Map.empty())


# --- [OPERATIONS] ----------------------------------------------------------------------


def _rss() -> EventDict:
    """The own-process RSS slot, omitted on a dead-process race rather than raising on the emit path.

    The narrow `_PROCESS_FAULTS` catch is the marked boundary adapter over `psutil`'s real
    dead/zombie/denied surface: the drained projection stays a pure dict spread that attaches the slot
    on success and omits it on the race, never lifting a transient process fault onto the log path. The
    slot key is `rss_bytes` — the one canonical field name the `@drained` consumer's
    `redaction=frozenset({"rss_bytes"})` drop targets, so the drop and the mint cannot name it two ways.

    Returns:
        A single-key `{"rss_bytes": bytes}` slot on success, or an empty dict on a dead-process race.
    """
    try:
        return {"rss_bytes": _PROCESS.memory_info().rss}
    except _PROCESS_FAULTS:
        return {}


def _stream(source: Streamable) -> Iterable[Receipt]:
    """Normalize every emit input shape to one `Iterable[Receipt]` through one `match`."""
    match source:
        case Receipt():
            return (source,)
        case ReceiptContributor():
            return source.contribute()
        case _:
            return source


def _render(source: Streamable, spec: RedactionSpec) -> Iterator[tuple[LevelBinding, str, EventDict]]:
    """Normalize the spec once, project each receipt, bind the `Redaction` under `_REDACTION`, yield the triple.

    The one render fold both sinks share: `Redaction.of` admits the bare drop-set / classification `Map` /
    full `Redaction` once at the head -> `project` -> split the level into its `(sync, async)` selector pair
    -> carry the `Redaction` onto the event, so `emit`/`emit_async` differ only by which half they drive and
    neither re-spells the spec normalization. Redaction is NOT applied here — the chain-resident `redact`
    processor runs it after the contextvars injector so it scrubs the whole line; this fold only carries it in.

    Yields:
        A `(LevelBinding, event_name, fields)` triple per receipt, the fields carrying the `Redaction`.
    """
    redaction = Redaction.of(spec)
    for receipt in _stream(source):
        level, event = receipt.project()
        yield LEVEL_METHOD[level], str(event.pop("event")), event | {_REDACTION: redaction}


def _serialize(event: ProcessorEvent, **_: object) -> bytes:
    """The `JSONRenderer` serializer adapter: absorb structlog's forwarded `default=` kwarg, encode once.

    `JSONRenderer` calls `serializer(event_dict, default=...)`, but the canonical `msgspec` encoder takes
    no keyword arguments — this thin adapter drops the forwarded kwargs and delegates to the one `_ENCODE`
    shared with the `hash` redaction class, so native ints/floats and domain `Struct` facts reach the line
    through the single fast deterministic encoder rather than a stdlib `json` re-encode.

    Returns:
        The deterministic `msgspec`-encoded JSON bytes for the structlog line.
    """
    return _ENCODE(event)


def redact(_: object, __: str, event: ProcessorEvent) -> ProcessorEvent:
    """Chain-resident redaction: scrub the assembled line per the bound `Redaction`, or keep-all.

    Pattern-narrows the value bound under `_REDACTION` (the `Redaction` `_render` is the sole binder of)
    and scrubs the fully-assembled line — receipt facts and the `merge_contextvars` ambient context — so
    a classified field arriving through `bind_contextvars` cannot bypass redaction the way a pre-chain
    `apply` does. A line carrying no bound `Redaction` (a direct log call) keeps all through `_OPEN`.

    Returns:
        The scrubbed event with the `_REDACTION` carrier stripped.
    """
    return Option.of_optional(event.get(_REDACTION)).default_value(_OPEN).apply(event)


def trace_context(_: object, __: str, event: ProcessorEvent) -> ProcessorEvent:
    """Inject the active span's `trace_id`/`span_id`/`trace_flags` into every event when one is valid.

    Returns:
        The event enriched with the active trace ids, or unchanged when no valid span is current.
    """
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event.update(trace_id=trace.format_trace_id(ctx.trace_id), span_id=trace.format_span_id(ctx.span_id), trace_flags=int(ctx.trace_flags))
    return event


# --- [SERVICES] ------------------------------------------------------------------------


class Signals:
    """The process-global structured-log service: configured once, emits receipts to stderr."""

    @staticmethod
    def configure(fmt: Format = "json", *, level: LogLevel = "info") -> None:
        """Configure the one structlog chain: stderr sink, the resolved level, and the selected renderer.

        The shared chain orders `merge_contextvars` (the ambient command/context first) -> `add_log_level`
        -> the custom `trace_context` -> the custom `redact` (after the contextvars/trace injectors so it
        scrubs the whole line) -> `CallsiteParameterAdder` -> `dict_tracebacks` (a bound `BoundaryFault`/
        `exc_info` to a JSON-safe stack) -> `TimeStamper`. The renderer tail and the matching sink factory
        ride one `_FORMAT[fmt]` row read once — `EventRenamer(to="body")` + the `JSONRenderer` over the
        deterministic `msgspec` encoder with a bytes sink, or the dev `ConsoleRenderer` with a text sink —
        so the json/console axis is the one discriminant, never read twice. `make_filtering_bound_logger`
        compiles sub-threshold levels to no-ops on both the sync and the `a*` async-mirror methods.
        """
        render, factory = _FORMAT[fmt]
        structlog.configure(
            processors=[*_CHAIN, *render],
            wrapper_class=structlog.make_filtering_bound_logger(_LEVEL_NUMBER[level]),
            logger_factory=factory(),
            cache_logger_on_first_use=True,
        )

    @staticmethod
    def emit(source: Streamable, redaction: RedactionSpec = _OPEN, *, sink: BoundLogger | None = None) -> None:
        """Project `source` and write one structured line per receipt at its level through the sync sink."""
        log = _sink(sink)
        for (sync, _), name, fields in _render(source, redaction):
            sync(log)(name, **fields)

    @staticmethod
    async def emit_async(source: Streamable, redaction: RedactionSpec = _OPEN, *, sink: BoundLogger | None = None) -> None:
        """Project `source` and await one structured line per receipt at its level through the `a*` mirror."""
        log = _sink(sink)
        for (_, amirror), name, fields in _render(source, redaction):
            await amirror(log)(name, **fields)


def _sink(sink: BoundLogger | None) -> BoundLogger:
    """The one default-sink resolution both emit arms share: an explicit override or the global logger.

    An explicit `sink` overrides for the `testing.capture_logs`/`wrap_logger` seam; an absent one folds
    to `structlog.get_logger(_LOGGER_NAME).bind()` fetched per emit (never cached as a module constant,
    so it always reflects the active `configure`). The `.bind()` materializes the lazy proxy into the
    configured `FilteringBoundLogger` so the per-emit method calls hit the bound chain directly; the
    override contract lives once rather than a ternary duplicated across the `emit`/`emit_async` pair.

    Returns:
        The passed `sink`, or the freshly bound configured runtime logger when absent.
    """
    return Option.of_optional(sink).default_with(lambda: structlog.get_logger(_LOGGER_NAME).bind())


def receipted[**P, R: ReceiptContributor](redaction: RedactionSpec = _OPEN) -> Callable[[Contributing[P, R]], Contributing[P, R]]:
    """Wrap a `ReceiptContributor`-returning op to harvest and emit its receipt stream on exit.

    The AOP aspect routes a coroutine to the loop-friendly `emit_async` and a sync op to `emit`,
    dispatched once on `iscoroutinefunction` at decoration; a measured kernel declares `@receipted(redaction)`
    and threads no emit call through its body. The `R: ReceiptContributor` bound preserves the concrete
    subtype the decorator harvests rather than erasing it to the port, so the consumer reads the concrete
    receipt member off the return value without a static type error. The `RedactionSpec` admits the bare
    drop-set, the classification table, or a full `Redaction`, normalized once at the `emit` head.

    Returns:
        A parameter-shape-preserving decorator over the contributor-returning op, sync or async.
    """

    def _decorate(operation: Contributing[P, R]) -> Contributing[P, R]:
        if iscoroutinefunction(operation):

            @wraps(operation)
            async def _async(*args: P.args, **kwargs: P.kwargs) -> R:
                produced = operation(*args, **kwargs)
                contributor = await produced if isawaitable(produced) else produced
                await Signals.emit_async(contributor, redaction)
                return contributor

            return _async

        @wraps(operation)
        def _sync(*args: P.args, **kwargs: P.kwargs) -> R:
            produced = operation(*args, **kwargs)
            if isawaitable(produced):
                msg = "a sync @receipted op must not return an awaitable contributor"
                raise TypeError(msg)
            Signals.emit(produced, redaction)
            return produced

        return _sync

    return _decorate


def drained[**P](owner: str, *, redaction: RedactionSpec = _OPEN) -> Callable[[Draining[P]], Draining[P]]:
    """Wrap a drain-returning `async def` to mint and emit one `drained` receipt on exit.

    Composes the unified rail — `Receipt.of(owner, drain)` discriminates the raw `DrainReceipt` into the
    `drained` case whose projection folds the RSS fact and the outcome columns — so the aspect threads no
    inline `emit` and re-derives no drain shape. `redaction` admits the bare `frozenset[str]` drop-set
    (`@drained("automation", redaction=frozenset({"rss_bytes"}))`), the classification `Map`, or a full
    `Redaction`, normalized once at the `emit_async` head. Outermost when stacked with `@receipted`.

    Returns:
        A parameter-shape-preserving decorator over the drain-returning async op.
    """

    def _decorate(operation: Draining[P]) -> Draining[P]:
        @wraps(operation)
        async def _async(*args: P.args, **kwargs: P.kwargs) -> DrainReceipt[object]:
            drain = await operation(*args, **kwargs)
            await Signals.emit_async(Receipt.of(owner, drain), redaction)
            return drain

        return _async

    return _decorate


# --- [TABLES] --------------------------------------------------------------------------

# Phase -> log level: `admitted` debugs, a scheduled `retry` warns, `emitted` infos — the `fact` case
# keys its level off this row with no phase branch, so a new phase is one entry reaching `project` for
# free. `retry` is the `resilience` on-retry seam's phase; the warning level is load-bearing there.
PHASE_LEVEL: Final[Map[Phase, LogLevel]] = Map.of_seq([("admitted", "debug"), ("retry", "warning"), ("emitted", "info")])

# Level -> stdlib numeric threshold the filtering bound logger admits at configure time.
_LEVEL_NUMBER: Final[Map[LogLevel, int]] = Map.of_seq([("debug", 10), ("info", 20), ("warning", 30), ("error", 40)])

# The chain prefix both formats share, in order; the per-format renderer tail rides `_FORMAT[fmt]`. Depends
# on the `trace_context`/`redact` custom processors so it anchors here, never top-level [CONSTANTS].
_CHAIN: Final[tuple[Processor, ...]] = (
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    trace_context,
    redact,
    structlog.processors.CallsiteParameterAdder(),
    structlog.processors.dict_tracebacks,
    structlog.processors.TimeStamper(fmt="iso"),
)

# Format -> (renderer tail, sink factory): the json/console axis as one row `configure` reads once. The json
# row renames `event` to the OTLP `body` key, renders through the deterministic `msgspec` encoder, and sinks
# bytes to stderr; the console row renders the human dev line and sinks text. Depends on `_serialize` so it
# anchors here, never top-level [CONSTANTS].
_FORMAT: Final[Map[Format, FormatBinding]] = Map.of_seq([
    (
        "json",
        (
            (structlog.processors.EventRenamer(to="body"), structlog.processors.JSONRenderer(serializer=_serialize)),
            lambda: structlog.BytesLoggerFactory(file=sys.stderr.buffer),
        ),
    ),
    (
        "console",
        ((structlog.dev.ConsoleRenderer(colors=False),), lambda: structlog.PrintLoggerFactory(file=sys.stderr)),
    ),
])

# The bounded LogLevel vocabulary owns which FilteringBoundLogger method each receipt emits through —
# one row per level carrying the (sync, async-mirror) bound-method selector pair, so `emit` binds
# `log.info` and `emit_async` awaits the loop-friendly `log.ainfo` off the one table over the closed
# literal rather than a stringly `getattr(log, level)`/`getattr(log, "a" + level)` over an open namespace.
LEVEL_METHOD: Final[Map[LogLevel, LevelBinding]] = Map.of_seq([
    ("debug", (lambda log: log.debug, lambda log: log.adebug)),
    ("info", (lambda log: log.info, lambda log: log.ainfo)),
    ("warning", (lambda log: log.warning, lambda log: log.awarning)),
    ("error", (lambda log: log.error, lambda log: log.aerror)),
])


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["PHASE_LEVEL", "Classification", "Phase", "Receipt", "ReceiptContributor", "Redaction", "Signals", "drained", "receipted"]
