"""MCP-as-IaC: the typed server fleet, the five-verb entrypoint, and the runtime rail in one owner.

`admin/mcp/` is the typed source of truth for the MCP server fleet; the committed `.mcp.json` is the
generated artifact. This module owns the whole domain — the `ServerKind` fleet vocabulary, the `McpOp`
modal discriminant, the `ServerSpec` invocation record with its own `argv`/`environ` projection and its
`is_docker` discriminant, the `_SERVER_TABLE` fleet declaration, the `McpConfigDetail` receipt, the five
verb builders, and the single polymorphic `mcp(op, cfg)` entrypoint. There is no per-rail fault carrier:
every boundary mints the one closed `BoundaryFault` family directly (`boundary` for a render/write breach,
`config` for the absent-binary precondition the CONVERGE verb refuses), so the typed `resource`/`deadline`
discrimination survives to the `Envelope` projection exactly as the `cloud`/`n8n`/`schema` siblings expose.
`mcp` self-lowers the interior `RuntimeRail[McpConfigDetail]` to the one stdout `Envelope` at its own edge —
the verb's sole egress, the typed detail single-minted into `report.detail` with no parallel stderr receipt
re-rendering the same fields — threading through the CLI without the shared `runtime.lower` lowering, the
same self-lowering shape `cloud` and `automation.drive` use. Only WATCH emits a distinct ephemeral
`admitted` receipt per change batch (the live `{changes, count}` census that never reaches an `Envelope`),
the one progress fact the receipt stream owns over and above the verb-result `Envelope`.

The fleet projects through `ServerSpec`, never a per-kind `match`: each row owns its `argv` (docker `-e
KEY=VAL` pairs splice ahead of the image, where Docker requires options, and the trailing command follows)
and its static `environ`; the lone settings-sourced overlay (the WORKSPACE credentials dir and conditional
OAuth redirect) is one `_ENV_OVERLAY` row keyed by `ServerKind`, defaulting empty, so adding a server is one
`ServerKind` case plus one `_SERVER_TABLE` row with no branch proliferation. Every secret-bearing key emits
a `${VAR}` placeholder, never a resolved value: secrets inject at the `op run -- claude` process boundary
and are never written to the file.

GENERATE renders then writes; VALIDATE round-trips the committed file and asserts every `${MAGHZ_MCP__*}`
placeholder backs a `McpServerSettings` field; DIFF renders in memory and reports per-server drift against
the committed artifact (the catch for a hand-edited or stale file); WATCH regenerates on every change to the
settings sources or this package under one `watchfiles.awatch` stream, bounded by the caller's cancel scope.
CONVERGE materializes every docker-run server's image as a Pulumi `docker.RemoteImage` desired-state through
the Automation API, so a `--rm` ephemeral `docker run` server never cold-pulls mid-session — the lone
remote boundary, ridden through the substrate `runtime.spawn` probe plus the one fused
`guarded(RetryClass.PROC, ...)` retry+terminal-lift envelope over the worker offload (never a hand-composed
`guard`-inside-`async_boundary` doubled lift), plus the function-locally-gated Pulumi host-side import
(dual-band law: a core-clean dist load never pays the heavy plugin stack).
"""

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from functools import partial
from pathlib import Path
import re
from typing import override

import anyio
import anyio.to_thread
from expression import Error, Ok, Result
from frozendict import frozendict
import msgspec
from watchfiles import awatch, Change, DefaultFilter

from admin.core import completed, Detail, Envelope, fault, Row, Status
from admin.runtime import BoundaryFault, guarded, Receipt, RetryClass, RuntimeRail, Signals
from admin.runtime.rails import spawn
from admin.settings import MaghzSettings, McpServerSettings


# --- [TYPES] ---------------------------------------------------------------------------


class ServerKind(StrEnum):
    """The closed MCP server fleet; one member per `.mcp.json` server, value is the JSON key.

    `ServerSpec.environ` projects each row's env, and the lone settings overlay rides `_ENV_OVERLAY`,
    so a new server lands as one case here plus one `_SERVER_TABLE` row with no branch proliferation.
    The member value is the `mcpServers` object key and the wire encoding of each `McpConfigDetail.servers`
    member, which stays a typed `ServerKind` in memory.

    The fleet is the four genuinely-interactive servers with no skill-CLI equivalent: `postgres`/`n8n`
    (deliberately DUAL-SURFACE — the rail owns deterministic truth, the MCP owns live agent exploration,
    two distinct consumers), `workspace`, and `notebooklm`. Web research (exa/perplexity/tavily) is NOT a
    member: it is served by the portable research skill CLIs for the single in-session agent consumer, so
    carrying it here too would be a duplicate surface at idle context cost. Surface is chosen by consumer —
    deterministic code -> rail, live agent exploration -> MCP, on-demand portable reach -> skill — never by
    concern, so a future research MCP is added only if a live-exploration consumer the skill cannot serve
    materializes.
    """

    POSTGRES = "postgres"
    N8N = "n8n"
    WORKSPACE = "workspace"
    NOTEBOOKLM = "notebooklm"


