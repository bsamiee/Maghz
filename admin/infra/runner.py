"""Stack runner: one polymorphic verb over converge, tear-down, and preview of the docker stack.

This module owns the Pulumi Automation API dispatch and the `StackOp` lifecycle vocabulary.
A single `run` entrypoint discriminates on a closed `StackOp` and returns the domain-internal
`RuntimeRail[Envelope]`; the CLI handler lowers that rail to the stdout `Envelope` through the
shared `project` seam, so the Pulumi/httpx/OS boundary fault is projected once, at the edge, never
inline. Each op names its converge builder and how its Pulumi result projects into the common
`StackDetail` receipt, so the three verbs are one surface rather than three sibling functions. The
Automation API is blocking, so every verb runs through one `_offload` worker-thread fence; state
lives in a local `file://` backend with an empty passphrase, so no Pulumi Cloud account is touched. `up` runs
`refresh` before `up` to close Pulumi's stopped-container `must_run` gap, then pulls the embed
model into the freshly-started Ollama container so the in-DB `pg_net` embed sweep has a model to
call. The spawn fence routes through the canonical resilience boundary: `guard(RetryClass.PROC)`
retries transient Pulumi offload flaps and `guard(RetryClass.HTTP)` rides the freshly-started
container's connection refusals, while `async_boundary` lifts any surviving escape to the
`BoundaryFault` rail.
"""

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from functools import partial
from typing import assert_never

from anyio.to_thread import run_sync
from expression import Error, Result
from frozendict import frozendict
import httpx
import msgspec
from pulumi import automation as auto

from admin.core import completed, Detail, Envelope, Status
from admin.infra.stack import define
from admin.runtime import async_boundary, guard, RetryClass, RuntimeRail
from admin.settings import MaghzSettings


# --- [TYPES] ---------------------------------------------------------------------------


class StackOp(StrEnum):
    """The closed set of stack verbs `run` discriminates on."""

    UP = "up"
    DOWN = "down"
    STATUS = "status"


# --- [MODELS] --------------------------------------------------------------------------


class StackDetail(Detail, frozen=True, tag="stack"):
    """Converge/destroy/preview receipt: the Pulumi result and embed-pull outcome."""

    op: StackOp
    result: str
    resource_changes: Mapping[str, int]
    model_pulled: bool = False


class _Pull(msgspec.Struct, frozen=True, gc=False):
    """One streamed line of the Ollama `/api/pull` progress response."""

    status: str = ""
    error: str | None = None

    @classmethod
    def parse(cls, line: str) -> _Pull:
        """Decode one progress line; non-JSON noise folds to a no-error empty frame."""
        try:
            return msgspec.json.decode(line.encode(), type=cls) if line else cls()
        except msgspec.DecodeError:
            return cls()


# --- [OPERATIONS] ----------------------------------------------------------------------


def _stack(cfg: MaghzSettings) -> auto.Stack:
    state = cfg.infra.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)  # the file:// backend cannot open a bucket whose directory does not exist
    opts = auto.LocalWorkspaceOptions(
        project_settings=auto.ProjectSettings(name=cfg.infra.project, runtime="python", backend=auto.ProjectBackend(url=f"file://{state}")),
        # DOCKER_CERT_PATH/DOCKER_TLS_VERIFY leak in from the machine env and point the docker provider at
        # a nonexistent TLS cert dir; the Colima socket is plain, so neutralize them alongside the host.
        env_vars={"PULUMI_CONFIG_PASSPHRASE": "", "DOCKER_HOST": cfg.infra.docker_host, "DOCKER_CERT_PATH": "", "DOCKER_TLS_VERIFY": ""},
    )
    return auto.create_or_select_stack(stack_name=cfg.infra.stack, project_name=cfg.infra.project, program=partial(define, cfg), opts=opts)


