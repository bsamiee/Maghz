"""agy boundary shim — the single modal entrypoint over the Antigravity CLI.

Delegates entirely to the closed-source `agy` Go binary: one synchronous `prompt` op (covers review,
research, summarization, adversarial critique — all are `agy -p`) and the asynchronous `task` lifecycle
(`task`/`status`/`cancel`/`result`). Maps exit code + stderr patterns to a closed `AgyFault` vocabulary onto
the one `Result[AgyReceipt, AgyFail]` rail chosen at the spawn boundary and carried through the match, then
folds that rail to the `AgyReceipt`/`AgyFail` egress pair encoded to stdout. The spawn fence composes the
canonical `guard(RetryClass.PROC)` resilience owner (transient `OSError` flaps retried under the runtime
`POLICY[PROC]` schedule) inside the outer `anyio.move_on_after(agy_process_timeout_s)` deadline; the surviving
escape and the non-zero exit are classified to `AgyFault`, never re-deriving the retry locally. Run via
`uv run -m`; it imports `admin.runtime`/`admin.settings`, so it is not a standalone `--script`.
"""

from collections.abc import Sequence
import functools
import sys
from types import MappingProxyType
from typing import assert_never, Literal

import anyio
from expression import Error, Nothing, Ok, Option, Result, Some
import msgspec

from admin.runtime import guard, RetryClass
from admin.settings import settings


# --- [TYPES] ---------------------------------------------------------------------------

type AgyOp = Literal["prompt", "task", "status", "cancel", "result"]
type AgyFault = Literal["binary_not_found", "auth_required", "quota_exceeded", "process_error"]


# --- [CONSTANTS] -----------------------------------------------------------------------

_TIER: MappingProxyType[str, str] = MappingProxyType(
    {
        "pro": "gemini-3-pro",
        "flash": "gemini-3-flash",
        "nano": "gemini-3-nano",
    }
)


# --- [MODELS] --------------------------------------------------------------------------


class AgyReceipt(msgspec.Struct, frozen=True, gc=False):
    """Success arm: prompt output text and/or task identifier, each absent for ops that do not carry it."""

    op: AgyOp
    output: Option[str]
    task_id: Option[str]


class AgyFail(msgspec.Struct, frozen=True, gc=False):
    """Fault arm: the closed fault discriminant plus the raw stderr/exception detail, never optional."""

    op: AgyOp
    fault: AgyFault
    detail: str


# --- [BOUNDARIES] ----------------------------------------------------------------------


def _egress(outcome: AgyReceipt | AgyFail) -> bytes:
    """Encode the egress arm to stdout JSON, collapsing each `Option[str]` field to msgspec-native `str | None`.

    The struct fields are lifted to a plain `dict` through `msgspec.structs.asdict` and each `Option[str]`
    is projected to its `str | None` payload before `msgspec.json.encode`. msgspec cannot introspect an
    `expression.Option[str]` struct-field type (the generic alias has no `__parameters__`), so neither a
    typed `Encoder` over the struct nor a `dec_hook`-equipped `Decoder(type=AgyReceipt)` can be built —
    the dict projection is the one viable egress, and the consumer decodes the wire as `str | None` and
    lifts to `Option` on its own side. The struct type still distinguishes the arm by presence of `fault`.

    Returns:
        The egress JSON bytes with `Option[str]` fields collapsed to `str | None`.
    """
    fields = {name: value.default_value(None) if isinstance(value, Option) else value for name, value in msgspec.structs.asdict(outcome).items()}
    return msgspec.json.encode(fields)


# --- [OPERATIONS] ----------------------------------------------------------------------


def _classify(returncode: int, stderr: str) -> AgyFault:
    """Map a non-zero exit + stderr pattern to the closed fault vocabulary; everything else is transient."""
    lowered = stderr.lower()
    match returncode:
        case 1 if "auth" in lowered or "login" in lowered or "unauthorized" in lowered:
            return "auth_required"
        case 2 if "quota" in lowered or "rate limit" in lowered or "exhausted" in lowered:
            return "quota_exceeded"
        case _:
            return "process_error"


