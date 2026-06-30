"""The `maghz` console entrypoint: cyclopts routing over the operator rails.

cyclopts owns the whole CLI grammar — `App` config, grouped sub-apps, annotated parameters,
the layered `config.Env` source, and result mapping. The async meta dispatcher is the single
pre-dispatch seam: it binds the global `--log-level` / `--log-format` flags once, configures the
one structlog pipeline, binds the resolved command name into the structlog context, then awaits
the matched rail through `App.run_async(backend="asyncio")` — the sole event-loop owner is the
`anyio.run` at `main()`. The meta launcher returns one `Envelope`; `main()` writes exactly one
`encode()` line to stdout and projects `envelope.code` to the exit status. Settings and structlog
resolve at dispatch, not import, so a config fault surfaces as a fault envelope rather than a bare
traceback. The runtime `Signals` service owns the structlog pipeline and `install(RetryMode.EMIT)`
routes boundary-retry receipts onto stderr once at startup. The `stack`, `ledger`, `schema`, `sync`,
`cloud`, `n8n`, and `remote` (`exec`, `deploy`) rails return the domain `RuntimeRail[Envelope]`, so
their handlers lower it to the stdout `Envelope` through the one `runtime.lower` seam — which spreads
a surviving `BoundaryFault` into a `fault` envelope at the single CLI edge. Only `mcp` self-lowers:
`mcp(op, cfg)` grades its internal `RuntimeRail[McpConfigDetail]` to an `Envelope` at its own
`completed`/`fault` boundary, so its handler returns it without that lowering; `mcp` mounts
`generate`/`validate`/`diff`/`watch`/`converge`.
The `remote` commands each derive one `RemoteTarget.from_config(settings().remote)` and await the
`admin.remote.ops` `exec`/`deploy` entrypoint at the SSH/SFTP `async_boundary` edge, with `deploy`
discriminating the run on the `StackOp` verb; `exec` carries `allow_leading_hyphen=True` so a
flag-bearing remote command (`git log --oneline`) forwards verbatim instead of being parsed as CLI
options.
"""

import functools
from importlib.metadata import version
import sys
from typing import Annotated

import anyio
import cyclopts
from cyclopts import App, CycloptsError, Group, Parameter
from pydantic import ValidationError
import structlog

from admin import automation, infra, mcp, rails, remote
from admin.core import Envelope, fault
from admin.runtime import install, lower, RetryMode, Signals
from admin.settings import LogFormat, LogLevel, settings


# --- [CONSTANTS] -----------------------------------------------------------------------

# Command groups: each sub-concern owns one help panel, ordered by operator workflow rather
# than the default alphabetical flattening. `sort_key` is the panel rank; the rail commands
# register into the matching group so `maghz --help` reads as a grouped operator surface.
_STACK = Group("Stack", sort_key=10)
_LEDGER = Group("Ledger", sort_key=20)
_SCHEMA = Group("Schema", sort_key=30)
_SYNC = Group("Sync", sort_key=40)
_N8N = Group("n8n", sort_key=45)
_AUTOMATION = Group("Automation", sort_key=48)
_CLOUD = Group("Cloud", sort_key=50)
_MCP = Group("MCP", sort_key=60)
_REMOTE = Group("Remote", sort_key=70)
_GLOBAL = Group("Global", sort_key=99)


# --- [COMPOSITION] ---------------------------------------------------------------------

