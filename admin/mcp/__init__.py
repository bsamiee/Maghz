"""MCP domain: the typed MCP server fleet and the single polymorphic `mcp` entrypoint.

`model.py` owns the closed `ServerKind` fleet vocabulary, the `McpOp` modal discriminant, the
`ServerSpec` wire record, and the `McpConfigDetail` typed receipt. `ops.py` owns `mcp` — the one
`McpOp`-dispatched entrypoint that renders, writes, and round-trip-validates the committed
`.mcp.json` — and the closed `McpFault` rail. This package `__init__` is the public domain surface:
it re-exports the closed fleet/op/spec/receipt vocabulary together with the `mcp` entrypoint and its
`McpFault` rail, so consumers compose the `admin.mcp` owner under one name instead of reaching into
`model.py`/`ops.py`. The `McpServerSettings` group those placeholder rows resolve against is owned by
`admin.settings` and reached through `settings()`, never re-forwarded here.
"""

from admin.mcp.model import McpConfigDetail, McpOp, ServerKind, ServerSpec
from admin.mcp.ops import mcp, McpFault


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["McpConfigDetail", "McpFault", "McpOp", "ServerKind", "ServerSpec", "mcp"]
