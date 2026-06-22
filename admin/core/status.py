"""Outcome algebra: one closed vocabulary that owns its severity fold and exit projection."""

from collections.abc import Iterable
from enum import StrEnum

from frozendict import frozendict


# --- [TYPES] ---------------------------------------------------------------------------


class Status(StrEnum):
    """The closed set of rail outcomes, ordered by severity and projected to exit codes.

    Severity rank and process exit code are the two projections of one correspondence row
    (`_RANK_EXIT`); the fold (`worst`/`fold`) and `code` derive from it, never from branches.
    """

    OK = "ok"
    SKIP = "skip"
    EMPTY = "empty"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    FAULTED = "faulted"

    @property
    def rank(self) -> int:
        """Severity rank projected from this outcome; higher is worse (`OK` lowest)."""
        rank, _ = _RANK_EXIT[self]
        return rank

    @property
    def code(self) -> int:
        """The process exit code projected from this outcome."""
        _, code = _RANK_EXIT[self]
        return code

    def worst(self, other: Status) -> Status:
        """Severity-max of two outcomes; the worse one wins, ties keep the receiver."""
        return self if self.rank >= other.rank else other

    @classmethod
    def fold(cls, statuses: Iterable[Status]) -> Status:
        """Reduce a stream of outcomes to the worst; an empty stream folds to `OK`."""
        return max(statuses, key=lambda status: status.rank, default=cls.OK)


# --- [TABLES] --------------------------------------------------------------------------

# Primary correspondence: status -> (severity rank, process exit code). The fold and exit
# projection on `Status` both derive from this single row; never enumerate them in branches.
# The key set equals `Status` exactly, so direct subscription is total — no missing key.
_RANK_EXIT: frozendict[Status, tuple[int, int]] = frozendict({
    Status.OK: (0, 0),
    Status.SKIP: (0, 0),
    Status.EMPTY: (0, 0),
    Status.UNSUPPORTED: (1, 3),
    Status.FAILED: (2, 1),
    Status.FAULTED: (3, 2),
})


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["Status"]
