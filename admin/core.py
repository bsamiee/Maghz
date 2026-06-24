"""The result/envelope algebra: the outcome vocabulary and the one-line JSON contract every rail emits.

`Status` is the closed outcome vocabulary; each member binds its severity rank and process exit code
through `__new__`, so `worst`/`fold` severity-max and `code` read the member's own row with no parallel
table or branch. `Detail` is the open tagged base each rail extends with one typed evidence case, so the
`Envelope` stays one shape while carrying precise receipts. `completed` and `fault` are the two envelope
constructors: `completed` owns every non-faulted outcome (success, skip, empty, tool-found defects, and a
gated skip carrying its reason), and `fault` mints the single `FAULTED` operational breach — no rail
reconstructs the carrier by hand. `tag_of` recovers a tagged struct's minted discriminant off
`__struct_config__.tag` and narrows it once into the caller's closed tag `Literal` through
`msgspec.convert`, so every consumer matches a value typed to the domain rather than re-narrowing a bare
`str`.
"""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from functools import reduce
from typing import Self, TYPE_CHECKING

from frozendict import frozendict
import msgspec


if TYPE_CHECKING:
    from typing import TypeForm

    type TagForm[T] = TypeForm[T]
else:
    type TagForm[T] = object


# --- [TYPES] ---------------------------------------------------------------------------