def _receipt(op: AgyOp, stdout: str) -> AgyReceipt:
    """Distribute stdout into the typed optionals by op: prompt carries output, task ops carry a task id."""
    match op:
        case "prompt":
            return AgyReceipt(op=op, output=Some(stdout), task_id=Nothing)
        case "task" | "status":
            return AgyReceipt(op=op, output=Nothing, task_id=Some(stdout))
        case "result":
            return AgyReceipt(op=op, output=Some(stdout), task_id=Nothing)
        case "cancel":
            return AgyReceipt(op=op, output=Nothing, task_id=Nothing)
        case _:
            assert_never(op)


def _command(op: AgyOp, args: Sequence[str]) -> Sequence[str]:
    """Build the `agy` argv for the op, resolving `--model <tier>` aliases against the `_TIER` table."""
    binary = str(settings().integrations.agy_binary)
    match op:
        case "prompt":
            head, rest = (args[0], args[1:]) if args else ("", ())
            tier = next((_TIER.get(rest[idx + 1], rest[idx + 1]) for idx, tok in enumerate(rest) if tok == "--model" and idx + 1 < len(rest)), None)
            return [binary, "-p", head, *(("--model", tier) if tier else ())]
        case "task":
            return [binary, "task", "create", *args]
        case "status" | "result" | "cancel":
            return [binary, "task", op, *args]
        case _:
            assert_never(op)


async def _invoke(op: AgyOp, cmd: Sequence[str]) -> Result[AgyReceipt, AgyFail]:
    """Run the binary under the deadline scope and grade the outcome onto the `Result` rail.

    The spawn composes the canonical `guard(RetryClass.PROC)` resilience owner — transient `OSError`
    spawn flaps retry under the runtime `POLICY[PROC]` schedule — inside the outer
    `anyio.move_on_after(agy_process_timeout_s)` deadline (deadline outermost, retry within, raw spawn
    innermost), so no transient predicate or retry decorator is re-derived here. The rail is chosen
    once: a missing binary (terminal `FileNotFoundError`, surfaced after the retry budget exhausts the
    deterministic spawn failure), a tripped deadline, and a non-zero exit each lift to
    `Error(AgyFail(...))`; a clean exit lifts to `Ok(_receipt(...))`. The caller folds the rail to the
    egress pair, so no arm is re-projected mid-pipeline.

    Returns:
        `Ok(AgyReceipt)` on a clean exit, or `Error(AgyFail)` carrying the closed fault and its detail.
    """
    try:
        with anyio.move_on_after(settings().integrations.agy_process_timeout_s) as scope:
            completed = await guard(RetryClass.PROC)(anyio.run_process, cmd, check=False)
    except FileNotFoundError as exc:
        return Error(AgyFail(op=op, fault="binary_not_found", detail=str(exc)))
    if scope.cancelled_caught:
        return Error(AgyFail(op=op, fault="process_error", detail="agy call exceeded agy_process_timeout_s budget"))
    stdout = completed.stdout.decode(errors="replace").strip()
    stderr = completed.stderr.decode(errors="replace").strip()
    if completed.returncode != 0:
        return Error(AgyFail(op=op, fault=_classify(completed.returncode, stderr), detail=stderr or stdout))
    return Ok(_receipt(op, stdout))


async def agy(op: AgyOp, *, args: Sequence[str]) -> None:
    """The one modal entrypoint: invoke the op, fold the `Result` rail, encode the arm to stdout."""
    match await _invoke(op, _command(op, args)):
        case Result(tag="ok", ok=receipt):
            outcome: AgyReceipt | AgyFail = receipt
        case Result(error=fail):
            outcome = fail
    sys.stdout.buffer.write(_egress(outcome))
    sys.stdout.buffer.write(b"\n")


# --- [COMPOSITION] ---------------------------------------------------------------------


def main() -> int:
    """CLI boundary: parse `<op> <args...>` and drive the modal entrypoint via anyio.run."""
    match sys.argv[1:]:
        case ["prompt" | "task" | "status" | "cancel" | "result" as op, *rest]:
            anyio.run(functools.partial(agy, op, args=rest))
            return 0
        case _:
            sys.stderr.write(__doc__ or "")
            sys.stderr.write("\nusage: agy.py <prompt|task|status|cancel|result> <args...>\n")
            return 1


if __name__ == "__main__":
    sys.exit(main())
