"""Automation wire vocabulary: triggers, actions, the spec record, the receipt, the fault rail.

Every type that crosses an automation module boundary lives here. The two tagged unions
(`Trigger` by `tag_field="type"`, `Action` by `tag_field="kind"`) are msgspec-native and
resolve independently; `AutomationSpec` pairs exactly one of each. `AutomationReceipt`
extends the envelope `Detail` base with `tag="automation"` so the report stays one shape.
`AutomationFault` is the domain-internal `expression` tagged union, projected to an
`Envelope` exactly once at the CLI boundary in `engine.py`. No operations live here.
"""

from enum import StrEnum
from typing import assert_never, Literal
import uuid

from expression import case, tag, tagged_union
import msgspec

from admin.core.model import Detail


# --- [TYPES] ---------------------------------------------------------------------------


class AgentSkill(StrEnum):
    """Closed in-arm discriminant for `AgentAction`; one member per research skill.

    Adding a skill is one member here plus one `_AGENT_DISPATCH` row in `engine.py` — the
    `Action` union is never restructured. A future `N8N_TRIGGER` member is the n8n entry.
    """

    DEEP_RESEARCH = "deep_research"
    REFINE = "refine"
    CREATE_ENTRY = "create_entry"


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
    """Research-skill dispatch; `params` defers the skill payload to the dispatch arm.

    Collapses the former `DeepResearch` / `Refine` / `CreateEntry` cases into one case keyed
    by `skill`. `params` is decoded lazily inside the `_AGENT_DISPATCH[skill]` callable, never
    by the engine itself.
    """

    skill: AgentSkill
    domain: str
    params: msgspec.Raw = msgspec.Raw(b"null")


class Notify(msgspec.Struct, frozen=True, gc=False, tag_field="kind", tag="notify"):
    """Side-channel message emission to stderr or the NDJSON ledger."""

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
type TriggerTag = Literal["watch", "schedule", "manual"]
type Action = AgentAction | Notify | Embed | Sync
type ActionTag = Literal["agent", "notify", "embed", "sync"]
type AutomationFaultKind = Literal[
    "spec_decode", "admission_denied", "lane_overflow", "action_transient", "action_permanent", "trigger_spawn", "agent_call"
]


# --- [MODELS] --------------------------------------------------------------------------


class AutomationSpec(msgspec.Struct, frozen=True, gc=False):
    """The complete `--spec` wire payload: one trigger, one action, one lane key.

    The two unions' tag fields (`type` vs `kind`) do not collide; msgspec resolves each
    independently. `lane` is validated against `cfg.automation.lane_keys` at the
    `_decode_spec` admission boundary, never silently coerced to `"default"`.
    """

    trigger: Trigger
    action: Action
    lane: str = "default"
    id: str = msgspec.field(default_factory=lambda: str(uuid.uuid4()))


class AutomationReceipt(Detail, frozen=True, tag="automation"):
    """The single typed receipt the engine emits; rides inside `report.detail`.

    `trigger_tag` / `action_tag` carry closed `Literal`s, never bare `str`. `agent_skill`
    is a valid `AgentSkill` only on the `AgentAction` arm. `cpu_percent` / `memory_rss_mb`
    are the governor snapshot, non-null on every fire.
    """

    spec_id: str
    trigger_tag: TriggerTag
    action_tag: ActionTag
    agent_skill: AgentSkill | None
    lane: str
    fired_at: str
    attempt: int
    elapsed_ms: float
    rows_affected: int | None = None
    job_id: str | None = None
    cpu_percent: float | None = None
    memory_rss_mb: float | None = None


# --- [ERRORS] --------------------------------------------------------------------------


@tagged_union(frozen=True)
class AutomationFault:
    """Closed domain-internal fault vocabulary; projected to an `Envelope` once at `drive`.

    Each case is `(context, detail)`: `spec_decode` / `admission_denied` / `action_*` /
    `agent_call` carry `(spec_id_or_empty, detail)`; `lane_overflow` carries `(spec_id, lane)`;
    `trigger_spawn` carries `(lane, detail)`. Never serialized directly — `context()` is the owner
    fold the engine reads, and `_fault_envelope` projects the pair with a total `match` +
    `assert_never`.
    """

    tag: AutomationFaultKind = tag()

    spec_decode: tuple[str, str] = case()
    admission_denied: tuple[str, str] = case()
    lane_overflow: tuple[str, str] = case()
    action_transient: tuple[str, str] = case()
    action_permanent: tuple[str, str] = case()
    trigger_spawn: tuple[str, str] = case()
    agent_call: tuple[str, str] = case()

    def context(self) -> tuple[str, str]:  # noqa: PLR0911, PLR0912 - one typed read per case of the closed seven-case fault union
        """Read the `(context, detail)` pair off whichever case is set, total over the closed union.

        Every leaf payload is a `(context, detail)` pair whose subject differs by case — `spec_id`
        for the spec/action/agent faults, `lane` for `lane_overflow`/`trigger_spawn` — so the engine
        composes one owner read instead of a free-function fold: `_lift` mints the runtime
        `BoundaryFault` from it and `_fault_envelope` carries it into the CLI `Envelope` context.

        Returns:
            The `(context, detail)` pair the populated case carries; the `assert_never` arm proves the
            seven `AutomationFaultKind` cases are exhausted.
        """
        match self.tag:
            case "spec_decode":
                return self.spec_decode
            case "admission_denied":
                return self.admission_denied
            case "lane_overflow":
                return self.lane_overflow
            case "action_transient":
                return self.action_transient
            case "action_permanent":
                return self.action_permanent
            case "trigger_spawn":
                return self.trigger_spawn
            case "agent_call":
                return self.agent_call
            case _ as unreachable:  # pragma: no cover - exhaustive over the closed AutomationFaultKind literal
                assert_never(unreachable)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "Action",
    "ActionTag",
    "AgentAction",
    "AgentSkill",
    "AutomationFault",
    "AutomationFaultKind",
    "AutomationReceipt",
    "AutomationSpec",
    "Embed",
    "Manual",
    "Notify",
    "Schedule",
    "Sync",
    "Trigger",
    "TriggerTag",
    "Watch",
]