class McpOp(StrEnum):
    """The `maghz mcp` modal discriminant; `mcp(op, cfg)` dispatches through the total `_BUILD` table.

    GENERATE renders then writes; VALIDATE round-trips and coverage-checks; DIFF reports drift of the
    committed file against a fresh render; WATCH regenerates on every settings/source change; CONVERGE
    materializes the docker-run server images as Pulumi desired-state. A future AUDIT op is one new member
    plus one `_BUILD` row — never a sibling function or module.
    """

    GENERATE = "generate"
    VALIDATE = "validate"
    DIFF = "diff"
    WATCH = "watch"
    CONVERGE = "converge"


# --- [MODELS] --------------------------------------------------------------------------


class ServerSpec(msgspec.Struct, frozen=True, gc=False):
    """The per-server invocation shape, owning its own `argv`/`environ` projection and `image` discriminant.

    `command` plus `args` plus a non-empty `image` (the container image for a docker-run server, spliced
    after the `-e KEY=VAL` pairs `docker_env` folds in — where Docker requires its options, ahead of the
    image — and before any trailing `command` args) is the launch vector. `env` is the top-level Claude
    Code `env` object; `docker_env` carries the docker `-e` pairs. A non-empty `image` is the one
    discriminant the CONVERGE verb folds over (`is_docker`): a docker-run server's image is materialized as
    Pulumi desired-state, a host-process server (`uvx`/`npx`/bare) carries none. Both maps are
    `frozendict[str, str]`; values are `${MAGHZ_MCP__*}` (or bare `${GOOGLE_OAUTH_*}`) placeholder literals
    resolved at the process boundary. `gc=False` is load-bearing: only `str`/`frozendict` fields, no cycles.
    """

    command: str
    args: tuple[str, ...] = ()
    image: str = ""
    env: frozendict[str, str] = frozendict()
    docker_env: frozendict[str, str] = frozendict()

    @property
    def is_docker(self) -> bool:
        """Whether this server runs as a container — the CONVERGE-fold discriminant off the `image` slot."""
        return bool(self.image)

    def argv(self) -> list[str]:
        """Project the full argument vector: `args`, then the docker `-e` pairs, then the image.

        The `-e KEY=VAL` pairs splice between `args` and `image` so a docker-run invocation reads
        `docker run <opts> -e ... <image>` — Docker treats every token after the image as the container
        command, so an `-e` flag past the image is silently dropped. A non-docker server carries an empty
        `docker_env` and `image`, so the vector is just `args`.

        Returns:
            The argument list committed to the server's `.mcp.json` `args` array.
        """
        flags = [token for key, value in self.docker_env.items() for token in ("-e", f"{key}={value}")]
        return [*self.args, *flags, *([self.image] if self.image else [])]

    def environ(self, overlay: Mapping[str, str]) -> dict[str, str]:
        """Project the server's env object, the static `env` overlaid by the settings-sourced `overlay`.

        Args:
            overlay: The settings-sourced keys for this server (the WORKSPACE credentials dir and
                conditional OAuth redirect), empty for every server `_ENV_OVERLAY` does not key.

        Returns:
            The `env` object committed to the server's `.mcp.json` entry.
        """
        return {**self.env, **overlay}


class McpConfigDetail(Detail, frozen=True, tag="mcp"):
    """The one typed verb receipt `mcp()` carries inside the stdout `report.detail` — its sole egress.

    `op` distinguishes the five verb paths; `path` is the filesystem artifact; `server_count` is the
    machine-verifiable fleet size; `servers` carries the rendered `ServerKind` members as load-bearing
    evidence (each encodes to its `.value` key on the wire and decodes back to the closed enum, so the
    evidence is precisely typed in memory yet byte-identical in JSON); `drift` carries the per-server drift
    keys the DIFF verb found (empty for a clean diff and for every non-DIFF verb); `result` carries the
    Pulumi convergence verdict for CONVERGE (empty otherwise). Every field is load-bearing — this detail
    never degrades to a generic envelope. The detail is single-minted: it is serialized exactly once, into
    the `Envelope` the deterministic `core` encoder writes to stdout, and re-spelled nowhere else (no
    parallel stderr `Receipt` re-render of the same fields beside the canonical projection), matching every
    sibling verb rail whose result rides its `report.detail`, never a side-channel receipt copy.
    """

    op: McpOp
    path: str
    server_count: int
    servers: tuple[ServerKind, ...]
    drift: tuple[str, ...] = ()
    result: str = ""