app = App(
    name="maghz",
    version=version("maghz"),
    help="Operator for the Maghz second-brain ledger.",
    help_format="markdown",
    version_flags=("--version",),
    help_flags=("--help", "-h"),
    group_commands=Group("Commands", sort_key=0),
    config=[cyclopts.config.Env(prefix="MAGHZ_")],
)
_schema = App(name="schema", help="Apply the declarative schema and assert ledger health.", group=_SCHEMA)
_sync = App(name="sync", help="Reconcile canonical concepts with their Heptabase cards.", group=_SYNC)
_n8n = App(name="n8n", help="Manage n8n automation workflows: export, import, and container liveness.", group=_N8N)
_automation = App(name="automation", help="Drive the trigger/action automation engine: watch, schedule, or one-shot.", group=_AUTOMATION)
_cloud = App(name="cloud", help="Replicate the ledger dump and content tree to the cloud remotes, and restore.", group=_CLOUD)
_mcp = App(name="mcp", help="Generate and round-trip-validate the committed `.mcp.json` MCP-server-fleet artifact.", group=_MCP)
# Each sub-app mounts onto the root once; the verb-bearing command bodies below register through the
# named handle's own `@<app>.command` decorator, so the handles stay bound and registration folds here.
for _subapp in (_schema, _sync, _n8n, _automation, _cloud, _mcp):
    app.command(_subapp)


@app.command(name="up", group=_STACK)
async def _up() -> Envelope:
    """Converge the local docker stack and pull the embedding model."""
    return lower(await infra.run(infra.StackOp.UP, settings()))


@app.command(name="down", group=_STACK)
async def _down() -> Envelope:
    """Tear the local docker stack down, preserving named volumes."""
    return lower(await infra.run(infra.StackOp.DOWN, settings()))


@app.command(name="status", group=_STACK)
async def _status() -> Envelope:
    """Preview the desired-vs-live stack diff without converging."""
    return lower(await infra.run(infra.StackOp.STATUS, settings()))


@app.command(name="ledger", group=_LEDGER)
async def _ledger(kind: Annotated[rails.Kind, Parameter(help="The ledger projection to run.")], /) -> Envelope:
    """Run one ledger projection (coverage | gaps | stale | next | owner)."""
    return lower(await rails.ledger(kind, settings()))


@_schema.command(name="apply")
async def _schema_apply() -> Envelope:
    """Apply the declarative schema, then replay the routine objects and cron registration."""
    return lower(await rails.schema(rails.SchemaOp.APPLY, settings()))


@_schema.command(name="doctor")
async def _schema_doctor() -> Envelope:
    """Probe connectivity and report the installed extension census."""
    return lower(await rails.schema(rails.SchemaOp.DOCTOR, settings()))


@_sync.command(name="diff")
async def _sync_diff() -> Envelope:
    """Report drifted/orphaned cards and cross-check the live Heptabase total."""
    return lower(await rails.sync(settings()))


@_sync.command(name="generate")
async def _sync_generate(concept: Annotated[str, Parameter(help="The canonical concept whose Heptabase card is materialized.")], /) -> Envelope:
    """Materialize a Heptabase note card from one concept's canonical content."""
    # The required positional always carries a present concept, so it threads straight into the
    # modal `concept: str | None` `sync.run` owns; the `diff` command supplies no concept (None).
    return lower(await rails.sync(settings(), concept=concept))


@_n8n.command(name="export")
async def _n8n_export() -> Envelope:
    """Export every n8n workflow to one `<id>.json` per file under the host-mounted workflows tree."""
    # The n8n rail returns the domain `RuntimeRail[Envelope]` (its `N8nDetail` completed/fault-graded at the
    # boundary), which this handler lowers to the stdout `Envelope` through the one `runtime.lower` seam.
    return lower(await rails.n8n(rails.N8nOp.EXPORT, settings()))


@_n8n.command(name="import")
async def _n8n_import() -> Envelope:
    """Import every `<id>.json` workflow from the host-mounted tree into the running container."""
    return lower(await rails.n8n(rails.N8nOp.IMPORT, settings()))


@_n8n.command(name="status")
async def _n8n_status() -> Envelope:
    """Probe the n8n container `/healthz` liveness; a reached non-200 reports `healthy=false`, not a fault."""
    return lower(await rails.n8n(rails.N8nOp.STATUS, settings()))