class Status(StrEnum):
    """The closed set of rail outcomes; each member carries its severity rank and exit code.

    `__new__` binds `rank` (severity-max key, higher is worse) and `code` (process exit) onto the
    member, so `worst`/`fold` and `code` spend the member's own row — no parallel correspondence table.
    """

    rank: int
    code: int

    OK = ("ok", 0, 0)
    SKIP = ("skip", 0, 0)
    EMPTY = ("empty", 0, 0)
    UNSUPPORTED = ("unsupported", 1, 3)
    FAILED = ("failed", 2, 1)
    FAULTED = ("faulted", 3, 2)

    def __new__(cls, value: str, rank: int, code: int) -> Self:
        """Mint the member as its string value, binding the severity rank and exit code onto it."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.rank = rank
        member.code = code
        return member

    def worst(self, other: Status) -> Status:
        """Severity-max of two outcomes; the worse one wins, ties keep the receiver.

        The one severity-comparison; `fold` reduces a stream through it, so the rank ordering lives
        in exactly one place.

        Returns:
            The higher-rank outcome, or the receiver on a tie.
        """
        return self if self.rank >= other.rank else other

    @classmethod
    def fold(cls, statuses: Iterable[Status]) -> Status:
        """Reduce a stream of outcomes to the worst through `worst`; an empty stream folds to `OK`.

        Returns:
            The maximum-severity outcome over `statuses`, or `OK` when the stream is empty.
        """
        return reduce(Status.worst, statuses, cls.OK)


# --- [MODELS] --------------------------------------------------------------------------


class Detail(msgspec.Struct, frozen=True, tag=True, gc=False):
    """Base for rail-specific typed evidence; each rail extends it with one tagged case."""


class Row(msgspec.Struct, frozen=True, gc=False):
    """One bounded result row under `report.rows`."""

    key: str
    text: str


class Report(msgspec.Struct, frozen=True):
    """Rail evidence: typed detail, bounded rows, durable artifacts, and notes.

    GC-tracked, not `gc=False`: the `detail` struct ref and the `rows` tuple-of-`Row` are object
    containers, so the leaf-only `gc=False` elision does not apply.
    """

    detail: Detail | None = None
    rows: tuple[Row, ...] = ()
    artifacts: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class Envelope(msgspec.Struct, frozen=True):
    """The single JSON object written to stdout per invocation.

    `completed` and `fault` are the only constructors; the raw initializer is never called at a rail
    edge. `encode` is the byte projection to the stdout line, and `code` the non-serialized exit
    projection off `status`. GC-tracked, not `gc=False`: the `report` struct ref and the
    `error_context` `frozendict` are object containers. `error_context` is the frozen `frozendict`
    carrier — never a mutable `dict`/`Mapping` a caller could rebind after the frozen struct closes —
    that the constructors mint from a raw mapping at admission.
    """

    status: Status
    report: Report | None = None
    error: str | None = None
    error_context: frozendict[str, str] | None = None

    @property
    def code(self) -> int:
        """The process exit code projected from `status` (not serialized)."""
        return self.status.code

    def encode(self) -> bytes:
        """Serialize to the newline-free JSON line for stdout through the shared deterministic encoder."""
        return _ENCODER.encode(self)


# --- [SERVICES] ------------------------------------------------------------------------

# One process-wide JSON encoder reused by every `Envelope.encode`; a fresh `Encoder` per call re-resolves
# the struct schema, so the shared instance is the owner. `order="deterministic"` makes the stdout line
# canonical: identical envelopes encode to byte-identical JSON across runs, so consumers diff, hash, and
# cache the contract, and it sorts the `frozendict` `error_context` keys too — `frozendict` subclasses
# `dict`, so the C core encodes it through the native mapping path with no `enc_hook`.
_ENCODER = msgspec.json.Encoder(order="deterministic")


# --- [OPERATIONS] ----------------------------------------------------------------------


def completed(
    status: Status,
    detail: Detail | None = None,
    *,
    rows: tuple[Row, ...] = (),
    artifacts: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
    error: str | None = None,
    error_context: Mapping[str, str] | None = None,
) -> Envelope:
    """A non-faulted rail: success, skip, empty, or tool-found defects, carrying its full report.

    `error`/`error_context` admit a gated outcome — a skip whose admission was denied or whose lane
    overflowed — that reports a reason alongside its report, so the gated case flows through this one
    constructor rather than a hand-built `Envelope(...)`. The raw `error_context` mapping is frozen into
    the `Envelope`'s `frozendict` carrier here, at admission. The `FAULTED` operational breach is `fault`.

    Returns:
        An `Envelope` carrying `status`, a `Report` of the supplied evidence, and the optional gated reason.
    """
    return Envelope(
        status=status,
        report=Report(detail=detail, rows=rows, artifacts=artifacts, notes=notes),
        error=error,
        error_context=None if error_context is None else frozendict(error_context),
    )


def fault(error: str, context: Mapping[str, str] | None = None) -> Envelope:
    """An operational failure: routing, spawn, precondition, or boundary breach — exit code 2.

    The raw `context` mapping is frozen into the `Envelope`'s `frozendict` carrier here, at admission.

    Returns:
        A `FAULTED` `Envelope` carrying the error message and the optional string-keyed context.
    """
    return Envelope(status=Status.FAULTED, error=error, error_context=None if context is None else frozendict(context))


def tag_of[T](carrier: msgspec.Struct, tag_type: TagForm[T]) -> T:
    """Recover a tagged struct's minted discriminant, narrowed to its closed tag domain.

    The single source of a struct's wire tag, minting it exactly once: the bare discriminant is read
    off the per-class `StructConfig` (never re-derived by a `getattr(self, self.tag)` escape or a
    per-case `match` over the union), then `msgspec.convert` narrows it into the closed `tag_type`
    `Literal` in the C core — the one witness that the discriminant is a member, so the caller's
    `match`/`assert_never` over `tag_type` is total against a value typed to the domain, never a bare
    `str` re-narrowed at each site. `carrier` is always a member of a tagged union by construction, so
    the narrow is total; an untagged struct carries `tag is None`, the programming error `convert`
    surfaces as the documented `ValidationError`.

    Returns:
        The struct's minted discriminant, typed to `tag_type`.

    Raises:
        msgspec.ValidationError: When `carrier` is untagged or its tag is not a member of `tag_type`.
    """
    return msgspec.convert(carrier.__struct_config__.tag, type=tag_type)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Detail", "Envelope", "Report", "Row", "Status", "completed", "fault", "tag_of"]
