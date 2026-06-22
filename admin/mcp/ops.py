"""MCP-as-IaC operations: render the server fleet to `.mcp.json` and round-trip-validate it.

`admin/mcp/` is the typed source of truth for the MCP server fleet; the committed `.mcp.json` is
the generated artifact. `_render` folds `_SERVER_TABLE` into the wire `mcpServers` object — one
total `match` over `ServerKind` projects each row, the WORKSPACE arm overlaying the two
filesystem-literal values the integrations group owns (`TOKEN_DIR`, conditional `OAUTH_REDIRECT_URI`).
Every secret-bearing key emits a `${VAR}` placeholder, never a resolved value: secrets inject at the
process boundary via `op run -- claude` and are never written to the file. `_write` formats and writes
the JSON through `anyio.Path`; `_validate` reads it back, decodes it for schema integrity, and asserts
every `${MAGHZ_MCP__*}` placeholder has a backing `McpServerSettings` field (the two bare
`${GOOGLE_OAUTH_*}` keys are exempt — they inject bare at the boundary).

All three transforms ride one closed `McpFault` rail carrying the raw provider message; the single
polymorphic `mcp(op, cfg)` entrypoint matches `McpOp`, folds an `Ok` to `completed(...)` and an
`Error` through `McpFault.envelope(op)` — the fault carrier owns its own projection — and emits the
`mcp.report` success / `mcp.fault` failure telemetry, both discriminated by an `op=op.value` field.
No retry and no `admin/runtime/` resilience owner applies — the surface is local-filesystem only, with
no transient remote boundary; `admin.core` is the sole runtime substrate `mcp()` folds into.
"""

import re
from typing import assert_never, Literal

import anyio
from expression import case, Error, Ok, Result, tag, tagged_union
import msgspec
import structlog

from admin.core import completed, Envelope, fault, Row, Status
from admin.mcp.model import _SERVER_TABLE, McpConfigDetail, McpOp, ServerKind, ServerSpec
from admin.settings import MaghzSettings, McpServerSettings


# --- [ERRORS] --------------------------------------------------------------------------


@tagged_union(frozen=True)
class McpFault:
    """The closed MCP fault union: one owner, three cases, each carrying the raw provider message.

    `render` lifts a fleet-projection failure (a placeholder whose backing field is missing), `write`
    lifts the raw `OSError` string from the `anyio.Path.write_bytes` boundary, and `validate` lifts
    either the raw `msgspec.DecodeError` string from the round-trip decode or the placeholder-coverage
    breach. Each `case` carries the original message verbatim — never a re-phrased template — so the
    cause survives to the `envelope` projection where `match self.tag` closes on `assert_never`.
    """

    tag: Literal["render", "write", "validate"] = tag()
    render: str = case()
    write: str = case()
    validate: str = case()

    def envelope(self, op: McpOp) -> Envelope:
        """Project this fault to a `fault` envelope, lifting the raw case message and the boundary tag.

        The single total `match self.tag` (closed by `assert_never`) selects the carried message; the
        fault carrier owns its own projection so `mcp()` folds `Error` to one envelope without a free
        projection function. The boundary tag and the originating `op` ride the error context so an
        agent reads which transform broke from the envelope alone.

        Args:
            op: The verb whose run produced this fault; stamped into the error context.

        Returns:
            A `Status.FAULTED` `Envelope` carrying the raw provider message and the `{boundary, op}`
            context.
        """
        match self.tag:
            case "render":
                message = self.render
            case "write":
                message = self.write
            case "validate":
                message = self.validate
            case _ as unreachable:  # pragma: no cover
                assert_never(unreachable)
        log.error("mcp.fault", op=op.value, boundary=self.tag, detail=message)
        return fault(message, {"boundary": self.tag, "op": op.value})


# --- [SERVICES] ------------------------------------------------------------------------

# One process-wide JSON encoder/decoder pair reused across every invocation; constructing a fresh
# codec per call re-resolves the schema, so the shared instances own the wire. The decoder is typed
# `dict[str, object]` so `_validate` round-trips the committed file as a plain JSON object for schema
# integrity without binding it to a struct shape (a future `AUDIT` op reads the typed receipt instead).
_ENCODER = msgspec.json.Encoder()
_DECODER = msgspec.json.Decoder(type=dict[str, object])

# The structlog handle (a lazy proxy resolved on first call) drives the two egress events, each
# carrying an `op=op.value` discriminant: the entrypoint emits `mcp.report` after a successful rail
# collapse, and `McpFault.envelope` emits `mcp.fault` as it projects a failed rail to the fault envelope.
log = structlog.get_logger()

# The committed artifact path, relative to the repository root the operator runs from. `.mcp.json`
# travels to the VPS unchanged; the `${VAR}` placeholders resolve from that host's process environment.
_MCP_JSON_PATH = ".mcp.json"