# --- [SERVICES] ------------------------------------------------------------------------

# One process-wide JSON encoder/decoder pair reused across every invocation; constructing a fresh codec
# per call re-resolves the schema, so the shared instances own the wire. The decoder is typed
# `dict[str, object]` so the round-trip reads the committed file as a plain JSON object — VALIDATE checks
# schema integrity, DIFF compares the decoded `mcpServers` object against a fresh render.
_ENCODER = msgspec.json.Encoder()
_DECODER = msgspec.json.Decoder(type=dict[str, object])

# The committed artifact path, relative to the repository root the operator runs from. `.mcp.json` travels
# to the VPS unchanged; the `${VAR}` placeholders resolve from that host's process environment.
_MCP_JSON_PATH = ".mcp.json"

# The `McpServerSettings` field set that backs every `${MAGHZ_MCP__<KEY>}` placeholder; VALIDATE
# lower-cases each captured key and asserts membership here, so a placeholder whose backing field a
# refactor drops surfaces as a coverage breach. Read off the settings group type, never an instance,
# because VALIDATE takes no `cfg` — the backing surface is static, the resolved values are not.
_MCP_FIELDS = frozenset(McpServerSettings.model_fields)

# Every `${MAGHZ_MCP__<KEY>}` occurrence in the rendered file; the captured `<KEY>` lower-cases to a
# `McpServerSettings` field name the coverage check asserts is present. The two bare `${GOOGLE_OAUTH_*}`
# placeholders carry no `MAGHZ_MCP__` prefix, so this pattern never matches them — exempt by construction,
# injected bare at the process boundary by `setup-env.sh`.
_PLACEHOLDER = re.compile(r"\$\{MAGHZ_MCP__([A-Z0-9_]+)\}")

# The WATCH verb watches the repository root (always present, unlike the optional `.env`, whose absence
# would make `awatch` raise `FileNotFoundError` at construction) and narrows to the render inputs through
# `_RenderInputsFilter`: the `.env` settings source and this package's `*.py` source, the only files whose
# change alters the rendered fleet. `_REPO_ROOT` is the operator's cwd; `_PKG_DIR` anchors the source match.
_REPO_ROOT = str(Path.cwd())
_PKG_DIR = str(Path(__file__).resolve().parent)


class _RenderInputsFilter(DefaultFilter):
    """Keep only the changes that alter the rendered fleet: the `.env` settings source and the mcp package source.

    Subclasses `DefaultFilter` so the editor-temp/VCS/build ignore defaults still apply, then narrows to
    the two render inputs by basename (`.env`) and source path (a `*.py` file under this package). Per the
    watchfiles filter law, ignore rules are one `BaseFilter` passed once via `watch_filter`, never per-event
    path tests in the `awatch` consumer.
    """

    @override
    def __call__(self, change: Change, path: str) -> bool:
        if not super().__call__(change, path):
            return False
        return Path(path).name == ".env" or (path.endswith(".py") and path.startswith(_PKG_DIR))


_WATCH_FILTER = _RenderInputsFilter()


# --- [OPERATIONS] ----------------------------------------------------------------------


def _render(cfg: MaghzSettings) -> dict[str, object]:
    """Fold `_SERVER_TABLE` into the wire `mcpServers` object, emitting `${VAR}` placeholders only.

    Each row projects itself: `ServerSpec.argv()` builds the argument vector (docker `-e` pairs ahead of
    the image), and `ServerSpec.environ(overlay)` projects the env, overlaid by the lone settings-sourced
    `_ENV_OVERLAY` row — the WORKSPACE credentials dir from `cfg.integrations.workspace_token_dir` plus a
    conditional `GOOGLE_OAUTH_REDIRECT_URI` from `cfg.integrations.workspace_oauth_redirect_uri`. No
    per-kind `match` and no `SecretStr.get_secret_value()`: secret-bearing keys emit their placeholder
    literals from the table, so the file never carries a resolved secret. The fold is total over the closed
    fleet, so the projection is a pure builtin map, not a rail — a malformed row cannot exist by
    construction (the `frozendict` keys equal `ServerKind`), so there is no admission fault to lift.

    Args:
        cfg: The validated settings; `cfg.integrations` owns the literal workspace credentials dir and the
            conditional OAuth redirect URI the WORKSPACE overlay reads.

    Returns:
        `{"mcpServers": {...}}` carrying one entry per `ServerKind` in declaration order.
    """
    servers = {
        kind.value: {
            "command": (spec := _SERVER_TABLE[kind]).command,
            "args": spec.argv(),
            "env": spec.environ(overlay(cfg) if (overlay := _ENV_OVERLAY.get(kind)) else {}),
        }
        for kind in ServerKind
    }
    return {"mcpServers": servers}