async def _offload[R](subject: str, blocking: Callable[[auto.Stack], R], cfg: MaghzSettings) -> RuntimeRail[R]:
    """Offload one blocking Pulumi verb to a worker thread on the `PROC` fence, lifting its result to the rail.

    This is the single offload boundary for every Automation API verb: select-or-create the stack,
    run `blocking` against it in a worker thread under `guard(RetryClass.PROC)` (which retries
    transient offload flaps), and lift any surviving escape to the `BoundaryFault` rail through
    `async_boundary`. `up` chains a pull onto the `Ok` leg, while `down`/`status` only project; both
    compose this one fence rather than re-deriving the `run_sync` -> `guard` -> `async_boundary` chain.

    Args:
        subject: The boundary identity stamped into the minted fault's `subject` slot.
        blocking: The blocking Pulumi verb to run against the selected stack on a worker thread.
        cfg: The validated settings driving the Pulumi stack.

    Returns:
        `Ok(R)` carrying the raw Pulumi verb result, or `Error(BoundaryFault)` from the `PROC` fence.
    """

    def _blocking() -> R:
        return blocking(_stack(cfg))  # select-or-create and the verb both run in the worker thread

    async def _offloaded() -> R:
        return await run_sync(_blocking)

    return await async_boundary(subject, lambda: guard(RetryClass.PROC)(_offloaded))


def _changes[K](raw: Mapping[K, int] | None) -> Mapping[str, int]:
    """Normalize a Pulumi op->count map (enum or string keys) to string-keyed counts."""
    return {str(op): count for op, count in (raw or {}).items()}


def _converge(stack: auto.Stack) -> auto.UpResult:
    """The `up` verb: refresh to close the stopped-container `must_run` gap, then converge."""
    stack.refresh()
    return stack.up()


async def _pull_embed_model(cfg: MaghzSettings) -> None:
    """Stream `POST /api/pull` against the container Ollama until the model is resolved.

    The freshly-started Ollama container may briefly refuse connections; the `HTTP` retry budget
    rides over that window at the call site. A typed `error` frame raises an `httpx.HTTPError` to
    abort the stream — a server-reported pull failure, not a transport flap.

    Args:
        cfg: The settings owning the Ollama base URL, model name, and request timeout.

    Raises:
        httpx.HTTPError: When the pull stream reports an error frame.
        httpx.ConnectError: When the container refuses connections (retried under `HTTP`).
        httpx.RemoteProtocolError: When the stream is cut (retried under `HTTP`).
    """
    body = {"model": cfg.ollama.embed_model}
    timeout = httpx.Timeout(cfg.ollama.request_timeout, read=None)  # read=None: a streaming pull has no read deadline
    async with (
        httpx.AsyncClient(base_url=str(cfg.ollama.base_url), timeout=timeout) as client,
        client.stream("POST", "/api/pull", json=body) as response,
    ):
        response.raise_for_status()
        async for line in response.aiter_lines():
            # A non-JSON progress line is benign noise, not an error frame; decode it into a
            # no-error `_Pull` so only a typed `error` field — never malformed bytes — aborts.
            frame = _Pull.parse(line)
            if frame.error:
                raise httpx.HTTPError(frame.error)


async def _up_detail(cfg: MaghzSettings) -> RuntimeRail[Envelope]:
    """Converge the stack under `PROC`, then pull the embed model under `HTTP`, on the rail.

    The Pulumi converge offloads to a worker thread under `guard(RetryClass.PROC)` through the shared
    `_offload` fence; the Ollama pull rides `guard(RetryClass.HTTP)` so a freshly-started container's
    connection refusals converge within the budget. Either fence's surviving escape rides the
    `BoundaryFault` rail to the CLI projection rather than lowering inline. `up` is sequential by
    construction: converge first under `PROC`, then pull under `HTTP` (Ollama must run before the pull).

    Args:
        cfg: The validated settings driving the Pulumi stack and the Ollama reach.

    Returns:
        `Ok(completed(OK))` carrying the converge receipt with `model_pulled`, or
        `Error(BoundaryFault)` from the converge or pull fence.
    """
    match await _offload(StackOp.UP.value, _converge, cfg):
        case Result(tag="ok", ok=result):
            # Converged: the pull rides its own `HTTP` fence and `.map`s the converge receipt onto a
            # success `Envelope`, so a pull fault short-circuits to `Error` while a clean pull stamps
            # `model_pulled=True` over the already-captured converge summary — one lift mirroring
            # `_offload_detail`, with the two-phase `PROC`-then-`HTTP` sequencing preserved.
            changes = _changes(result.summary.resource_changes)
            detail = StackDetail(op=StackOp.UP, result=result.summary.result, resource_changes=changes, model_pulled=True)
            pull = await async_boundary("pull", lambda: guard(RetryClass.HTTP)(_pull_embed_model, cfg))
            return pull.map(lambda _: completed(Status.OK, detail))
        case Result(error=boundary_fault):
            return Error(boundary_fault)