# The `McpServerSettings` field set that backs every `${MAGHZ_MCP__<KEY>}` placeholder; `_validate`
# lower-cases each captured key and asserts membership here, so a placeholder whose backing field a
# refactor drops surfaces as a coverage breach. Read off the settings group type, never an instance,
# because `_validate(path)` takes no `cfg` — the backing surface is static, the resolved values are not.
_MCP_FIELDS = frozenset(McpServerSettings.model_fields)

# Every `${MAGHZ_MCP__<KEY>}` occurrence in the rendered file; the captured `<KEY>` lower-cases to a
# `McpServerSettings` field name the coverage check asserts is present. The two bare `${GOOGLE_OAUTH_*}`
# placeholders carry no `MAGHZ_MCP__` prefix, so this pattern never matches them — they are exempt by
# construction, injected bare at the process boundary by `setup-env.sh`.
_PLACEHOLDER = re.compile(r"\$\{MAGHZ_MCP__([A-Z0-9_]+)\}")


# --- [OPERATIONS] ----------------------------------------------------------------------


def _render(cfg: MaghzSettings) -> Result[dict[str, object], McpFault]:
    """Fold `_SERVER_TABLE` into the wire `mcpServers` object, emitting `${VAR}` placeholders only.

    One total `match` over `ServerKind` (closed by `assert_never`) projects each row to its
    `{command, args, env}` JSON shape. `docker_env` pairs fold into the rendered `args` as
    `("-e", "KEY=VAL")` for the Docker-invoked server; the WORKSPACE arm overlays the two
    filesystem-literal values the integrations group owns — `WORKSPACE_MCP_CREDENTIALS_DIR` (the
    server's canonical credentials-dir env key) from `cfg.integrations.workspace_token_dir`, and a
    conditional `GOOGLE_OAUTH_REDIRECT_URI` emitted only when
    `cfg.integrations.workspace_oauth_redirect_uri` is non-`None`. No `SecretStr.get_secret_value()`
    is called: secret-bearing keys emit their `${MAGHZ_MCP__*}` / bare `${GOOGLE_OAUTH_*}` placeholder
    literals from the table, so the file never carries a resolved secret.

    Args:
        cfg: The validated settings; `cfg.integrations` owns the literal workspace credentials-dir and
            the conditional OAuth redirect URI the WORKSPACE arm overlays.

    Returns:
        `Ok({"mcpServers": {...}})` carrying one entry per `ServerKind` in declaration order.
    """
    servers: dict[str, object] = {}
    for kind in ServerKind:
        spec: ServerSpec = _SERVER_TABLE[kind]
        args = (*spec.args, *(arg for key, value in spec.docker_env.items() for arg in ("-e", f"{key}={value}")))
        match kind:
            case ServerKind.WORKSPACE:
                env = {
                    **spec.env,
                    "WORKSPACE_MCP_CREDENTIALS_DIR": str(cfg.integrations.workspace_token_dir),
                    **({"GOOGLE_OAUTH_REDIRECT_URI": redirect} if (redirect := cfg.integrations.workspace_oauth_redirect_uri) is not None else {}),
                }
            case ServerKind.POSTGRES | ServerKind.N8N | ServerKind.EXA | ServerKind.PERPLEXITY | ServerKind.TAVILY | ServerKind.NOTEBOOKLM:
                env = dict(spec.env)
            case _ as unreachable:  # pragma: no cover
                assert_never(unreachable)
        servers[kind.value] = {"command": spec.command, "args": list(args), "env": env}
    return Ok({"mcpServers": servers})


async def _write(fleet: dict[str, object], path: str) -> Result[McpConfigDetail, McpFault]:
    """Format the rendered fleet and write it to `path`, lifting an `OSError` onto the fault rail.

    `msgspec.json.format(ENCODER.encode(fleet), indent=2)` produces the human-readable bytes the
    committed git artifact needs; `anyio.Path(path).write_bytes` performs the async write. An `OSError`
    from the filesystem boundary (disk full, permission denied) lifts as `McpFault(write=str(exc))`
    carrying the raw message — it never escapes to the CLI meta handler as a raw traceback.

    Args:
        fleet: The `{"mcpServers": {...}}` object `_render` produced.
        path: The destination artifact path.

    Returns:
        `Ok(McpConfigDetail)` carrying the generate receipt (path, server count, enumerated kinds), or
        `Error(McpFault(write=...))` when the write boundary raises.
    """
    payload = msgspec.json.format(_ENCODER.encode(fleet), indent=2)
    servers = tuple(ServerKind)
    try:
        await anyio.Path(path).write_bytes(payload)
    except OSError as exc:
        return Error(McpFault(write=str(exc)))
    return Ok(McpConfigDetail(op=McpOp.GENERATE, path=path, server_count=len(servers), servers=servers))