async def _generate(cfg: MaghzSettings) -> RuntimeRail[McpConfigDetail]:
    """Render the fleet, then format and write it to `.mcp.json`, lifting an `OSError` onto the fault rail.

    `_render` is a pure total fold; `msgspec.json.format(ENCODER.encode(fleet), indent=2)` produces the
    human-readable bytes the committed git artifact needs; `anyio.Path(path).write_bytes` performs the async
    write inside `async_boundary`-equivalent grading. An `OSError` from the filesystem boundary lifts as
    `BoundaryFault(boundary=("mcp.write", str(exc)))`, never escaping as a raw traceback.

    Args:
        cfg: The validated settings the render reads.

    Returns:
        `Ok(McpConfigDetail(op=GENERATE))` carrying the path, server count, and enumerated kinds, or
        `Error(BoundaryFault(boundary="mcp.write"))` when the write boundary raises.
    """
    payload = msgspec.json.format(_ENCODER.encode(_render(cfg)), indent=2)
    try:
        await anyio.Path(_MCP_JSON_PATH).write_bytes(payload)
    except OSError as exc:
        return Error(BoundaryFault(boundary=("mcp.write", str(exc))))
    return Ok(_detail(McpOp.GENERATE))


async def _validate(_cfg: MaghzSettings) -> RuntimeRail[McpConfigDetail]:
    """Read `.mcp.json` back, decode it for schema integrity, and assert every placeholder has a backing field.

    `_read_committed` reads and round-trips the committed artifact, lifting an absent/unreadable/malformed
    file to `BoundaryFault(boundary="mcp.validate")`. The coverage check then scans every
    `${MAGHZ_MCP__<KEY>}` occurrence and confirms the lower-cased `<KEY>` is a `McpServerSettings` field; a
    missing backing field is the seam breach the acceptance gate forbids. The two bare `${GOOGLE_OAUTH_*}`
    placeholders never match the `MAGHZ_MCP__` pattern, so they are exempt by construction.

    Args:
        _cfg: Unused by the coverage check (the backing surface is the static `McpServerSettings` type),
            accepted so every `_BUILD` builder shares one `(cfg) -> rail` shape.

    Returns:
        `Ok(McpConfigDetail(op=VALIDATE))` when the file reads, decodes, and every `MAGHZ_MCP__*`
        placeholder is backed, or `Error(BoundaryFault(boundary="mcp.validate"))` for an absent/unreadable
        file, a decode failure, or an unbacked placeholder.
    """
    return (await _read_committed()).bind(lambda read: _coverage(read[0]))


def _coverage(raw: bytes) -> RuntimeRail[McpConfigDetail]:
    """Assert every `${MAGHZ_MCP__<KEY>}` placeholder in the rendered bytes backs a `McpServerSettings` field.

    Each captured `<KEY>` lower-cases to a settings field name; an unbacked placeholder (a backing field a
    refactor dropped) is the seam breach. The bare `${GOOGLE_OAUTH_*}` placeholders never match the
    `MAGHZ_MCP__` pattern, so they are exempt by construction.

    Returns:
        `Ok(McpConfigDetail(op=VALIDATE))` when every placeholder is backed, else
        `Error(BoundaryFault(boundary="mcp.validate"))` naming the unbacked placeholders.
    """
    unbacked = frozenset(m.group(0) for m in _PLACEHOLDER.finditer(raw.decode(errors="replace")) if m.group(1).lower() not in _MCP_FIELDS)
    if unbacked:
        return Error(BoundaryFault(boundary=("mcp.validate", f"placeholders without a McpServerSettings field: {', '.join(sorted(unbacked))}")))
    return Ok(_detail(McpOp.VALIDATE))