async def _offload_detail[R](
    op: StackOp, verb: Callable[[auto.Stack], R], project: Callable[[R], StackDetail], cfg: MaghzSettings
) -> RuntimeRail[Envelope]:
    """Offload one single-phase Pulumi verb (destroy/preview) under `PROC`, lifting its receipt onto the rail.

    `down` and `status` differ only in the Pulumi method they offload and how their result projects
    to a `StackDetail`; this is the one parametric builder over `(op, verb, project)`. The blocking
    Automation API call runs on the shared `_offload` fence (worker thread under `guard(RetryClass.PROC)`,
    escape lifted by `async_boundary`); the `Ok` leg projects the raw result to its receipt.

    Args:
        op: The verb identity stamped into the boundary subject and the receipt.
        verb: The blocking Pulumi method to offload (`Stack.destroy` / `Stack.preview`).
        project: Maps the offloaded Pulumi result to its `StackDetail` receipt.
        cfg: The validated settings driving the Pulumi stack.

    Returns:
        `Ok(completed(OK))` carrying the projected receipt, or `Error(BoundaryFault)` from the fence.
    """
    return (await _offload(op.value, verb, cfg)).map(lambda result: completed(Status.OK, project(result)))


def _down_project(result: auto.DestroyResult) -> StackDetail:
    """Project a destroy result to its receipt; `down` reads the run `.summary`."""
    return StackDetail(op=StackOp.DOWN, result=result.summary.result, resource_changes=_changes(result.summary.resource_changes))


def _status_project(result: auto.PreviewResult) -> StackDetail:
    """Project a preview result to its receipt; `status` reads the `.change_summary` (no `.summary`)."""
    return StackDetail(op=StackOp.STATUS, result="preview", resource_changes=_changes(result.change_summary))


# --- [TABLES] --------------------------------------------------------------------------


# op -> its converge-and-project builder. The key set equals `StackOp` exactly, so `run`'s
# subscription is total; the `match` arm proves exhaustiveness to the type checker. `up` is the
# distinct two-phase builder (converge then pull); `down`/`status` are data rows over the one
# `_offload_detail` builder, naming only their Pulumi verb and result projection.
_BUILD: frozendict[StackOp, Callable[[MaghzSettings], Awaitable[RuntimeRail[Envelope]]]] = frozendict({
    StackOp.UP: _up_detail,
    StackOp.DOWN: partial(_offload_detail, StackOp.DOWN, auto.Stack.destroy, _down_project),
    StackOp.STATUS: partial(_offload_detail, StackOp.STATUS, auto.Stack.preview, _status_project),
})


# --- [ENTRY] ---------------------------------------------------------------------------


async def run(op: StackOp, cfg: MaghzSettings, /) -> RuntimeRail[Envelope]:
    """Run one stack verb by `op` on the domain rail, dispatching through the `_BUILD` table.

    The returned `RuntimeRail[Envelope]` is the domain-internal contract; the CLI handler lowers
    it to the stdout `Envelope` through the shared `project` seam, so a Pulumi/httpx/OS boundary
    fault is projected once, at the edge.

    Args:
        op: The stack verb to run; selects its converge-and-project builder from `_BUILD`.
        cfg: The validated settings driving the Pulumi stack and Ollama reach.

    Returns:
        The rail the selected builder produced — `Ok(Envelope)` carrying a completed converge,
        destroy, or preview receipt, or `Error(BoundaryFault)` from the boundary fence.
    """
    match op:
        case StackOp.UP | StackOp.DOWN | StackOp.STATUS:
            return await _BUILD[op](cfg)
        case unreachable:
            assert_never(unreachable)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["StackDetail", "StackOp", "run"]