async def _validate(path: str) -> Result[McpConfigDetail, McpFault]:
    """Read `path` back, decode it for schema integrity, and assert every placeholder has a backing field.

    `anyio.Path(path).read_bytes` reads the committed artifact; `DECODER.decode` round-trips it as a
    plain JSON object. The validate boundary catches both its faults explicitly as `McpFault(validate=...)`
    carrying the raw provider message — an `OSError` (the file is absent or unreadable, e.g. validate
    before generate) and a `msgspec.DecodeError` (the file is malformed) — so neither escapes to the CLI
    meta handler as a raw traceback. The coverage check then scans every `${MAGHZ_MCP__<KEY>}` occurrence
    and confirms the lower-cased `<KEY>` is a field on `McpServerSettings` — a missing backing field is
    the seam breach the acceptance gate forbids. The two bare `${GOOGLE_OAUTH_*}` placeholders never
    match the `MAGHZ_MCP__` pattern, so they are exempt by construction.

    Args:
        path: The committed artifact to round-trip and coverage-check.

    Returns:
        `Ok(McpConfigDetail)` carrying the validate receipt when the file reads, decodes, and every
        `MAGHZ_MCP__*` placeholder is backed, or `Error(McpFault(validate=...))` for an absent/unreadable
        file, a decode failure, or an unbacked placeholder.
    """
    servers = tuple(ServerKind)
    try:
        raw = await anyio.Path(path).read_bytes()
        _DECODER.decode(raw)
    except (OSError, msgspec.DecodeError) as exc:
        return Error(McpFault(validate=str(exc)))
    unbacked = frozenset(match.group(0) for match in _PLACEHOLDER.finditer(raw.decode(errors="replace")) if match.group(1).lower() not in _MCP_FIELDS)
    if unbacked:
        return Error(McpFault(validate=f"placeholders without a McpServerSettings field: {', '.join(sorted(unbacked))}"))
    return Ok(McpConfigDetail(op=McpOp.VALIDATE, path=path, server_count=len(servers), servers=servers))


async def _generate(cfg: MaghzSettings) -> Result[McpConfigDetail, McpFault]:
    """Sequence the sync render then the async write, binding the result across the async boundary by `match`.

    `_render` is a pure sync fold returning `Result`; `_write` is async. The `effect.result` builder
    uses the synchronous generator-coroutine protocol and cannot `await`, so the bind is an explicit
    `match` — `Ok(fleet)` flows into `await _write`, an `Error` re-lifts its carried `McpFault` through
    a fresh `Error(cause)` (the covariant success type makes the render `Result[dict[str, object], ...]`
    unassignable to this `Result[McpConfigDetail, ...]`, so the fault is rebound, never the carrier).
    No single builder spans both steps.

    Args:
        cfg: The validated settings the render reads.

    Returns:
        The `_write` receipt on a successful render, or the render fault propagated unchanged.
    """
    match _render(cfg):
        case Result(tag="ok", ok=fleet):
            return await _write(fleet, _MCP_JSON_PATH)
        case Result(error=cause):
            return Error(cause)


# --- [ENTRY] ---------------------------------------------------------------------------


async def mcp(op: McpOp, cfg: MaghzSettings) -> Envelope:
    """Run one MCP verb by `op`, folding the closed fault rail to a single `completed`/`fault` envelope.

    `match op` (closed by `assert_never`) dispatches to `_generate` (render then write) or `_validate`
    (round-trip then coverage); the resulting `Result[McpConfigDetail, McpFault]` folds at the boundary:
    an `Ok` becomes `completed(Status.OK, detail, rows=...)` with one `Row(key=kind.value, text="ok")`
    per server, and an `Error` folds through `McpFault.envelope(op)` — the fault carrier owns its own
    projection, lifting the raw provider message and the `{boundary, op}` context. The two egress events
    emit after collapse — `mcp.report` on success, `mcp.fault` inside the fault projection on failure,
    both discriminated by `op=op.value` — the sole cross-cutting concern, so no `@aspect` factory is
    warranted.

    Args:
        op: The MCP verb to run; selects the render-write or round-trip-validate path.
        cfg: The validated settings the render reads.

    Returns:
        One `Envelope`: `Status.OK` carrying the typed `McpConfigDetail` receipt and per-server rows, or
        a `Status.FAULTED` envelope carrying the raw provider message and the originating fault tag.
    """
    match op:
        case McpOp.GENERATE:
            outcome = await _generate(cfg)
        case McpOp.VALIDATE:
            outcome = await _validate(_MCP_JSON_PATH)
        case _ as unreachable:  # pragma: no cover
            assert_never(unreachable)
    match outcome:
        case Result(tag="ok", ok=detail):
            rows = tuple(Row(key=kind.value, text="ok") for kind in ServerKind)
            log.info("mcp.report", op=op.value, path=detail.path, server_count=detail.server_count)
            return completed(Status.OK, detail, rows=rows)
        case Result(error=cause):
            return cause.envelope(op)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["McpFault", "mcp"]