@_automation.command(name="run")
async def _automation_run(*, spec: Annotated[automation.AutomationSpec, Parameter(converter=automation.decode_spec)]) -> Envelope:
    """Drive one automation spec: the `trigger` discriminant selects the watch/schedule/manual lane.

    `--spec` carries the complete `AutomationSpec` JSON; there is no `watch`/`schedule` verb alias —
    the trigger variant inside the spec selects the lane within `drive`. `decode_spec` is the
    `Parameter(converter=...)` admission boundary cyclopts runs before binding: cyclopts invokes it with
    the `--spec` `Token`, whose `.value` it decodes through the stateful `AutomationSpec` decoder and
    validates `spec.lane` against `cfg.automation.lane_keys`, raising the converter-canonical `ValueError`
    on a `msgspec.DecodeError` or an unknown lane. cyclopts wraps that into a `--spec` `CoercionError`,
    so a malformed or unadmitted spec faults at the CLI edge (exit 2) through `main()`'s `CycloptsError`
    arm instead of reaching the engine. `drive` grades its `BoundaryFault` rail to an `Envelope` at its
    own `completed`/`fault` boundary, so it threads straight through without the `runtime.lower` lowering,
    exactly like the `mcp` rail.

    Returns:
        The single `Envelope` `drive` emits for the resolved trigger lane, lowered at the engine edge.
    """
    return await automation.drive(spec, settings())


@_cloud.command(name="sync")
async def _cloud_sync() -> Envelope:
    """Dump the ledger and bisync the content tree to both cloud remotes."""
    # The cloud rail returns the domain `RuntimeRail[Envelope]` (its `CloudSyncDetail` completed/fault-graded
    # at the boundary), which this handler lowers to the stdout `Envelope` through `runtime.lower`.
    return lower(await rails.cloud(rails.CloudOp.SYNC, settings()))


@_cloud.command(name="restore")
async def _cloud_restore() -> Envelope:
    """Restore the ledger from the latest remote dump and bisync the content tree back."""
    return lower(await rails.cloud(rails.CloudOp.RESTORE, settings()))


@_mcp.command(name="generate")
async def _mcp_generate() -> Envelope:
    """Render the typed server fleet to the committed `.mcp.json` with `${VAR}` placeholders."""
    # The mcp rail lifts its internal `RuntimeRail[McpConfigDetail]` to an `Envelope` at its own
    # `completed`/`fault` boundary, so it threads straight through without the `runtime.lower` lowering.
    return await mcp.mcp(mcp.McpOp.GENERATE, settings())


@_mcp.command(name="validate")
async def _mcp_validate() -> Envelope:
    """Round-trip-decode the committed `.mcp.json` and assert every placeholder backs a settings field."""
    return await mcp.mcp(mcp.McpOp.VALIDATE, settings())


@_mcp.command(name="diff")
async def _mcp_diff() -> Envelope:
    """Render the fleet in memory and report every committed server entry that drifts from it (`failed` on drift)."""
    return await mcp.mcp(mcp.McpOp.DIFF, settings())


@_mcp.command(name="watch")
async def _mcp_watch() -> Envelope:
    """Regenerate `.mcp.json` on every settings/source change until SIGINT; one `watchfiles.awatch` stream."""
    return await mcp.mcp(mcp.McpOp.WATCH, settings())


@_mcp.command(name="converge")
async def _mcp_converge() -> Envelope:
    """Materialize every docker-run MCP server image as Pulumi desired-state so a session never cold-pulls."""
    return await mcp.mcp(mcp.McpOp.CONVERGE, settings())


