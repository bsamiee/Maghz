"""Automation wire vocabulary: the trigger/action unions, the spec, the receipt, and the gated-skip owner.

Every type crossing an automation module boundary lives here. The two msgspec tagged unions resolve
independently — `Trigger` by `tag_field="type"`, `Action` by `tag_field="kind"` — and `AutomationSpec`
pairs exactly one of each. `AutomationReceipt` extends the open `Detail` base with `tag="automation"`,
so the report stays one shape while carrying precise per-fire evidence: every slot a given fire mode
never touches rides `msgspec.UNSET` so it encodes ABSENT on the ledger wire rather than `null`,
preserving the fire/skip and agent/engine-arm distinction for downstream consumers exactly as the
sibling `SyncDetail` carries its verb-divergent slots. Boundary breaches ride the runtime `BoundaryFault`
directly; the domain mints no parallel fault carrier. `Gate` is the one non-fault gated-skip outcome — a
saturated lane or an over-ceiling host is a deliberate `Status.SKIP` value the governor returns — and
`Gate.envelope` is its sole egress projection through the canonical `core.completed` constructor, never a
fault case the engine must re-classify.
"""

from enum import StrEnum
from typing import Literal, Self
import uuid

import msgspec

from admin.core import completed, Detail, Envelope, Status


# --- [TYPES] ---------------------------------------------------------------------------


class AgentSkill(StrEnum):
    """Closed in-arm discriminant for `AgentAction`; one member per research skill.

    Adding a skill is one member here plus one `_AGENT_DISPATCH` row in `engine.py`; the `Action`
    union is never restructured.
    """

    DEEP_RESEARCH = "deep_research"
    REFINE = "refine"
    CREATE_ENTRY = "create_entry"


