"""The `remote` domain surface: VPS `exec` and `deploy` over one scoped asyncssh connection.

Re-exports the canonical public vocabulary: `RemoteOp` (the closed `exec`/`deploy` verb set),
`RemoteTarget` (the derived SSH value object), and the two modal-arity entrypoints `exec` and
`deploy`. The connection lifecycle owner is `admin.remote.connection`; the operation owner is
`admin.remote.ops`. Faults lift through the `admin.runtime` `BoundaryFault` rail — this domain owns no
parallel fault vocabulary and the package adds no logic. The beartype import claw is installed once at
the `admin.*` package root, so every `admin.remote.*` callable is already type-checked at its boundary.
"""

from admin.remote.connection import RemoteTarget
from admin.remote.ops import deploy, exec, RemoteOp


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["RemoteOp", "RemoteTarget", "deploy", "exec"]