async def _diff(cfg: MaghzSettings) -> RuntimeRail[McpConfigDetail]:
    """Render the fleet in memory and report every server whose committed entry drifts from it.

    `_render` produces the canonical `mcpServers` object; `_read_committed` round-trips the file to the same
    shape; `msgspec.to_builtins` normalizes both sides to comparable builtins. A server is drifted when its
    committed entry is absent or unequal to the rendered one (the catch for a hand-edited or stale file —
    the kind of breach a `TOKEN_DIR`/`WORKSPACE_MCP_CREDENTIALS_DIR` key rename leaves behind). The drifted
    `ServerKind` values ride `McpConfigDetail.drift`; a non-empty drift folds to `Status.FAILED` at the
    entrypoint, never a fault — drift is a reported defect, not a boundary breach.

    Args:
        cfg: The validated settings the in-memory render reads.

    Returns:
        `Ok(McpConfigDetail(op=DIFF, drift=...))` carrying the drifted server keys (empty when the committed
        file matches the render), or `Error(BoundaryFault(boundary="mcp.validate"))` when the file is
        absent, unreadable, or malformed.
    """
    rendered = msgspec.to_builtins(_render(cfg))["mcpServers"]
    return (await _read_committed()).map(lambda read: _detail(McpOp.DIFF, drift=_drift(read[1], rendered)))


def _drift(decoded: dict[str, object], rendered: object) -> tuple[str, ...]:
    """Name every `ServerKind` whose committed `mcpServers` entry is absent or unequal to the render.

    The decoded committed object's `mcpServers` is narrowed to a `Mapping` (a hand-edited file could carry
    any JSON value there); an absent or non-mapping value yields the empty map so every server reads as
    drifted. The rendered side is already the canonical `mcpServers` builtin map.

    Returns:
        The drifted server keys in `ServerKind` declaration order, empty when the file matches the render.
    """
    committed = decoded.get("mcpServers")
    servers = committed if isinstance(committed, Mapping) else {}
    rows = rendered if isinstance(rendered, Mapping) else {}
    return tuple(kind.value for kind in ServerKind if servers.get(kind.value) != rows.get(kind.value))


async def _watch(cfg: MaghzSettings) -> RuntimeRail[McpConfigDetail]:
    """Regenerate `.mcp.json` on the initial pass and on every settings/source change until cancelled.

    One `watchfiles.awatch` stream over the `.env` settings source and this package's source tree drives the
    loop: an initial `_generate` renders the current fleet, then each change batch re-renders. A
    regeneration fault short-circuits the watch onto the rail; otherwise the stream runs until the caller's
    cancel scope stops it (the CLI binds no deadline, so `maghz mcp watch` runs until SIGINT, which
    `anyio.run` surfaces as cancellation). Each change batch streams an `admitted` fact through `Signals`,
    so the watch egress rides the receipt rail rather than an inline log line. The receipt the entrypoint
    reports is the last regeneration's — a long-lived watch returns only when stopped or faulted.

    Args:
        cfg: The validated settings each regeneration reads (re-read by the caller is out of scope — the
            watch re-renders from the same in-process settings; a settings-shape change is rare and a
            restart re-reads `.env`).

    Returns:
        The final `Ok(McpConfigDetail(op=WATCH))` when the stream stops cleanly, or the first regeneration
        `Error(BoundaryFault)` that short-circuits the watch.
    """
    if (initial := await _generate(cfg)).is_error():
        return initial
    async for batch in awatch(_REPO_ROOT, watch_filter=_WATCH_FILTER):
        facts: dict[str, object] = {"changes": [change.raw_str() for change, _ in batch], "count": len(batch)}
        await Signals.emit_async(Receipt.of("mcp", ("admitted", McpOp.WATCH.value, facts)))
        if (regen := await _generate(cfg)).is_error():
            return regen
    return Ok(_detail(McpOp.WATCH))


