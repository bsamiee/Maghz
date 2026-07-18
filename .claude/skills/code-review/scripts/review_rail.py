#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.15"
# dependencies = ["cyclopts>=4", "expression>=5", "msgspec>=0.19", "pydantic>=2.11", "ruamel.yaml>=0.18"]
# ///
# ruff: noqa: T201, D100, D101, D102, D103

# --- [RUNTIME_PRELUDE] ------------------------------------------------------------------

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from copy import replace as evolved
from dataclasses import dataclass
from functools import reduce
import hashlib
import io
from itertools import accumulate, groupby, islice
import json
from operator import itemgetter
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import time
from types import MappingProxyType
from typing import Annotated, Final, Literal
import unicodedata

from cyclopts import App, Parameter
from expression import Error, Nothing, Ok, Option, Result, Some
from expression.collections import Block
from expression.extra.result import catch, traverse
import msgspec
from msgspec.structs import replace
from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


# --- [TYPES] ----------------------------------------------------------------------------

type Reviewer = Literal["coderabbit", "greptile", "macroscope"]
type Severity = Literal["critical", "major", "minor", "trivial", "info"]
type ScopeKind = Literal["all", "committed", "uncommitted", "base", "base-commit"]
type Phase = Literal["launched", "reviewing", "completed", "failed", "refused", "stalled", "timed-out"]
type Balance = Literal["count", "loc"]
type SliceAxis = Literal["folder"]
type FaultCode = Literal[
    "not-a-repo",
    "command-failed",
    "spawn-failed",
    "bad-scope",
    "unsupported-scope",
    "unsupported-focus",
    "live-run",
    "no-round",
    "not-completed",
    "unreadable",
    "unwritable",
    "malformed",
    "no-findings",
    "no-lanes",
    "bad-lane",
    "no-report",
    "store-missing",
    "no-payload",
    "already-sliced",
    "already-closed",
]

# --- [CONSTANTS] ------------------------------------------------------------------------

CLAIM_STEM: Final = 120
FOLDER_DEPTH: Final = 2
HEADLINE: Final = 160
JSON_SCAN_CAP: Final = 64
LANES_CAP: Final = 12
LANE_ALPHABET: Final = "abcdefghijkl"
LIVENESS_NOTE_S: Final = 60.0
POLL_S: Final = 5.0
STORE_SLACK_S: Final = 120.0
EXIT_MARK: Final = "__rail_exit="
FEED_NAME: Final = "harvest-feed.md"
FINDINGS_NAME: Final = "findings.json"
FOCUS_NAME: Final = "focus.md"
LEDGER_NAME: Final = "rounds.jsonl"
LOG_NAME: Final = "stream.log"
REPRINT_NAME: Final = "findings-reprint.log"
RUN_NAME: Final = "run.json"
STATE_DIR: Final = Path(".cache/review")
CR_STORE: Final = Path.home() / ".coderabbit" / "reviews"
GREPTILE_LEDGER: Final = Path.home() / ".greptile" / "reviews.json"
REGISTRY_PATH: Final = Path(__file__).resolve().parent.parent / "data" / "refuted-classes.yaml"
CR_META_NAMES: Final = frozenset({"git.json", "internalState.json"})
SEVERITIES: Final[tuple[Severity, ...]] = ("critical", "major", "minor", "trivial", "info")
RANK: Final[Mapping[Severity, int]] = MappingProxyType({level: rank for rank, level in enumerate(SEVERITIES)})
TERMINAL: Final[frozenset[Phase]] = frozenset({"completed", "failed", "refused", "stalled", "timed-out"})
SEVERITY_ROWS: Final[tuple[tuple[str, Severity], ...]] = (
    ("critical", "critical"),
    ("major", "major"),
    ("high", "major"),
    ("logic", "major"),
    ("syntax", "major"),
    ("medium", "minor"),
    ("minor", "minor"),
    ("style", "minor"),
    ("low", "trivial"),
    ("trivial", "trivial"),
    ("info", "info"),
    ("note", "info"),
)
SEVERITY_MAP: Final[Mapping[str, Severity]] = MappingProxyType(dict(SEVERITY_ROWS))
SCOPE_ROWS: Final[tuple[tuple[str, ScopeKind], ...]] = (
    ("all", "all"),
    ("committed", "committed"),
    ("uncommitted", "uncommitted"),
    ("base", "base"),
    ("base-commit", "base-commit"),
)
SCOPE_KINDS: Final[Mapping[str, ScopeKind]] = MappingProxyType(dict(SCOPE_ROWS))
REF_KINDS: Final[frozenset[ScopeKind]] = frozenset({"base", "base-commit"})
ROW_KEYS: Final = ("comments", "findings", "issues")
ANSI_RE: Final = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
EXIT_LINE_RE: Final = re.compile(rf"^{EXIT_MARK}(\d+)\s*$")
ISSUE_AT_RE: Final = re.compile(r"issue_event\s*=\s*")
STEM_RE: Final = re.compile(r"\W+")

# --- [MODELS] ---------------------------------------------------------------------------


class Scope(msgspec.Struct, frozen=True):
    kind: ScopeKind
    ref: str = ""

    @property
    def line(self) -> str:
        return f"{self.kind}:{self.ref}" if self.ref else str(self.kind)

    @staticmethod
    def of(text: str, /) -> Result[Scope, Fault]:
        head, _, ref = text.partition(":")
        kind = SCOPE_KINDS.get(head)
        return (
            Ok(Scope(kind=kind, ref=ref))
            if kind is not None and (kind in REF_KINDS) == bool(ref)
            else Error(Fault(code="bad-scope", detail=f"{text!r} is not all|committed|uncommitted|base:<ref>|base-commit:<sha>"))
        )


class Range(msgspec.Struct, frozen=True):
    start: int = 0
    end: int = 0


class Finding(msgspec.Struct, frozen=True):
    id: str
    fingerprint: str
    reviewer: Reviewer
    file: str
    range: Range
    severity: Severity
    claim: str
    fix_instructions: str
    class_match: str
    raw: msgspec.Raw


class Run(msgspec.Struct, frozen=True):
    round: int
    reviewer: Reviewer
    scope: Scope
    pid: int
    started: float
    argv: tuple[str, ...]
    focus: str = ""


class LaneManifest(msgspec.Struct, frozen=True):
    lane: str
    files: tuple[str, ...]
    count: int
    criticals: int
    suggested_scope_line: str


class LaneSlice(msgspec.Struct, frozen=True):
    manifest: LaneManifest
    settled_rulings: tuple[str, ...]
    findings: tuple[Finding, ...]


class LedgerRow(msgspec.Struct, frozen=True):
    id: str = ""
    file: str = ""
    severity: str = ""
    verdict: str = ""
    note: str = ""


class Improvement(msgspec.Struct, frozen=True):
    page: str = ""
    pattern: str = ""
    what: str = ""


class Refutation(msgspec.Struct, frozen=True):
    claim: str = ""
    evidence: str = ""


class LaneReport(msgspec.Struct, frozen=True):
    ledger: tuple[LedgerRow, ...] = ()
    improvements: tuple[Improvement, ...] = ()
    refuted: tuple[Refutation, ...] = ()
    capability: tuple[msgspec.Raw, ...] = ()
    routing: tuple[msgspec.Raw, ...] = ()
    uncertain: tuple[msgspec.Raw, ...] = ()
    model: str = ""
    wall_s: float = 0.0


class RefutedClass(msgspec.Struct, frozen=True):
    class_id: str
    matchers: tuple[str, ...] = ()
    refuting_citation: str = ""
    landed_surfaces: tuple[str, ...] = ()
    rounds_seen: tuple[int, ...] = ()


class Registry(msgspec.Struct, frozen=True):
    classes: tuple[RefutedClass, ...] = ()


class CrMeta(msgspec.Struct, frozen=True, rename="camel"):
    working_directory: str = ""
    timestamp: float = 0.0


class CrRange(msgspec.Struct, frozen=True):
    start: int = 0
    end: int = 0


class CrRich(msgspec.Struct, frozen=True, rename="camel"):
    severity: str = "info"
    file_name: str = ""
    start_line: int = 0
    end_line: int = 0
    line_range: CrRange | None = None
    title: str = ""
    comment: str = ""
    codegen_instructions: str = ""
    fingerprint: str = ""


