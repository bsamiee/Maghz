"""The one-line JSON result contract every rail emits on stdout.

`Detail` is the open base for rail-specific typed evidence: each rail declares one tagged
subclass, so the envelope stays a single shape while carrying precise receipts. `completed`
is the sole `Report` constructor — it owns every report field (detail, rows, artifacts,
notes), so no rail reconstructs the carrier by hand. `Envelope.amend` derives an enriched
envelope from an existing one through `msgspec.structs.replace`, the frozen-struct update
path for consumers that accumulate rows, artifacts, or notes onto a prior receipt.
"""

from collections.abc import Mapping

import msgspec
from msgspec.structs import replace

from admin.core.status import Status


# --- [MODELS] --------------------------------------------------------------------------


class Detail(msgspec.Struct, frozen=True, tag=True, gc=False):
    """Base for rail-specific typed evidence; each rail extends it with one tagged case."""


class Row(msgspec.Struct, frozen=True, gc=False):
    """One bounded result row under `report.rows`."""

    key: str
    text: str


class Report(msgspec.Struct, frozen=True, gc=False):
    """Rail evidence: typed detail, bounded rows, durable artifacts, and notes."""

    detail: Detail | None = None
    rows: tuple[Row, ...] = ()
    artifacts: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class Envelope(msgspec.Struct, frozen=True, gc=False):
    """The single JSON object written to stdout per invocation."""

    status: Status
    report: Report | None = None
    error: str | None = None
    error_context: Mapping[str, str] | None = None

    @property
    def code(self) -> int:
        """The process exit code projected from `status` (not serialized)."""
        return self.status.code

    def amend(self, *, rows: tuple[Row, ...] = (), artifacts: tuple[str, ...] = (), notes: tuple[str, ...] = ()) -> Envelope:
        """Derive an enriched envelope, appending evidence to this report without reconstruction.

        The status, error, and detail are preserved; the supplied rows, artifacts, and notes are
        concatenated onto the current report through `msgspec.structs.replace`, the frozen-struct
        update path. A `fault` envelope with no report yields a fresh report carrying the evidence.

        Returns:
            A new `Envelope` whose report carries the original evidence followed by the appended rows,
            artifacts, and notes; the original is left unchanged.
        """
        base = self.report or Report()
        return replace(self, report=replace(base, rows=base.rows + rows, artifacts=base.artifacts + artifacts, notes=base.notes + notes))

    def encode(self) -> bytes:
        """Serialize to the newline-free JSON line for stdout through the shared encoder."""
        return _ENCODER.encode(self)


# --- [SERVICES] ------------------------------------------------------------------------

# One process-wide JSON encoder reused by every `Envelope.encode`; constructing a fresh
# `Encoder` per call re-resolves the struct schema, so the shared instance is the owner.
# `order="deterministic"` makes the stdout result line canonical: identical envelopes encode
# to byte-identical JSON across runs, so consumers can diff, hash, and cache the contract.
_ENCODER = msgspec.json.Encoder(order="deterministic")


# --- [OPERATIONS] ----------------------------------------------------------------------


def completed(
    status: Status, detail: Detail | None = None, *, rows: tuple[Row, ...] = (), artifacts: tuple[str, ...] = (), notes: tuple[str, ...] = ()
) -> Envelope:
    """A completed rail: success, skip, empty, or tool-found defects, carrying its full report."""
    return Envelope(status=status, report=Report(detail=detail, rows=rows, artifacts=artifacts, notes=notes))


def fault(error: str, context: Mapping[str, str] | None = None) -> Envelope:
    """An operational failure: routing, spawn, precondition, or boundary breach."""
    return Envelope(status=Status.FAULTED, error=error, error_context=context)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Detail", "Envelope", "Report", "Row", "completed", "fault"]