async def _converge(cfg: MaghzSettings) -> RuntimeRail[McpConfigDetail]:
    """Materialize every docker-run server's image as Pulumi `docker.RemoteImage` desired-state, on the rail.

    The lone remote boundary in the fleet: the `--rm` ephemeral `docker run` MCP servers (only N8N today)
    must have their image present so a Claude session never cold-pulls mid-handshake. A preflight asserts
    `docker` is on `PATH` through `runtime.spawn` (`docker --version` under `guard(RetryClass.PROC)`) — an
    absent binary is `Error(BoundaryFault(config=...))`, never a doomed Pulumi launch — then the Automation
    API converges the inline `_define_images` program (one `docker.RemoteImage` per docker-run row, pinned
    to the same Colima socket the infra stack uses). The preflight `Error` is matched here (the sole arm the
    async Pulumi leg cannot fold through `Result.bind`, which is synchronous), and the convergence is awaited
    on the `Ok` leg — exactly the `n8n._status` admission-then-await shape. A fleet with no docker-run server
    converges an empty program (a clean no-op). The verdict rides `McpConfigDetail.result`.

    Args:
        cfg: The validated settings owning the Colima docker socket and the Pulumi project/stack/state dir.

    Returns:
        `Ok(McpConfigDetail(op=CONVERGE, result=...))` carrying the Pulumi result text, or
        `Error(BoundaryFault)` for an absent `docker` binary or a surviving Pulumi convergence fault.
    """
    match await spawn(("docker", "--version"), subject="mcp.converge", retry_class=RetryClass.PROC):
        case Result(tag="error", error=probe_fault):
            return Error(probe_fault)
        case Result(ok=probe) if probe.returncode != 0:
            detail = probe.stderr.decode(errors="replace").strip() or f"exit {probe.returncode}"
            return Error(BoundaryFault(config=("mcp.converge", f"docker unavailable: {detail}")))
    return await _converge_images(cfg)


async def _converge_images(cfg: MaghzSettings) -> RuntimeRail[McpConfigDetail]:
    """Drive the Pulumi Automation API over the inline image program on a `PROC`-guarded worker offload.

    The blocking select-or-create-and-`up` runs in a worker thread, driven through the substrate
    `guarded(RetryClass.PROC, ...)` fused envelope — the one retry+terminal-lift seam every offload leg
    delegates to, so a transient offload flap replays within the `PROC` budget and a surviving escape (a
    typed `pulumi.automation` `CommandError`, an `OSError` flap, or a `BrokenWorkerProcess`) lifts to the
    `BoundaryFault` rail through the one `CLASSIFY` authority, never a hand-composed `guard`-inside-
    `async_boundary` doubled lift nor an inline catch. The `Ok` leg projects the Pulumi
    `UpResult.summary.result` text onto the receipt. The Pulumi host-side import is gated function-locally
    (dual-band law) inside the offloaded thunk, so the runtime core loads without the heavy plugin stack.

    Returns:
        `Ok(McpConfigDetail(op=CONVERGE, result=...))`, or `Error(BoundaryFault)` from the offload fence.
    """

    def _blocking() -> str:
        # The Automation API drives the host-side plugin stack; the import is gated here (dual-band law) so a
        # CONVERGE-free runtime core never pays the heavy load, and the `auto.Stack` type stays out of every
        # signature (a `TYPE_CHECKING`-only return annotation would crash the beartype claw's forward-ref eval).
        from pulumi import automation as auto  # noqa: PLC0415

        state = (cfg.infra.state_dir / "mcp").resolve()
        state.mkdir(parents=True, exist_ok=True)  # the file:// backend cannot open a bucket whose directory does not exist
        opts = auto.LocalWorkspaceOptions(
            project_settings=auto.ProjectSettings(name="maghz-mcp", runtime="python", backend=auto.ProjectBackend(url=f"file://{state}")),
            # Pin the Colima socket and neutralize the leaked machine DOCKER_CERT_PATH/DOCKER_TLS_VERIFY (which
            # would point the docker provider at a nonexistent TLS cert dir), matching the infra runner setup.
            env_vars={"PULUMI_CONFIG_PASSPHRASE": "", "DOCKER_HOST": cfg.infra.docker_host, "DOCKER_CERT_PATH": "", "DOCKER_TLS_VERIFY": ""},
        )
        stack = auto.create_or_select_stack(stack_name="images", project_name="maghz-mcp", program=partial(_define_images, cfg), opts=opts)
        return stack.up(on_output=lambda _line: None).summary.result  # select-or-create and `up` both run in the worker thread

    rail = await guarded(RetryClass.PROC, lambda: anyio.to_thread.run_sync(_blocking), subject="mcp.converge")
    return rail.map(lambda result: _detail(McpOp.CONVERGE, result=result))


