"""MCP domain: the typed MCP server fleet and the single polymorphic `mcp` entrypoint.

`ops.py` owns the whole domain — the closed `ServerKind` fleet vocabulary, the `McpOp` modal
discriminant, the `ServerSpec` invocation record, the `McpConfigDetail` typed receipt, and `mcp`: the one
`McpOp`-dispatched entrypoint that renders, writes, round-trip-validates, diffs, watch-regenerates, and
Pulumi-converges the committed `.mcp.json`. There is no per-rail fault carrier — every boundary mints the
one closed `admin.runtime` `BoundaryFault` family directly, and `mcp` self-lowers its interior rail to the
stdout `Envelope` at its own `completed`/`fault` boundary. This package `__init__` is the public domain
surface: it re-exports the closed fleet/op/spec/receipt vocabulary together with the `mcp` entrypoint, so
consumers compose the `admin.mcp` owner under one name instead of reaching into `ops.py`. The
`McpServerSettings` group those placeholder rows resolve against is owned by `admin.settings` and reached
through `settings()`, never re-forwarded here.
"""

from admin.mcp.ops import mcp, McpConfigDetail, McpOp, ServerKind, ServerSpec


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["McpConfigDetail", "McpOp", "ServerKind", "ServerSpec", "mcp"]