@app.command(name="exec", group=_REMOTE)
async def _remote_exec(
    *argv: Annotated[str, Parameter(help="The remote command and its arguments, run under the pushed working tree.", allow_leading_hyphen=True)],
) -> Envelope:
    """Run one command on the VPS: push the working tree, execute it, and pull artifacts back."""
    # `allow_leading_hyphen=True` lets the variadic absorb a flag-bearing remote command (`git log
    # --oneline`, `ls -la`) verbatim instead of cyclopts rejecting `-`/`--` tokens as unknown options.
    # `remote.run(RemoteExec)` returns the domain `RuntimeRail[Envelope]` lifted at the SSH/SFTP `async_boundary`
    # edge, so the shared `runtime.lower` seam lowers it to the stdout `Envelope` once, at this CLI edge.
    cfg = settings()
    return lower(await remote.run(remote.RemoteExec(argv), cfg))


@app.command(name="deploy", group=_REMOTE)
async def _remote_deploy(*, op: Annotated[infra.StackOp, Parameter(help="The stack verb to run remotely (up | down | status).")]) -> Envelope:
    """Push the working tree to the VPS, then run the selected remote `maghz` stack verb."""
    # `--op` selects the `StackOp` carried by `RemoteDeploy`; `remote.run` returns the
    # domain `RuntimeRail[Envelope]` lifted at the SSH boundary, so the shared `runtime.lower` seam
    # lowers it to the stdout `Envelope` once, at this CLI edge.
    cfg = settings()
    return lower(await remote.run(remote.RemoteDeploy(op), cfg))


# --- [ENTRY] ---------------------------------------------------------------------------


@app.meta.default
async def _launch(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    log_level: Annotated[LogLevel | None, Parameter(env_var="MAGHZ_LOG__LEVEL", group=_GLOBAL, help="Override the structlog level.")] = None,
    log_format: Annotated[LogFormat | None, Parameter(env_var="MAGHZ_LOG__FORMAT", group=_GLOBAL, help="Override the structlog renderer.")] = None,
) -> Envelope | None:
    """Bind the global flags, configure logging, bind the command context, and dispatch the rail.

    This is the single pre-dispatch seam: the `--log-level` / `--log-format` overrides default
    from the settings observability config, the structlog pipeline is configured once, the
    resolved command name is bound into the structlog context (it propagates across the anyio
    task boundary), then the matched async rail is awaited through `App.run_async` — so the
    coroutine never reaches cyclopts' banned `asyncio.run`, and `main()`'s `anyio.run` is the
    sole loop owner.

    Returns:
        The single `Envelope` the matched rail produced, or `None` when cyclopts handled a
        `--help` / `--version` token itself.
    """
    cfg = settings()
    Signals.configure(log_format or cfg.log.format, level=log_level or cfg.log.level)
    chain, _, _ = app.parse_commands(tokens)
    structlog.contextvars.bind_contextvars(command=" ".join(chain))
    return await app.run_async(tokens, backend="asyncio", result_action="return_value", exit_on_error=False)


def main() -> None:
    """Console entry: dispatch one rail through the meta seam, emit one envelope, set exit code.

    The meta seam runs under the sole `anyio.run` loop; a settings `ValidationError`, a cyclopts
    usage error, or any unexpected boundary exception still collapses to a single fault envelope
    rather than a raw traceback; every path writes exactly one JSON line and exits on `envelope.code`.
    The runtime retry instrumentation is installed once so boundary retries mint receipts on stderr.
    """
    install(RetryMode.EMIT)
    dispatch = functools.partial(app.meta.run_async, result_action="return_value", exit_on_error=False)
    try:
        envelope: Envelope | None = anyio.run(dispatch)
    except ValidationError as exc:
        envelope = fault("settings validation failed", {"errors": exc.json()})
    except CycloptsError as exc:
        envelope = fault(str(exc), {"boundary": "usage"})
    except Exception as exc:  # noqa: BLE001 — process boundary collapses any escape to one fault envelope
        envelope = fault(str(exc), {"boundary": type(exc).__name__})
    if envelope is None:  # cyclopts printed --help/--version itself; there is no envelope to emit
        return
    sys.stdout.buffer.write(envelope.encode())
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()
    sys.exit(envelope.code)


if __name__ == "__main__":
    main()