def _define_images(cfg: MaghzSettings) -> None:
    """Declare one `docker.RemoteImage` per docker-run MCP server; the inline Pulumi program CONVERGE runs.

    Folds over `_SERVER_TABLE` for every `ServerSpec.is_docker` row, declaring its image as desired-state
    pinned to the Colima socket the infra stack uses, so a `pulumi up` pulls any absent image and a present
    one is a clean no-op. The heavy `pulumi`/`pulumi_docker` imports are function-local (dual-band law) so
    the runtime core loads without the host-side plugin stack; this body runs only inside the offload worker
    that `_converge_images` binds the program to. A fleet with no docker-run server declares nothing.
    """
    import pulumi  # noqa: PLC0415 - dual-band: heavy host-side plugin stack, imported only inside the offloaded program
    import pulumi_docker as docker  # noqa: PLC0415

    provider = docker.Provider("colima", host=cfg.infra.docker_host)
    on = pulumi.ResourceOptions(provider=provider)
    for kind in ServerKind:
        spec = _SERVER_TABLE[kind]
        if spec.is_docker:
            image = docker.RemoteImage(f"mcp-{kind.value}", name=spec.image, keep_locally=True, opts=on)
            pulumi.export(f"{kind.value}_image", image.repo_digest)


async def _read_committed() -> RuntimeRail[tuple[bytes, dict[str, object]]]:
    """Read `.mcp.json` and round-trip-decode it, lifting an absent/unreadable/malformed file to the rail.

    The shared read boundary for VALIDATE and DIFF: `anyio.Path.read_bytes` then one `_DECODER.decode`.
    Both faults lift explicitly as `BoundaryFault(boundary=("mcp.validate", str(exc)))` carrying the raw
    provider message — an `OSError` (absent/unreadable) and a `msgspec.DecodeError` (malformed) — so neither
    escapes as a raw traceback. The raw bytes feed VALIDATE's placeholder regex; the decoded object feeds
    DIFF's compare, so the single decode serves both.

    Returns:
        `Ok((raw_bytes, decoded_object))` when the file reads and decodes, or
        `Error(BoundaryFault(boundary="mcp.validate"))`.
    """
    try:
        raw = await anyio.Path(_MCP_JSON_PATH).read_bytes()
        decoded = _DECODER.decode(raw)
    except (OSError, msgspec.DecodeError) as exc:
        return Error(BoundaryFault(boundary=("mcp.validate", str(exc))))
    return Ok((raw, decoded))


def _detail(op: McpOp, *, drift: tuple[str, ...] = (), result: str = "") -> McpConfigDetail:
    """Build the verb receipt: the op, the committed path, and the full enumerated fleet as evidence."""
    servers = tuple(ServerKind)
    return McpConfigDetail(op=op, path=_MCP_JSON_PATH, server_count=len(servers), servers=servers, drift=drift, result=result)


def _workspace_overlay(cfg: MaghzSettings) -> dict[str, str]:
    """The WORKSPACE settings overlay: the canonical credentials-dir key and the conditional OAuth redirect.

    `WORKSPACE_MCP_CREDENTIALS_DIR` is the server's canonical credentials-dir env key, sourced from
    `cfg.integrations.workspace_token_dir`; `GOOGLE_OAUTH_REDIRECT_URI` is emitted only when
    `cfg.integrations.workspace_oauth_redirect_uri` is set. Both are filesystem/URL literals the
    integrations group owns, never secrets — no placeholder, the resolved value is committed.

    Args:
        cfg: The validated settings; `cfg.integrations` owns both values.

    Returns:
        The WORKSPACE-only env overlay folded onto the static `env` by `ServerSpec.environ`.
    """
    redirect = cfg.integrations.workspace_oauth_redirect_uri
    return {
        "WORKSPACE_MCP_CREDENTIALS_DIR": str(cfg.integrations.workspace_token_dir),
        **({"GOOGLE_OAUTH_REDIRECT_URI": redirect} if redirect else {}),
    }


# --- [TABLES] --------------------------------------------------------------------------