class GateReason(StrEnum):
    """The closed reasons the governor gates a fire to a non-failing skip; each binds its own `Status`.

    The projected `Status` rides each member through `__new__` (the `Status`-pattern attribute bind), so
    `Gate.envelope` reads the member's own outcome with no parallel correspondence: both current reasons
    project `SKIP`, and a future hard-deny reason lands as one member carrying its own `Status`. A gated
    fire never enters the boundary rail, so it cannot collapse into the shared `BoundaryFault` vocabulary.
    """

    status: Status

    SATURATED = ("saturated", Status.SKIP)
    OVER_CEILING = ("over_ceiling", Status.SKIP)

    def __new__(cls, value: str, status: Status) -> Self:
        """Mint the member as its string value, binding the projected gated `Status` onto it."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.status = status
        return member


type TriggerTag = Literal["watch", "schedule", "manual"]
type ActionTag = Literal["agent", "notify", "embed", "sync"]


# --- [MODELS] --------------------------------------------------------------------------


class Watch(msgspec.Struct, frozen=True, gc=False, tag="watch"):
    """Filesystem-change trigger; feeds `watchfiles.awatch(debounce=, recursive=)`."""

    paths: tuple[str, ...]
    filter: Literal["default", "python", "none"] = "default"
    debounce: int = 1600
    recursive: bool = True


class Schedule(msgspec.Struct, frozen=True, gc=False, tag="schedule"):
    """Cron trigger; feeds `CronTrigger.from_crontab(cron, timezone=)` with `jitter` seconds."""

    cron: str
    jitter: int = 0
    timezone: str = "UTC"


class Manual(msgspec.Struct, frozen=True, gc=False, tag="manual"):
    """One-shot immediate execution; the default verb path."""


class AgentAction(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="agent"):
    """Research-skill dispatch keyed by `skill`; `params` defers the skill payload to the dispatch arm.

    One case for every skill, not a per-skill struct: `params` is `msgspec.Raw`, decoded lazily inside
    the `_AGENT_DISPATCH[skill]` callable, never by the engine.
    """

    skill: AgentSkill
    domain: str
    params: msgspec.Raw = msgspec.Raw(b"null")


class Notify(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="notify"):
    """Side-channel message emission; `channel` is the routing key the `Signals` sink discriminates on."""

    channel: Literal["stderr", "ndjson"]
    message: str


class Embed(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="embed"):
    """Embed-pipeline trigger; `None` sweeps all pending, a name enqueues one concept."""

    concept: str | None = None


class Sync(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="sync"):
    """Heptabase sync trigger; `concept` presence is the diff/generate discriminant."""

    op: Literal["diff", "generate"]
    concept: str | None = None


type Trigger = Watch | Schedule | Manual
type Action = AgentAction | Notify | Embed | Sync


class AutomationSpec(msgspec.Struct, frozen=True, gc=False):
    """The complete `--spec` wire payload: one trigger, one action, one lane key.

    The two unions' tag fields (`type` vs `kind`) do not collide; msgspec resolves each independently.
    `lane` is validated against `cfg.automation.lane_keys` at the `decode_spec` admission boundary,
    never silently coerced to `"default"`.
    """

    trigger: Trigger
    action: Action
    lane: str = "default"
    id: str = msgspec.field(default_factory=lambda: str(uuid.uuid4()))


class AutomationReceipt(Detail, frozen=True, tag="automation"):
    """The single typed receipt the engine emits; rides inside `report.detail`.

    `trigger_tag`/`action_tag` carry closed `Literal`s, never bare `str`. Every mode-divergent slot rides
    `msgspec.UNSET` so it encodes ABSENT on the ledger wire rather than `null`, exactly as the sibling
    `SyncDetail` carries its verb-divergent slots: `agent_skill` is present only on the `AgentAction` arm
    (the engine-owned arms omit it); `cpu_percent`/`memory_rss_mb` are the governor snapshot, present on a
    real fire and ABSENT on a gated/missed tick; `rows_affected`/`job_id` are the action-arm evidence the
    fire that produced them carries and every other fire omits. `attempt`/`elapsed_ms` stay required: a
    fire stamps the live reading, a skip stamps `0`/`0.0`, so the fire/skip discriminant is the snapshot
    slots' presence, never a null required field.
    """

    spec_id: str
    trigger_tag: TriggerTag
    action_tag: ActionTag
    lane: str
    fired_at: str
    attempt: int
    elapsed_ms: float
    agent_skill: AgentSkill | msgspec.UnsetType = msgspec.UNSET
    rows_affected: int | msgspec.UnsetType = msgspec.UNSET
    job_id: str | msgspec.UnsetType = msgspec.UNSET
    cpu_percent: float | msgspec.UnsetType = msgspec.UNSET
    memory_rss_mb: float | msgspec.UnsetType = msgspec.UNSET


class Gate(msgspec.Struct, frozen=True, gc=False):
    """One gated, non-failing admission outcome the governor returns instead of firing the spec.

    A saturated lane or an over-ceiling host holds the fire as a deliberate skip, distinct from a
    `BoundaryFault` operational breach — the gate never enters the boundary rail, so the engine's
    dispatch result is `RuntimeRail[AutomationReceipt] | Gate` rather than smuggling a non-failure
    through the fault carrier. `envelope` projects through the canonical `core.completed` gated-skip
    constructor (the one owner that freezes `error_context` into the `Envelope` carrier), reading the
    reason's own `Status` and stamping `{reason, spec_id, detail}` so an operator reads saturation or
    ceiling pressure off the wire.
    """

    reason: GateReason
    spec_id: str
    detail: str

    def envelope(self) -> Envelope:
        """Project this gated outcome to its skip `Envelope` at the reason's own `Status`.

        Returns:
            The `core.completed` envelope carrying the gate detail as `error` and the
            `{reason, spec_id, detail}` context the CLI and ledger read the gating cause off.
        """
        context = {"reason": self.reason.value, "spec_id": self.spec_id, "detail": self.detail}
        return completed(self.reason.status, error=self.detail, error_context=context)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "Action",
    "ActionTag",
    "AgentAction",
    "AgentSkill",
    "AutomationReceipt",
    "AutomationSpec",
    "Embed",
    "Gate",
    "GateReason",
    "Manual",
    "Notify",
    "Schedule",
    "Sync",
    "Trigger",
    "TriggerTag",
    "Watch",
]