class WireFinding(BaseModel):
    """Tolerant wire-row admission for greptile `--json` rows and the CR reprint stream.

    TODO: pin against first real run — the greptile finding-array field spellings and the CR
    reprint event payload are unverified candidates; the alias rosters below are the probe set.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)
    file: str = Field(
        default="",
        validation_alias=AliasChoices(
            "file", "path", "filePath", "filepath", "fileName", AliasPath("location", "file"), AliasPath("location", "path")
        ),
    )
    start: int = Field(
        default=0,
        validation_alias=AliasChoices(
            "startLine", "start_line", "lineStart", "start", "line", AliasPath("lineRange", "start"), AliasPath("range", "start")
        ),
    )
    end: int = Field(
        default=0, validation_alias=AliasChoices("endLine", "end_line", "lineEnd", "end", AliasPath("lineRange", "end"), AliasPath("range", "end"))
    )
    severity: str = Field(default="", validation_alias=AliasChoices("severity", "level", "priority", "commentType", "type", "category"))
    body: str = Field(default="", validation_alias=AliasChoices("body", "comment", "text", "message", "content", "description"))


class GreptileRow(msgspec.Struct, frozen=True, rename="camel"):
    run_id: str = ""
    base_ref: str = ""
    head_ref: str = ""
    status: str = ""
    comment_count: int = 0


class GreptileLedger(msgspec.Struct, frozen=True):
    version: int = 1
    reviews: tuple[GreptileRow, ...] = ()


class MsIssue(msgspec.Struct, frozen=True):
    issue_id: str = ""
    sequence: int = 0
    path: str = ""
    line: int = 0
    severity: str = ""
    category: str = ""
    body: str = ""


class LaneStat(msgspec.Struct, frozen=True):
    lane: str
    model: str
    findings: int
    verdicts: dict[str, int]
    missing: tuple[str, ...]
    phantom: tuple[str, ...]
    wall_s: float
    report_valid: bool


class RoundRow(msgspec.Struct, frozen=True):
    round: int
    reviewer: Reviewer
    scope: str
    counts_by_severity: dict[str, int]
    total: int
    lanes: tuple[LaneStat, ...]
    recurred_classes: tuple[str, ...]
    new_classes: int
    routed: int
    capability_rows: int
    commit: str
    at: float
    focus: str = ""


class Delta(msgspec.Struct, frozen=True):
    prior_round: int
    total_delta: int
    by_severity: dict[str, int]
    recurred_still: tuple[str, ...]


class LaunchReceipt(msgspec.Struct, frozen=True):
    round: int
    reviewer: Reviewer
    scope: str
    pid: int
    argv: tuple[str, ...]
    focus: str
    log: str
    run: str


class StatusReceipt(msgspec.Struct, frozen=True):
    round: int
    reviewer: Reviewer
    scope: str
    phase: Phase
    elapsed_s: float
    last_pulse_age_s: float
    findings_seen: int
    detail: str
    log: str


class FindingsReceipt(msgspec.Struct, frozen=True):
    round: int
    reviewer: Reviewer
    total: int
    deduped: int
    cross_deduped: int
    classified: int
    counts_by_severity: dict[str, int]
    source: str
    path: str


class SliceReceipt(msgspec.Struct, frozen=True):
    round: int
    lanes: tuple[LaneManifest, ...]
    stamped: int
    settled_rulings: int
    cleared: int


class ReconcileReceipt(msgspec.Struct, frozen=True):
    round: int
    lanes: tuple[LaneStat, ...]
    bijective: bool


class HarvestReceipt(msgspec.Struct, frozen=True):
    round: int
    reports: int
    recurred: tuple[str, ...]
    new_refuted: int
    improvements: int
    capability: int
    routed: int
    path: str


class RoundReceipt(msgspec.Struct, frozen=True):
    row: RoundRow
    delta: Delta | None


class VerifyReceipt(msgspec.Struct, frozen=True):
    rule: str
    path: str
    effective: bool
    matched: str
    source: str


# --- [ERRORS] ---------------------------------------------------------------------------


class Fault(msgspec.Struct, frozen=True):
    code: FaultCode
    detail: str = ""


# --- [SERVICES] -------------------------------------------------------------------------

APP: Final = App(help="One verb rail over CodeRabbit, Greptile, and Macroscope: launch, status, findings, slice, reconcile, harvest, round, verify.")
ENCODER: Final = msgspec.json.Encoder()
RAW_JSON: Final = json.JSONDecoder()
YAML_SAFE: Final = YAML(typ="safe")
YAML_RT: Final = YAML(typ="rt")

# --- [BOUNDARIES] -----------------------------------------------------------------------


def emitted(payload: object, /) -> int:
    print(ENCODER.encode(payload).decode())
    return 0


def refused(fault: Fault, /) -> int:
    emitted(fault)
    return 1


def delivered(outcome: Result[object, Fault], /) -> int:
    return outcome.map(emitted).default_with(refused)


def read_bytes(path: Path, /) -> Result[bytes, Fault]:
    return catch(exception=OSError)(path.read_bytes)().map_error(lambda unreachable: Fault(code="unreadable", detail=f"{path}: {unreachable}"))


def written(path: Path, payload: bytes, /, *, append: bool = False) -> Result[Path, Fault]:
    def sunk() -> Path:
        with path.open("ab" if append else "wb") as sink:
            sink.write(payload)
        return path

    return catch(exception=OSError)(sunk)().map_error(lambda unwritable: Fault(code="unwritable", detail=f"{path}: {unwritable}"))


def unlinked(paths: tuple[Path, ...], /) -> Result[int, Fault]:
    def gone(path: Path, /) -> Result[Path, Fault]:
        return catch(exception=OSError)(path.unlink)().map(lambda _n: path).map_error(lambda held: Fault(code="unwritable", detail=f"{path}: {held}"))

    return traverse(gone, Block.of_seq(paths)).map(len)


def decoded[T](payload: bytes, shape: type[T], origin: str, /) -> Result[T, Fault]:
    try:
        return Ok(msgspec.json.decode(payload, type=shape, strict=False))
    except msgspec.ValidationError as drift:
        return Error(Fault(code="malformed", detail=f"{origin}: {drift}"))
    except msgspec.DecodeError as garbled:
        return Error(Fault(code="malformed", detail=f"{origin}: {garbled}"))


def json_value(payload: bytes, origin: str, /) -> Result[object, Fault]:
    def parsed() -> object:
        value: object = msgspec.json.decode(payload)
        return value

    return catch(exception=msgspec.DecodeError)(parsed)().map_error(lambda garbled: Fault(code="malformed", detail=f"{origin}: {garbled}"))


def json_document(text: str, at: int, /) -> Option[object]:
    return catch(exception=ValueError)(RAW_JSON.raw_decode)(text, at).to_option().map(itemgetter(0))


def shaped[T](path: Path, shape: type[T], /) -> Option[T]:
    return read_bytes(path).bind(lambda payload: decoded(payload, shape, str(path))).to_option()


def sh(argv: tuple[str, ...], /, *, cwd: Path | None = None) -> Result[str, Fault]:
    def ran() -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, capture_output=True, text=True, check=False, cwd=None if cwd is None else str(cwd))

    return (
        catch(exception=OSError)(ran)()
        .map_error(lambda unrunnable: Fault(code="command-failed", detail=f"{argv[0]}: {unrunnable}"))
        .bind(
            lambda probe: (
                Ok(probe.stdout.strip())
                if probe.returncode == 0
                else Error(Fault(code="command-failed", detail=f"{argv[0]}: {probe.stderr.strip() or f'exit={probe.returncode}'}"))
            )
        )
    )


def spawned(argv: tuple[str, ...], log: Path, cwd: Path, /) -> Result[int, Fault]:
    script = f'{shlex.join(argv)}; printf "\\n{EXIT_MARK}%s\\n" "$?"'

    def forked() -> int:
        with log.open("ab") as sink:
            child = subprocess.Popen(
                ("/bin/sh", "-c", script), stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT, cwd=str(cwd), start_new_session=True
            )
        return child.pid

    return catch(exception=OSError)(forked)().map_error(lambda unspawnable: Fault(code="spawn-failed", detail=f"{argv[0]}: {unspawnable}"))


def alive(pid: int, /) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def breathing(pid: int, needle: str, /) -> bool:
    return alive(pid) and sh(("ps", "-p", str(pid), "-o", "command=")).map(lambda command: needle in command).default_with(lambda _f: False)


def repo_root(directory: Path | None, /) -> Result[Path, Fault]:
    anchor = directory or Path.cwd()
    return (
        sh(("git", "-C", str(anchor), "rev-parse", "--show-toplevel"))
        .map(Path)
        .map_error(lambda fault: Fault(code="not-a-repo", detail=f"{anchor}: {fault.detail}"))
    )


def registry_loaded() -> Result[Registry, Fault]:
    if not REGISTRY_PATH.is_file():
        return Ok(Registry())
    try:
        parsed: object = YAML_SAFE.load(REGISTRY_PATH.read_text(encoding="utf-8"))
    except OSError as unreachable_file:
        return Error(Fault(code="unreadable", detail=f"{REGISTRY_PATH}: {unreachable_file}"))
    except YAMLError as garbled:
        return Error(Fault(code="malformed", detail=f"{REGISTRY_PATH}: {garbled}"))
    try:
        return Ok(msgspec.convert(parsed or {}, type=Registry, strict=False))
    except msgspec.ValidationError as drift:
        return Error(Fault(code="malformed", detail=f"{REGISTRY_PATH}: {drift}"))


# --- [OPERATIONS] -----------------------------------------------------------------------

# --- [ROUND_STORE]


@dataclass(frozen=True, slots=True, kw_only=True)
class Context:
    repo: Path
    round_dir: Path
    run: Run


def round_number(round_dir: Path, /) -> int:
    tail = round_dir.name.rpartition("-")[2]
    return int(tail) if tail.isdigit() else 0


def round_dirs(repo: Path, /) -> tuple[Path, ...]:
    return tuple(sorted((repo / STATE_DIR).glob("round-*"), key=round_number))


def run_loaded(round_dir: Path, /) -> Result[Run, Fault]:
    return read_bytes(round_dir / RUN_NAME).bind(lambda payload: decoded(payload, Run, str(round_dir / RUN_NAME)))


def context_resolved(directory: Path | None, round_no: int | None, /) -> Result[Context, Fault]:
    def chosen(repo: Path, /) -> Result[Context, Fault]:
        rounds = round_dirs(repo)
        found = next((d for d in rounds if round_number(d) == round_no), None) if round_no is not None else (rounds[-1] if rounds else None)
        if found is None:
            wanted = f"round {round_no}" if round_no is not None else "any round-*"
            return Error(Fault(code="no-round", detail=f"{wanted} not under {repo / STATE_DIR}; launch first"))
        return run_loaded(found).map(lambda run: Context(repo=repo, round_dir=found, run=run))

    return repo_root(directory).bind(chosen)


def rounds_read(repo: Path, /) -> tuple[RoundRow, ...]:
    lines = read_bytes(repo / STATE_DIR / LEDGER_NAME).map(bytes.splitlines).default_with(lambda _f: [])
    return tuple(Block.of_seq(lines).choose(lambda line: decoded(line, RoundRow, LEDGER_NAME).to_option() if line.strip() else Nothing))


# --- [PROBE]


@dataclass(frozen=True, slots=True, kw_only=True)
class Markers:
    start_grace_s: float
    stall_grace_s: float
    deadline_s: float
    done: Option[re.Pattern[str]] = Nothing
    dead: Option[re.Pattern[str]] = Nothing
    refusal: Option[re.Pattern[str]] = Nothing
    pulse: Option[re.Pattern[str]] = Nothing
    tick: Option[re.Pattern[str]] = Nothing


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamProbe:
    remainder: str = ""
    done: bool = False
    dead: Option[str] = Nothing
    refusal: Option[str] = Nothing
    pulses: int = 0
    ticks: int = 0
    exited: Option[int] = Nothing
    tail: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class Liveness:
    elapsed: float
    pulse_age: float
    alive: bool


def plain(line: str, /) -> str:
    return ANSI_RE.sub("", line).strip()[:HEADLINE]


def marker_hit(pattern: Option[re.Pattern[str]], line: str, /) -> bool:
    return pattern.filter(lambda held: held.search(line) is not None).is_some()


def marker_caught(prior: Option[str], pattern: Option[re.Pattern[str]], line: str, /) -> Option[str]:
    return prior if prior.is_some() else pattern.bind(lambda held: Some(plain(line)) if held.search(line) else Nothing)


def scanned(probe: StreamProbe, chunk: str, markers: Markers, /) -> StreamProbe:
    lines = (probe.remainder + chunk).split("\n")

    def stepped(acc: StreamProbe, line: str, /) -> StreamProbe:
        exit_hit = EXIT_LINE_RE.match(line)
        bare = line.strip()
        return evolved(
            acc,
            done=acc.done or marker_hit(markers.done, line),
            dead=marker_caught(acc.dead, markers.dead, line),
            refusal=marker_caught(acc.refusal, markers.refusal, line),
            pulses=acc.pulses + int(marker_hit(markers.pulse, line)),
            ticks=acc.ticks + int(marker_hit(markers.tick, line)),
            exited=Some(int(exit_hit.group(1))) if exit_hit else acc.exited,
            tail=plain(line) if bare and not bare.startswith(EXIT_MARK) else acc.tail,
        )

    folded: StreamProbe = reduce(stepped, lines[:-1], probe)
    return evolved(folded, remainder=lines[-1])


def phased(probe: StreamProbe, markers: Markers, live: Liveness, /) -> tuple[Phase, str]:
    silent_start = markers.pulse.is_some() and probe.pulses == 0
    exit_zero = probe.exited.filter(lambda code: code == 0).is_some()
    rules: tuple[tuple[bool, Phase, str], ...] = (
        (probe.refusal.is_some(), "refused", probe.refusal.default_value("")),
        (probe.done, "completed", ""),
        (probe.dead.is_some(), "failed", probe.dead.default_value("")),
        (exit_zero and markers.done.is_none(), "completed", ""),
        (exit_zero, "failed", "exited 0 without the engine's terminal marker"),
        (probe.exited.is_some(), "failed", probe.tail or f"exit={probe.exited.default_value(-1)}"),
        (not live.alive, "failed", "process died without a terminal marker"),
        (live.elapsed > markers.deadline_s, "timed-out", f"exceeded the {markers.deadline_s:.0f}s engine deadline"),
        (
            silent_start and live.elapsed > markers.start_grace_s and live.pulse_age > markers.start_grace_s,
            "stalled",
            f"no pulse marker and no output within the {markers.start_grace_s:.0f}s start grace",
        ),
        (live.pulse_age > markers.stall_grace_s, "stalled", f"alive with no output for {live.pulse_age:.0f}s (grace {markers.stall_grace_s:.0f}s)"),
        (probe.pulses > 0 or probe.ticks > 0, "reviewing", ""),
    )
    return next(((phase, detail) for hit, phase, detail in rules if hit), ("launched", ""))


def status_of(context: Context, probe: StreamProbe, broken: Option[str], /) -> StatusReceipt:
    markers = ADAPTERS[context.run.reviewer].markers
    log = context.round_dir / LOG_NAME
    now = time.time()
    mtime = catch(exception=OSError)(log.stat)().to_option().map(lambda held: held.st_mtime)
    live = Liveness(
        elapsed=max(now - context.run.started, 0.0),
        pulse_age=max(now - mtime.default_value(context.run.started), 0.0),
        alive=breathing(context.run.pid, context.run.argv[0]),
    )

    def broken_status(cause: str, /) -> tuple[Phase, str]:
        return "failed", cause

    phase, detail = broken.map(broken_status).default_with(lambda: phased(probe, markers, live))
    settled_at = mtime.map(lambda held: max(held - context.run.started, 0.0)).default_value(live.elapsed)
    return StatusReceipt(
        round=context.run.round,
        reviewer=context.run.reviewer,
        scope=context.run.scope.line,
        phase=phase,
        elapsed_s=round(min(live.elapsed, settled_at) if phase in TERMINAL else live.elapsed, 1),
        last_pulse_age_s=round(live.pulse_age, 1),
        findings_seen=probe.ticks,
        detail=detail,
        log=str(log),
    )


def observed(context: Context, /) -> StatusReceipt:
    markers = ADAPTERS[context.run.reviewer].markers
    log = context.round_dir / LOG_NAME
    payload = read_bytes(log)
    text = payload.map(lambda raw: raw.decode(errors="replace")).default_with(lambda _f: "")
    broken = payload.swap().to_option().bind(lambda fault: Some(fault.detail) if log.is_file() else Nothing)
    return status_of(context, scanned(StreamProbe(), text + "\n", markers), broken)


def log_chunk(log: Path, offset: int, /) -> tuple[str, int]:
    def sliced_read() -> tuple[str, int]:
        with log.open("rb") as source:
            source.seek(offset)
            payload = source.read()
        return payload.decode(errors="replace"), offset + len(payload)

    return catch(exception=OSError)(sliced_read)().default_with(lambda _f: ("", offset))


# --- [NORMALIZE]


def headline(text: str, /) -> str:
    return next((line.strip()[:HEADLINE] for line in text.splitlines() if line.strip()), "")


def ranked(native: str, /) -> Severity:
    return SEVERITY_MAP.get(native.lower(), "minor")


def stemmed(claim: str, /) -> str:
    return STEM_RE.sub(" ", unicodedata.normalize("NFC", claim).casefold()).strip()[:CLAIM_STEM]


def fingerprinted(file: str, span: Range, claim: str, /) -> str:
    return hashlib.sha256(f"{file}|{span.start}:{span.end}|{stemmed(claim)}".encode()).hexdigest()[:16]


def minted(reviewer: Reviewer, file: str, span: Range, claim: str, fix: str, severity: str, payload: bytes, /) -> Option[Finding]:
    if not file and not claim:
        return Nothing
    return Some(
        Finding(
            id="",
            fingerprint=fingerprinted(file, span, claim),
            reviewer=reviewer,
            file=file,
            range=span,
            severity=ranked(severity),
            claim=claim,
            fix_instructions=fix,
            class_match="",
            raw=msgspec.Raw(payload),
        )
    )


def counted(rows: tuple[Finding, ...], /) -> dict[str, int]:
    tally = Counter(row.severity for row in rows)
    return {level: tally[level] for level in SEVERITIES if level in tally}


def compiled(registry: Registry, /) -> tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]:
    def pattern(matcher: str, /) -> re.Pattern[str]:
        return catch(exception=re.PatternError)(re.compile)(matcher, re.IGNORECASE).default_with(
            lambda _bad: re.compile(re.escape(matcher), re.IGNORECASE)
        )

    return tuple((row.class_id, tuple(pattern(matcher) for matcher in row.matchers)) for row in registry.classes)


def classified(matchers: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...], claim: str, /) -> str:
    return next((class_id for class_id, patterns in matchers if any(pattern.search(claim) for pattern in patterns)), "")


def normalized(rows: tuple[Finding, ...], registry: Registry, /) -> tuple[Finding, ...]:
    matchers = compiled(registry)
    stamped = tuple(replace(row, class_match=classified(matchers, row.claim)) for row in rows)
    ordered = sorted(stamped, key=lambda row: (row.fingerprint, RANK[row.severity]))
    survivors = tuple(next(iter(bunch)) for _, bunch in groupby(ordered, key=lambda row: row.fingerprint))
    return tuple(sorted(survivors, key=lambda row: (RANK[row.severity], row.file, row.range.start)))


def pruned_against(prior: tuple[Finding, ...], rows: tuple[Finding, ...], /) -> tuple[tuple[Finding, ...], int]:
    seen = {row.fingerprint for row in prior}
    kept = tuple(row for row in rows if row.fingerprint not in seen)
    return kept, len(rows) - len(kept)


# --- [HARVEST_LEGS]


def cr_epoch(repo: Path, run: Run, now: float, /) -> Option[Path]:
    low, high = run.started - STORE_SLACK_S, now + STORE_SLACK_S
    anchor = Path(os.path.realpath(repo))
    stamped = Block.of_seq(CR_STORE.glob("*/*/reviews/*/git.json")).choose(
        lambda meta_path: shaped(meta_path, CrMeta).bind(
            lambda meta: (
                Some((meta.timestamp, meta_path.parent))
                if meta.working_directory and Path(os.path.realpath(meta.working_directory)) == anchor and low <= meta.timestamp <= high
                else Nothing
            )
        )
    )

    def launch_distance(stamp: tuple[float, Path], /) -> tuple[float, float]:
        at = stamp[0]
        return (0.0 if run.started <= at <= now else min(abs(at - run.started), abs(at - now)), abs(at - run.started))

    ordered = sorted(stamped, key=launch_distance)
    return Some(ordered[0][1]) if ordered else Nothing


def cr_span(rich: CrRich, /) -> Range:
    match rich.line_range:
        case CrRange(start=start, end=end) if start or end:
            return Range(start=start, end=end)
        case _:
            return Range(start=rich.start_line, end=rich.end_line or rich.start_line)


def cr_admitted(path: Path, /) -> Option[Finding]:
    def projected(payload: bytes, rich: CrRich, /) -> Option[Finding]:
        span = cr_span(rich)
        claim = headline(rich.title or rich.comment)
        return minted("coderabbit", rich.file_name, span, claim, rich.codegen_instructions or rich.comment, rich.severity, payload).map(
            lambda row: replace(row, fingerprint=rich.fingerprint or row.fingerprint)
        )

    return (
        read_bytes(path).to_option().bind(lambda payload: decoded(payload, CrRich, str(path)).to_option().bind(lambda rich: projected(payload, rich)))
    )


def cr_store_rows(epoch: Path, /) -> tuple[Finding, ...]:
    return tuple(Block.of_seq(sorted(epoch.glob("*.json"))).choose(lambda path: Nothing if path.name in CR_META_NAMES else cr_admitted(path)))


def wire_admitted(reviewer: Reviewer, row: dict[str, object], /) -> Option[Finding]:
    def projected(wire: WireFinding, /) -> Option[Finding]:
        span = Range(start=wire.start, end=wire.end or wire.start)
        return minted(reviewer, wire.file, span, headline(wire.body), wire.body, wire.severity, ENCODER.encode(row))

    return catch(exception=ValidationError)(WireFinding.model_validate)(row).to_option().bind(projected)


def reprint_row(event: object, /) -> Option[dict[str, object]]:
    match event:
        case {"type": "finding", **rest}:
            inner = next((value for key in ("data", "finding") if isinstance(value := rest.get(key), dict)), rest)
            return Some({str(key): value for key, value in inner.items()})
        case _:
            return Nothing


def cr_reprinted(context: Context, /) -> Result[tuple[Finding, ...], Fault]:
    # TODO(maghz-pin): pin against the first real run — the reprint event payload shape is unverified; the rich store window match stays the primary leg.
    def mined(text: str, /) -> Result[tuple[Finding, ...], Fault]:
        lines = Block.of_seq(ANSI_RE.sub("", text).splitlines())
        events = lines.choose(lambda line: json_document(line.strip(), 0) if line.strip() else Nothing)
        rows = tuple(events.choose(reprint_row).choose(lambda row: wire_admitted("coderabbit", row)))
        return written(context.round_dir / REPRINT_NAME, text.encode()).bind(
            lambda _path: (
                Ok(rows)
                if rows
                else Error(
                    Fault(code="store-missing", detail=f"no {CR_STORE} epoch matched the run window and the reprint fallback carried no findings")
                )
            )
        )

    return (
        sh(("coderabbit", "review", "findings", "--agent"), cwd=context.repo)
        .map_error(lambda fault: Fault(code="store-missing", detail=f"no {CR_STORE} epoch matched the run window; reprint fallback: {fault.detail}"))
        .bind(mined)
    )


def cr_harvested(context: Context, /) -> Result[tuple[Finding, ...], Fault]:
    def from_store(epoch: Path, /) -> Result[tuple[Finding, ...], Fault]:
        return Ok(cr_store_rows(epoch))

    return cr_epoch(context.repo, context.run, time.time()).map(from_store).default_with(lambda: cr_reprinted(context))


def json_offsets(text: str, /) -> tuple[int, ...]:
    starts = accumulate((len(line) for line in text.splitlines(keepends=True)), initial=0)
    candidates = (
        at + len(line) - len(stripped)
        for at, line in zip(starts, text.splitlines(keepends=True), strict=False)
        if (stripped := line.lstrip())[:1] in {"[", "{"}
    )
    return tuple(islice(candidates, JSON_SCAN_CAP))


def json_documents(text: str, /) -> tuple[object, ...]:
    def stepped(acc: tuple[int, tuple[object, ...]], at: int, /) -> tuple[int, tuple[object, ...]]:
        horizon, docs = acc
        if at < horizon:
            return acc
        return catch(exception=ValueError)(RAW_JSON.raw_decode)(text, at).to_option().map(lambda pair: (pair[1], (*docs, pair[0]))).default_value(acc)

    seed: tuple[int, tuple[object, ...]] = (0, ())
    return reduce(stepped, json_offsets(text), seed)[1]


def stringly(raw: object, /) -> dict[str, object]:
    return {str(key): value for key, value in raw.items()} if isinstance(raw, dict) else {}


def greptile_rows(doc: object, /) -> tuple[dict[str, object], ...]:
    # TODO(maghz-pin): pin against the first real run — envelope keys (top-level list, {comments|findings|issues}, one nested level) are candidates.
    def rows_at(body: dict[str, object], /) -> Option[Sequence[object]]:
        return next((Some(value) for key in ROW_KEYS if isinstance(value := body.get(key), list)), Nothing)

    match doc:
        case list() as items:
            found: Sequence[object] = items
        case dict():
            body = stringly(doc)
            nested = Block.of_seq(body.values()).choose(lambda value: rows_at(stringly(value)) if isinstance(value, dict) else Nothing)
            found = rows_at(body).default_with(lambda: nested.head() if not nested.is_empty() else [])
        case _:
            found = []
    return tuple(stringly(row) for row in found if isinstance(row, dict))


def greptile_payload(text: str, origin: str, /) -> Result[tuple[dict[str, object], ...], Fault]:
    docs = Block.of_seq(json_documents(text))
    projected = docs.map(greptile_rows)
    populated = projected.choose(lambda rows: Some(rows) if rows else Nothing)
    return (
        Ok(populated.head())
        if not populated.is_empty()
        else Ok(())
        if not docs.is_empty()
        else Error(Fault(code="no-payload", detail=f"{origin}: no JSON document in the greptile stream"))
    )


def greptile_harvested(context: Context, /) -> Result[tuple[Finding, ...], Fault]:
    log = context.round_dir / LOG_NAME

    def kept_lines(text: str, /) -> str:
        return "\n".join(line for line in text.splitlines() if not line.startswith(EXIT_MARK))

    return (
        read_bytes(log)
        .map(lambda raw: kept_lines(ANSI_RE.sub("", raw.decode(errors="replace"))))
        .bind(lambda text: greptile_payload(text, str(log)))
        .map(lambda rows: tuple(Block.of_seq(rows).choose(lambda row: wire_admitted("greptile", row))))
    )


def greptile_trace() -> str:
    return (
        shaped(GREPTILE_LEDGER, GreptileLedger)
        .bind(lambda ledger: Some(ledger.reviews[-1]) if ledger.reviews else Nothing)
        .map(lambda last: f"cli-ledger:{last.run_id}:{last.status}:{last.comment_count} (runId is CLI-local, not the MCP codeReviewId)")
        .default_value("cli-ledger:absent")
    )


def ms_admitted(text: str, at: int, /) -> Option[Finding]:
    def converted(payload: object, /) -> Option[Finding]:
        def as_issue() -> MsIssue:
            return msgspec.convert(payload, type=MsIssue, strict=False)

        return (
            catch(exception=msgspec.ValidationError)(as_issue)()
            .to_option()
            .bind(
                lambda issue: (
                    minted(
                        "macroscope",
                        issue.path,
                        Range(start=issue.line, end=issue.line),
                        headline(issue.body),
                        issue.body,
                        issue.severity,
                        ENCODER.encode(payload),
                    )
                    if issue.issue_id or issue.path
                    else Nothing
                )
            )
        )

    return json_document(text, at).bind(converted)


def ms_harvested(context: Context, /) -> Result[tuple[Finding, ...], Fault]:
    return (
        read_bytes(context.round_dir / LOG_NAME)
        .map(lambda raw: ANSI_RE.sub("", raw.decode(errors="replace")))
        .map(lambda text: tuple(Block.of_seq(ISSUE_AT_RE.finditer(text)).choose(lambda hit: ms_admitted(text, hit.end()))))
    )


# --- [SLICING]


def folder_of(file: str, /) -> str:
    parts = PurePosixPath(file).parts
    return "/".join(parts[:FOLDER_DEPTH]) if len(parts) > FOLDER_DEPTH else "/".join(parts[:-1]) or file


GROUPERS: Final[Mapping[SliceAxis, Callable[[str], str]]] = MappingProxyType({"folder": folder_of})


def loc_of(path: Path, /) -> int:
    return read_bytes(path).map(lambda payload: payload.count(b"\n")).default_with(lambda _f: 0)


def rulings_of(registry: Registry, /) -> tuple[str, ...]:
    return tuple(f"{row.class_id}: {row.refuting_citation}".rstrip(": ") for row in registry.classes)


def sliced(
    rows: tuple[Finding, ...], lanes: int, axis: SliceAxis, balance: Balance, repo: Path, round_no: int, rulings: tuple[str, ...], /
) -> tuple[LaneSlice, ...]:
    grouper = GROUPERS[axis]
    ordered = sorted(rows, key=lambda row: grouper(row.file))
    groups = tuple((key, tuple(bunch)) for key, bunch in groupby(ordered, key=lambda row: grouper(row.file)))

    def weighed(bunch: tuple[Finding, ...], /) -> int:
        return len(bunch) if balance == "count" else sum(loc_of(repo / file) for file in {row.file for row in bunch})

    weighted = sorted(((weighed(bunch), key, bunch) for key, bunch in groups), key=itemgetter(0), reverse=True)
    by_folder = dict(groups)

    def packed(
        acc: tuple[tuple[int, tuple[str, ...]], ...], entry: tuple[int, str, tuple[Finding, ...]], /
    ) -> tuple[tuple[int, tuple[str, ...]], ...]:
        slot = min(range(len(acc)), key=lambda at: acc[at][0])
        weight, held = acc[slot]
        return (*acc[:slot], (weight + entry[0], (*held, entry[1])), *acc[slot + 1 :])

    seeds: tuple[tuple[int, tuple[str, ...]], ...] = tuple((0, ()) for _ in range(min(lanes, LANES_CAP)))
    packs = reduce(packed, weighted, seeds)

    def lane_carved(at: int, folders: tuple[str, ...], /) -> LaneSlice:
        letter = LANE_ALPHABET[at]
        picked_rows = sorted(
            (row for folder in folders for row in by_folder[folder]), key=lambda row: (RANK[row.severity], row.file, row.range.start)
        )
        stamped = tuple(replace(row, id=f"r{round_no}{letter}-{index + 1:02d}") for index, row in enumerate(picked_rows))
        criticals = sum(1 for row in stamped if row.severity == "critical")
        return LaneSlice(
            manifest=LaneManifest(
                lane=f"lane-{letter}",
                files=tuple(sorted({row.file for row in stamped})),
                count=len(stamped),
                criticals=criticals,
                suggested_scope_line=f"{', '.join(sorted(folders))} — {len(stamped)} findings, {criticals} critical",
            ),
            settled_rulings=rulings,
            findings=stamped,
        )

    return tuple(lane_carved(at, folders) for at, (_, folders) in enumerate(packs) if folders)


# --- [RECONCILE]


def lane_slices(round_dir: Path, /) -> tuple[tuple[Path, LaneSlice], ...]:
    return tuple(Block.of_seq(sorted(round_dir.glob("lane-?.json"))).choose(lambda path: shaped(path, LaneSlice).map(lambda held: (path, held))))


def lane_reports(round_dir: Path, /) -> tuple[LaneReport, ...]:
    return tuple(Block.of_seq(sorted(round_dir.glob("lane-?-report.json"))).choose(lambda path: shaped(path, LaneReport)))


def lane_stat(lane_path: Path, slice_: LaneSlice, round_dir: Path, /) -> LaneStat:
    report_path = round_dir / f"{slice_.manifest.lane}-report.json"
    report = shaped(report_path, LaneReport)
    ids = {row.id for row in slice_.findings}
    ledger_ids = tuple(row.id for row in report.map(lambda held: held.ledger).default_value(()))
    sliced_at = catch(exception=OSError)(lane_path.stat)().map(lambda held: held.st_mtime).default_with(lambda _f: 0.0)
    reported_at = catch(exception=OSError)(report_path.stat)().map(lambda held: held.st_mtime).default_with(lambda _f: sliced_at)
    wall = report.bind(lambda held: Some(held.wall_s) if held.wall_s > 0 else Nothing).default_with(lambda: reported_at - sliced_at)
    return LaneStat(
        lane=slice_.manifest.lane,
        model=report.map(lambda held: held.model).default_value(""),
        findings=slice_.manifest.count,
        verdicts=report.map(lambda held: dict(Counter(row.verdict or "<blank>" for row in held.ledger))).default_value({}),
        missing=tuple(sorted(ids - set(ledger_ids))),
        phantom=tuple(sorted(set(ledger_ids) - ids - {""})),
        wall_s=round(max(wall, 0.0), 1),
        report_valid=report.is_some(),
    )


def reconciled(round_dir: Path, /) -> Result[tuple[LaneStat, ...], Fault]:
    slices = lane_slices(round_dir)
    if not slices:
        return Error(Fault(code="no-lanes", detail=f"no lane-?.json under {round_dir}; slice first"))
    return Ok(tuple(lane_stat(path, slice_, round_dir) for path, slice_ in slices))


# --- [RECURRENCE]


def recurrence(
    registry: Registry, rows: tuple[Finding, ...], reports: tuple[LaneReport, ...], /
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], tuple[Refutation, ...]]:
    matchers = compiled(registry)
    flagged = tuple((row.class_match, f"{row.id or row.fingerprint}: {row.claim}") for row in rows if row.class_match)
    refutations = tuple(entry for report in reports for entry in report.refuted)
    matched = tuple((classified(matchers, entry.claim), f"refuted: {entry.claim}") for entry in refutations)
    recurred = {
        class_id: tuple(instance for hit_id, instance in (*flagged, *matched) if hit_id == class_id)
        for class_id in dict.fromkeys(hit_id for hit_id, _ in (*flagged, *matched) if hit_id)
    }
    fresh = tuple(entry for entry, (hit_id, _) in zip(refutations, matched, strict=True) if not hit_id)
    return tuple(recurred.items()), fresh


def raw_text(raw: msgspec.Raw, /) -> str:
    match json_value(bytes(raw), "report-row"):
        case Result(tag="ok", ok=str() as text):
            return text
        case Result(tag="ok", ok=value):
            return ENCODER.encode(value).decode()
        case _:
            return bytes(raw).decode(errors="replace")


def slugged(claim: str, /) -> str:
    return "-".join(stemmed(claim).split()[:4]) or "unnamed"


def proposal_block(fresh: tuple[Refutation, ...], round_no: int, /) -> tuple[str, ...]:
    if not fresh:
        return ()
    rows = [
        {
            "class_id": slugged(entry.claim),
            "matchers": [stemmed(entry.claim)],
            "refuting_citation": "",
            "landed_surfaces": [],
            "rounds_seen": [round_no],
        }
        for entry in fresh
    ]
    sink = io.StringIO()
    YAML_RT.dump({"classes": rows}, sink)
    return ("```yaml proposed-registry-rows", sink.getvalue().rstrip("\n"), "```")


def feed_rendered(
    run: Run, recurred: tuple[tuple[str, tuple[str, ...]], ...], fresh: tuple[Refutation, ...], reports: tuple[LaneReport, ...], registry: Registry, /
) -> str:
    citations = {row.class_id: row.refuting_citation for row in registry.classes}
    sections = (
        f"# [HARVEST_FEED] round {run.round} — {run.reviewer} — {run.scope.line}",
        *((f"focus: {run.focus}",) if run.focus else ()),
        "## [RECURRED]",
        *(
            f"- `{class_id}` ({citations.get(class_id, '')}) — guard did not bite:\n" + "\n".join(f"  - {instance}" for instance in instances)
            for class_id, instances in recurred
        ),
        "## [NEW_REFUTED]",
        *(f"- {entry.claim} — {entry.evidence}" for entry in fresh),
        *proposal_block(fresh, run.round),
        "## [IMPROVEMENTS]",
        *(f"- {row.page} — {row.pattern} — {row.what}" for report in reports for row in report.improvements),
        "## [CAPABILITY_LANDED]",
        *(f"- {raw_text(row)}" for report in reports for row in report.capability),
        "## [ROUTED]",
        *(f"- {raw_text(row)}" for report in reports for row in report.routing),
        *(f"- (uncertain) {raw_text(row)}" for report in reports for row in report.uncertain),
    )
    return "\n".join(sections) + "\n"


# --- [ROUND_LEDGER]


def row_built(
    context: Context, rows: tuple[Finding, ...], stats: tuple[LaneStat, ...], reports: tuple[LaneReport, ...], registry: Registry, /
) -> RoundRow:
    recurred, fresh = recurrence(registry, rows, reports)
    return RoundRow(
        round=context.run.round,
        reviewer=context.run.reviewer,
        scope=context.run.scope.line,
        counts_by_severity=counted(rows),
        total=len(rows),
        lanes=stats,
        recurred_classes=tuple(class_id for class_id, _ in recurred),
        new_classes=len(fresh),
        routed=sum(len(report.routing) + len(report.uncertain) for report in reports),
        capability_rows=sum(len(report.capability) for report in reports),
        commit=sh(("git", "-C", str(context.repo), "rev-parse", "--short", "HEAD")).default_with(lambda _f: ""),
        at=round(time.time(), 1),
        focus=context.run.focus,
    )


def delta_of(prior: RoundRow | None, row: RoundRow, /) -> Delta | None:
    if prior is None:
        return None
    return Delta(
        prior_round=prior.round,
        total_delta=row.total - prior.total,
        by_severity={
            level: row.counts_by_severity.get(level, 0) - prior.counts_by_severity.get(level, 0)
            for level in SEVERITIES
            if level in row.counts_by_severity or level in prior.counts_by_severity
        },
        recurred_still=tuple(class_id for class_id in row.recurred_classes if class_id in prior.recurred_classes),
    )


# --- [COMPOSITION] ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Adapter:
    scopes: frozenset[ScopeKind]
    armed: Callable[[Scope], tuple[str, ...]]
    focused: Callable[[str, Path], Result[tuple[str, ...], Fault]]
    markers: Markers
    harvested: Callable[[Context], Result[tuple[Finding, ...], Fault]]
    source: Callable[[Context], str]


def cr_argv(scope: Scope, /) -> tuple[str, ...]:
    match scope.kind:
        case "base":
            return ("coderabbit", "review", "--agent", "--base", scope.ref)
        case "base-commit":
            return ("coderabbit", "review", "--agent", "--base-commit", scope.ref)
        case kind:
            return ("coderabbit", "review", "--agent", "-t", kind)


def greptile_argv(scope: Scope, /) -> tuple[str, ...]:
    return ("greptile", "review", "--json", *(("-b", scope.ref) if scope.kind == "base" else ()))


def ms_argv(scope: Scope, /) -> tuple[str, ...]:
    return ("macroscope", "codereview", "--raw", "--in-place", *(("--base", scope.ref) if scope.kind == "base" else ()))


def cr_focused(text: str, round_dir: Path, /) -> Result[tuple[str, ...], Fault]:
    return written(round_dir / FOCUS_NAME, text.encode()).map(lambda path: ("-c", str(path)))


def greptile_focused(text: str, _round_dir: Path, /) -> Result[tuple[str, ...], Fault]:
    return Ok(("--instructions", text))


def ms_focused(_text: str, _round_dir: Path, /) -> Result[tuple[str, ...], Fault]:
    return Error(
        Fault(code="unsupported-focus", detail="macroscope has no per-run instruction flag; land the concern as .macroscope/ config, then relaunch")
    )


ADAPTERS: Final[Mapping[Reviewer, Adapter]] = MappingProxyType({
    "coderabbit": Adapter(
        scopes=frozenset({"all", "committed", "uncommitted", "base", "base-commit"}),
        armed=cr_argv,
        focused=cr_focused,
        markers=Markers(
            start_grace_s=180.0,
            stall_grace_s=420.0,
            deadline_s=2700.0,
            done=Some(re.compile(r'"type"\s*:\s*"complete"')),
            dead=Some(re.compile(r'"type"\s*:\s*"error"')),
            pulse=Some(re.compile(r'"type"\s*:\s*"(?:heartbeat|status)"')),
            tick=Some(re.compile(r'"type"\s*:\s*"finding"')),
        ),
        harvested=cr_harvested,
        source=lambda context: cr_epoch(context.repo, context.run, time.time()).map(str).default_value("store-missing (reprint fallback)"),
    ),
    "greptile": Adapter(
        scopes=frozenset({"committed", "base"}),
        armed=greptile_argv,
        focused=greptile_focused,
        markers=Markers(start_grace_s=300.0, stall_grace_s=600.0, deadline_s=1500.0, refusal=Some(re.compile(r"this review is too large to send"))),
        harvested=greptile_harvested,
        source=lambda _context: greptile_trace(),
    ),
    "macroscope": Adapter(
        scopes=frozenset({"uncommitted", "base"}),
        armed=ms_argv,
        focused=ms_focused,
        markers=Markers(
            start_grace_s=90.0,
            stall_grace_s=300.0,
            deadline_s=1800.0,
            done=Some(re.compile(r"issue_status\s*=\s*completed")),
            dead=Some(re.compile(r"issue_status\s*=\s*failed")),
            pulse=Some(re.compile(r"review_id\s*=")),
            tick=Some(re.compile(r"issue_event\s*=")),
        ),
        harvested=ms_harvested,
        source=lambda context: str(context.round_dir / LOG_NAME),
    ),
})

# --- [ENTRY] ----------------------------------------------------------------------------

type _Dir = Annotated[Path | None, Parameter(name=("--dir", "--directory"))]
type _RoundNo = Annotated[int | None, Parameter(name="--round")]


def focus_resolved(spec: str, /) -> Result[str, Fault]:
    candidate = Path(spec)
    return read_bytes(candidate).map(lambda raw: raw.decode(errors="replace")) if spec and candidate.is_file() else Ok(spec)


def launched(repo: Path, reviewer: Reviewer, scope: Scope, focus: str, /) -> Result[LaunchReceipt, Fault]:
    adapter = ADAPTERS[reviewer]
    if scope.kind not in adapter.scopes:
        return Error(Fault(code="unsupported-scope", detail=f"{reviewer} accepts {sorted(adapter.scopes)}, not {scope.line!r}"))
    rounds = round_dirs(repo)
    held: Option[Run] = run_loaded(rounds[-1]).to_option() if rounds else Nothing
    blocking = held.map(lambda prior: observed(Context(repo=repo, round_dir=rounds[-1], run=prior))).bind(
        lambda status: Some(status) if status.phase not in TERMINAL else Nothing
    )
    match blocking:
        case Option(tag="some", some=live):
            return Error(
                Fault(
                    code="live-run",
                    detail=f"round {live.round} ({live.reviewer}) is still {live.phase}; a wedged engine converts to stalled/timed-out once its grace lapses",
                )
            )
        case _:
            pass
    number = (round_number(rounds[-1]) if rounds else 0) + 1
    round_dir = repo / STATE_DIR / f"round-{number:03d}"
    made = catch(exception=OSError)(round_dir.mkdir)(parents=True).map_error(
        lambda unmakeable: Fault(code="unwritable", detail=f"{round_dir}: {unmakeable}")
    )

    def unrounded(fault: Fault, /) -> Fault:
        catch(exception=OSError)(shutil.rmtree)(round_dir)
        return fault

    def armed_and_spawned(_made: object, /) -> Result[LaunchReceipt, Fault]:
        focus_argv: Result[tuple[str, ...], Fault] = Ok(()) if not focus else adapter.focused(focus, round_dir)
        return focus_argv.map_error(unrounded).bind(lambda extra: flown((*adapter.armed(scope), *extra)))

    def flown(argv: tuple[str, ...], /) -> Result[LaunchReceipt, Fault]:
        return spawned(argv, round_dir / LOG_NAME, repo).bind(
            lambda pid: written(
                round_dir / RUN_NAME,
                ENCODER.encode(Run(round=number, reviewer=reviewer, scope=scope, pid=pid, started=time.time(), argv=argv, focus=focus)),
            ).map(
                lambda run_path: LaunchReceipt(
                    round=number,
                    reviewer=reviewer,
                    scope=scope.line,
                    pid=pid,
                    argv=argv,
                    focus=focus,
                    log=str(round_dir / LOG_NAME),
                    run=str(run_path),
                )
            )
        )

    return made.bind(armed_and_spawned)


@APP.command
def launch(*, reviewer: Reviewer, scope: str, focus: str = "", directory: _Dir = None) -> int:
    return delivered(
        repo_root(directory).bind(
            lambda repo: Scope.of(scope).bind(lambda parsed: focus_resolved(focus).bind(lambda text: launched(repo, reviewer, parsed, text)))
        )
    )


def followed(context: Context, /) -> int:
    markers = ADAPTERS[context.run.reviewer].markers
    log = context.round_dir / LOG_NAME
    probe, offset = StreamProbe(), 0
    last: Phase | Literal[""] = ""
    noted = time.time()
    while True:  # bounded: phased() converts every hang to a terminal stalled/timed-out verdict, so this loop always exits
        chunk, offset = log_chunk(log, offset)
        probe = scanned(probe, chunk, markers)
        receipt = status_of(context, probe, Nothing)
        if receipt.phase in TERMINAL:
            emitted(receipt)
            return 0 if receipt.phase == "completed" else 1
        now = time.time()
        if receipt.phase != last:
            last, noted = receipt.phase, now
            print(f"[{receipt.phase.upper()}] round={receipt.round} reviewer={receipt.reviewer} elapsed={receipt.elapsed_s:.0f}s")
        elif now - noted > LIVENESS_NOTE_S:
            noted = now
            print(
                f"[{receipt.phase.upper()}] elapsed={receipt.elapsed_s:.0f}s pulse_age={receipt.last_pulse_age_s:.0f}s findings={receipt.findings_seen}"
            )
        time.sleep(POLL_S)


@APP.command
def status(*, follow: bool = False, round_no: _RoundNo = None, directory: _Dir = None) -> int:
    context = context_resolved(directory, round_no)
    match context, follow:
        case Result(tag="error", error=fault), _:
            return refused(fault)
        case Result(tag="ok", ok=held), True:
            return followed(held)
        case Result(tag="ok", ok=held), False:
            return emitted(observed(held))
        case _:
            return 1


def findings_normalized(context: Context, prior_round: int | None, /) -> Result[FindingsReceipt, Fault]:
    adapter = ADAPTERS[context.run.reviewer]
    if tuple(context.round_dir.glob("lane-?.json")):
        return Error(Fault(code="already-sliced", detail=f"{context.round_dir} carries lane slices; a re-normalize would orphan the stamped ids"))
    terminal = observed(context)
    if terminal.phase != "completed":
        return Error(
            Fault(code="not-completed", detail=f"round {context.run.round} is {terminal.phase}: {terminal.detail or 'wait for the terminal phase'}")
        )

    def persisted(rows: tuple[Finding, ...], registry: Registry, /) -> Result[FindingsReceipt, Fault]:
        kept = normalized(rows, registry)
        return cross_pruned(context.repo, prior_round, kept).bind(
            lambda pruned: written(context.round_dir / FINDINGS_NAME, ENCODER.encode(pruned[0])).map(
                lambda path: FindingsReceipt(
                    round=context.run.round,
                    reviewer=context.run.reviewer,
                    total=len(pruned[0]),
                    deduped=len(rows) - len(kept),
                    cross_deduped=pruned[1],
                    classified=sum(1 for row in pruned[0] if row.class_match),
                    counts_by_severity=counted(pruned[0]),
                    source=adapter.source(context),
                    path=str(path),
                )
            )
        )

    return registry_loaded().bind(lambda registry: adapter.harvested(context).bind(lambda rows: persisted(rows, registry)))


def cross_pruned(repo: Path, prior_round: int | None, rows: tuple[Finding, ...], /) -> Result[tuple[tuple[Finding, ...], int], Fault]:
    if prior_round is None:
        return Ok((rows, 0))
    path = repo / STATE_DIR / f"round-{prior_round:03d}" / FINDINGS_NAME
    return read_bytes(path).bind(lambda payload: decoded(payload, tuple[Finding, ...], str(path))).map(lambda prior: pruned_against(prior, rows))


def findings_read(context: Context, /) -> Result[tuple[Finding, ...], Fault]:
    path = context.round_dir / FINDINGS_NAME
    if not path.is_file():
        return Error(Fault(code="no-findings", detail=f"{path} absent; run findings --normalize first"))
    return read_bytes(path).bind(lambda payload: decoded(payload, tuple[Finding, ...], str(path)))


@APP.command
def findings(
    *,
    normalize: bool = False,
    dedup_against: Annotated[int | None, Parameter(name="--dedup-against")] = None,
    round_no: _RoundNo = None,
    directory: _Dir = None,
) -> int:
    def summarized(context: Context, /) -> Result[FindingsReceipt, Fault]:
        return findings_read(context).map(
            lambda rows: FindingsReceipt(
                round=context.run.round,
                reviewer=context.run.reviewer,
                total=len(rows),
                deduped=0,
                cross_deduped=0,
                classified=sum(1 for row in rows if row.class_match),
                counts_by_severity=counted(rows),
                source=str(context.round_dir / FINDINGS_NAME),
                path=str(context.round_dir / FINDINGS_NAME),
            )
        )

    resolved = context_resolved(directory, round_no)
    return delivered(resolved.bind(lambda context: findings_normalized(context, dedup_against) if normalize else summarized(context)))


@APP.command(name="slice")
def slice_cmd(
    *,
    lanes: Annotated[int, Parameter(name="--lanes")] = 3,
    by: SliceAxis = "folder",
    balance: Balance = "count",
    round_no: _RoundNo = None,
    directory: _Dir = None,
) -> int:
    def carved_round(context: Context, /) -> Result[SliceReceipt, Fault]:
        if not 1 <= lanes <= LANES_CAP:
            return Error(Fault(code="bad-lane", detail=f"lanes must be 1..{LANES_CAP}, got {lanes}"))
        stale = (*context.round_dir.glob("lane-?.json"), *context.round_dir.glob("lane-?-report.json"))
        return unlinked(stale).bind(
            lambda cleared: registry_loaded().bind(
                lambda registry: findings_read(context).bind(
                    lambda rows: slices_written(
                        context, sliced(rows, lanes, by, balance, context.repo, context.run.round, rulings_of(registry)), cleared
                    )
                )
            )
        )

    def slices_written(context: Context, packs: tuple[LaneSlice, ...], cleared: int, /) -> Result[SliceReceipt, Fault]:
        if not packs:
            return Error(Fault(code="no-findings", detail=f"round {context.run.round} has zero findings to slice; close it with `round` and rotate"))
        stamped = tuple(row for pack in packs for row in pack.findings)
        writes = (
            *((context.round_dir / f"{pack.manifest.lane}.json", ENCODER.encode(pack)) for pack in packs),
            (context.round_dir / FINDINGS_NAME, ENCODER.encode(stamped)),
        )
        outcome: Result[Path, Fault] = reduce(lambda acc, job: acc.bind(lambda _done: written(*job)), writes, Ok(context.round_dir))
        return outcome.map(
            lambda _last: SliceReceipt(
                round=context.run.round,
                lanes=tuple(pack.manifest for pack in packs),
                stamped=len(stamped),
                settled_rulings=len(packs[0].settled_rulings),
                cleared=cleared,
            )
        )

    return delivered(context_resolved(directory, round_no).bind(carved_round))


@APP.command
def reconcile(
    lane: str = "", /, *, all_lanes: Annotated[bool, Parameter(name="--all")] = False, round_no: _RoundNo = None, directory: _Dir = None
) -> int:
    def resolved(context: Context, /) -> Result[ReconcileReceipt, Fault]:
        if all_lanes and lane:
            return Error(Fault(code="bad-lane", detail=f"--all excludes a named lane; drop {lane!r} or the flag"))
        wanted = lane.removeprefix("lane-")
        return reconciled(context.round_dir).bind(
            lambda stats: (
                Error(Fault(code="bad-lane", detail=f"lane-{wanted} not among {tuple(stat.lane for stat in stats)}"))
                if wanted and not any(stat.lane == f"lane-{wanted}" for stat in stats)
                else Ok(
                    ReconcileReceipt(
                        round=context.run.round,
                        lanes=(kept := tuple(stat for stat in stats if not wanted or stat.lane == f"lane-{wanted}")),
                        bijective=all(stat.report_valid and not stat.missing and not stat.phantom for stat in kept),
                    )
                )
            )
        )

    return delivered(context_resolved(directory, round_no).bind(resolved))


@APP.command
def harvest(*, round_no: _RoundNo = None, directory: _Dir = None) -> int:
    def gathered(context: Context, /) -> Result[HarvestReceipt, Fault]:
        reports = lane_reports(context.round_dir)
        if not reports:
            return Error(Fault(code="no-report", detail=f"no lane-?-report.json under {context.round_dir}; fixer lanes write reports first"))
        return registry_loaded().bind(lambda registry: findings_read(context).bind(lambda rows: fed(context, registry, rows, reports)))

    def fed(context: Context, registry: Registry, rows: tuple[Finding, ...], reports: tuple[LaneReport, ...], /) -> Result[HarvestReceipt, Fault]:
        recurred, fresh = recurrence(registry, rows, reports)
        feed = feed_rendered(context.run, recurred, fresh, reports, registry)
        return written(context.round_dir / FEED_NAME, feed.encode()).map(
            lambda path: HarvestReceipt(
                round=context.run.round,
                reports=len(reports),
                recurred=tuple(class_id for class_id, _ in recurred),
                new_refuted=len(fresh),
                improvements=sum(len(report.improvements) for report in reports),
                capability=sum(len(report.capability) for report in reports),
                routed=sum(len(report.routing) + len(report.uncertain) for report in reports),
                path=str(path),
            )
        )

    return delivered(context_resolved(directory, round_no).bind(gathered))


@APP.command(name="round")
def round_cmd(*, round_no: _RoundNo = None, directory: _Dir = None) -> int:
    def closed(context: Context, /) -> Result[RoundReceipt, Fault]:
        if any(row.round == context.run.round for row in rounds_read(context.repo)):
            return Error(Fault(code="already-closed", detail=f"round {context.run.round} already has a {LEDGER_NAME} row"))
        return registry_loaded().bind(lambda registry: findings_read(context).bind(lambda rows: assembled(context, rows, registry)))

    def assembled(context: Context, rows: tuple[Finding, ...], registry: Registry, /) -> Result[RoundReceipt, Fault]:
        if not rows:
            return appended(context, row_built(context, rows, (), (), registry))
        reports = lane_reports(context.round_dir)
        if not reports:
            return Error(
                Fault(code="no-report", detail=f"round {context.run.round} has findings but no lane-?-report.json; fix lanes before closing")
            )
        return reconciled(context.round_dir).bind(lambda stats: appended(context, row_built(context, rows, stats, reports, registry)))

    def appended(context: Context, row: RoundRow, /) -> Result[RoundReceipt, Fault]:
        prior = next((held for held in reversed(rounds_read(context.repo)) if held.round < row.round), None)
        return written(context.repo / STATE_DIR / LEDGER_NAME, ENCODER.encode(row) + b"\n", append=True).map(
            lambda _path: RoundReceipt(row=row, delta=delta_of(prior, row))
        )

    return delivered(context_resolved(directory, round_no).bind(closed))


@APP.command
def verify(*, rule: str, path: str = "", directory: _Dir = None) -> int:
    def checked(repo: Path, /) -> Result[VerifyReceipt, Fault]:
        argv = ("greptile", "config", *((path,) if path else ()))
        return sh(argv, cwd=repo).map(
            lambda effective: VerifyReceipt(
                rule=rule,
                path=path,
                effective=rule.casefold() in ANSI_RE.sub("", effective).casefold(),
                matched=next((plain(line) for line in effective.splitlines() if rule.casefold() in line.casefold()), ""),
                source=shlex.join(argv),
            )
        )

    match repo_root(directory).bind(checked):
        case Result(tag="ok", ok=receipt):
            emitted(receipt)
            return 0 if receipt.effective else 1
        case Result(tag="error", error=fault):
            return refused(fault)
        case _:
            return 1


if __name__ == "__main__":
    sys.exit(APP(sys.argv[1:], result_action="return_value"))