# The fleet declaration: `ServerKind` -> `ServerSpec`. Placed after `[MODELS]` because it references the
# `ServerSpec` runtime class (Python overlay law: a runtime table follows the model it builds). Each row is
# the EXCLUSIVE invocation surface for its server; `env`/`docker_env` values are the `${MAGHZ_MCP__*}`
# placeholder literals committed to `.mcp.json` verbatim, except `GOOGLE_OAUTH_*` which emit bare per the
# integrations seam. The N8N row splits the docker run-options (`args`) from the `image` so the `-e` pairs
# splice ahead of the image where Docker requires them, and its non-empty `image` is the one CONVERGE
# materializes. The key set equals `ServerKind` exactly, so direct subscription is total.
_SERVER_TABLE: frozendict[ServerKind, ServerSpec] = frozendict({
    ServerKind.POSTGRES: ServerSpec(
        command="uvx", args=("postgres-mcp", "--access-mode=restricted"), env=frozendict({"DATABASE_URI": "${MAGHZ_MCP__DATABASE_URI}"})
    ),
    ServerKind.N8N: ServerSpec(
        command="docker",
        args=("run", "-i", "--rm", "--init"),
        image="ghcr.io/czlonkowski/n8n-mcp:latest",
        docker_env=frozendict({
            "MCP_MODE": "stdio",
            "LOG_LEVEL": "error",
            "DISABLE_CONSOLE_OUTPUT": "true",
            "N8N_API_URL": "${MAGHZ_MCP__N8N_API_URL}",
            "N8N_API_KEY": "${MAGHZ_MCP__N8N_API_KEY}",
        }),
    ),
    ServerKind.WORKSPACE: ServerSpec(
        command="uvx",
        args=("workspace-mcp", "--tool-tier", "extended"),
        env=frozendict({"GOOGLE_OAUTH_CLIENT_ID": "${GOOGLE_OAUTH_CLIENT_ID}", "GOOGLE_OAUTH_CLIENT_SECRET": "${GOOGLE_OAUTH_CLIENT_SECRET}"}),
    ),
    ServerKind.NOTEBOOKLM: ServerSpec(command="notebooklm-mcp"),
})

# The lone settings-sourced env overlay, keyed by `ServerKind`; an absent key resolves to no overlay
# (`_render` projects an empty map for every kind `.get` misses). Only WORKSPACE overlays the static `env`
# (with filesystem/URL literals the integrations group owns). This is the DERIVED collapse of the former
# per-kind `match` arm into one table row.
_ENV_OVERLAY: frozendict[ServerKind, Callable[[MaghzSettings], dict[str, str]]] = frozendict({ServerKind.WORKSPACE: _workspace_overlay})

# op -> its builder on the typed `RuntimeRail[McpConfigDetail]` rail. The key set equals `McpOp` exactly, so
# `mcp`'s subscription is total — `mcp` runs `await _BUILD[op](cfg)` with no `match`/`assert_never` ceremony
# around an already-exhaustive `frozendict`. Every builder shares one `(cfg) -> Awaitable[rail]` shape so the
# entrypoint dispatches without per-op argument shaping.
_BUILD: frozendict[McpOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[McpConfigDetail]]]] = frozendict({
    McpOp.GENERATE: _generate,
    McpOp.VALIDATE: _validate,
    McpOp.DIFF: _diff,
    McpOp.WATCH: _watch,
    McpOp.CONVERGE: _converge,
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def mcp(op: McpOp, cfg: MaghzSettings) -> Envelope:
    """Run one MCP verb by `op`, self-lowering the closed fault rail to one `completed`/`fault` envelope.

    `_BUILD[op]` selects the builder over the exhaustive table (no `match`/`assert_never` ceremony around an
    already-total `frozendict`); the resulting `RuntimeRail[McpConfigDetail]` projects at this edge to the
    one stdout `Envelope` — the verb's sole egress, no stderr receipt copy beside it. The `Ok` arm carries
    the `McpConfigDetail` in `completed(status, detail, rows=...)` with one `Row(key=kind.value, text=...)`
    per server — `text` the per-server drift verdict for DIFF (`"drift"`/`"ok"`) and a flat `"ok"` for the
    other verbs, `status` `Status.FAILED` on drift else `Status.OK`. The `Error` arm self-lowers through
    `fault(headline(), facts())` — the same projection the CLI `lower` seam performs (and the same
    `_convert` already recorded on the active OTel span at the boundary), so this rail threads through the
    CLI without the shared lowering, exactly the `cloud`/`automation.drive` self-lowering shape.

    Args:
        op: The MCP verb to run; selects its builder from `_BUILD`.
        cfg: The validated settings the render reads.

    Returns:
        One `Envelope`: `Status.OK`/`Status.FAILED` carrying the typed `McpConfigDetail` receipt and
        per-server rows, or a `Status.FAULTED` envelope carrying the boundary fault's `subject: cause` line
        and its structured facts.
    """
    match await _BUILD[op](cfg):
        case Result(tag="ok", ok=detail):
            drifted = frozenset(detail.drift)
            rows = tuple(Row(key=kind.value, text="drift" if kind.value in drifted else "ok") for kind in ServerKind)
            return completed(Status.FAILED if drifted else Status.OK, detail, rows=rows)
        case Result(error=boundary_fault):
            return fault(boundary_fault.headline(), {key: str(value) for key, value in boundary_fault.facts().items()})


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["McpConfigDetail", "McpOp", "ServerKind", "ServerSpec", "mcp"]
