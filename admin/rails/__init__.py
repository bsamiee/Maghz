"""Rails package: the one mount surface `admin/__main__.py` binds onto the `maghz` CLI.

Each rail owns one bounded concern under one polymorphic entrypoint and one semantic alias:
`ledger` is the polymorphic ledger read over `Kind`, `cloud`/`mcp`/`n8n`/`schema`/`stack`/`sync` are
the verb dispatchers over `CloudOp`/`McpOp`/`N8nOp`/`SchemaOp`/`StackOp`/the `concept`-presence
discriminant, and `drive` is the single polymorphic automation entrypoint that selects its Watch /
Schedule / Manual lane off the `AutomationSpec.trigger` discriminant. `ledger`, `schema`, `stack`, and
`sync` return the domain-internal `RuntimeRail[Envelope]`
(`Result[Envelope, BoundaryFault]`) that the CLI `project` handler lowers to the stdout `Envelope`
once, at the edge; `cloud` lifts its own `Result[CloudSyncDetail, CloudFault]` to `Envelope` at its
`completed`/`fault` boundary and `mcp` lifts its own `Result[McpConfigDetail, McpFault]` likewise, so
both thread straight through without that lowering. `n8n` returns the lifted `Envelope` directly: its
`run` lifts its own `Result[N8nDetail, N8nFault]` rail (the `_exec` exit grade plus the STATUS
transport escape) to `completed`/`fault` itself, threading through unchanged. `drive`
likewise returns the lifted `Envelope` directly: it projects its closed `AutomationFault` vocabulary to
`completed`/`fault` once at the boundary via its own `_fault_envelope`, threading through unchanged. The
`CloudOp`/`Kind`/`McpOp`/`N8nOp`/`SchemaOp`/`StackOp` vocabularies are re-exported so the CLI types each
verb parameter. The stack verb lives in `admin.infra.runner` and the `mcp` verb and its `McpOp`
vocabulary mount from the canonical `admin.mcp` package surface; both are re-exported here so every rail
mounts from this single surface. `cloud` drives `rclone` off-site backup/restore under the distinct
`cloud` namespace, never colliding with `sync` (Heptabase card reconciliation); `mcp`
generates/round-trip-validates the committed `.mcp.json` MCP-server-fleet artifact, a static-config
cycle distinct from every DB/Pulumi/Heptabase rail; `n8n` drives `docker exec`
workflow export/import plus `/healthz` liveness over the Pulumi-managed automation container.
"""

from admin.automation.engine import drive
from admin.infra.runner import run as stack, StackOp
from admin.mcp import mcp, McpOp
from admin.rails.cloud import CloudOp, run as cloud
from admin.rails.ledger import Kind, query as ledger
from admin.rails.n8n import N8nOp, run as n8n
from admin.rails.schema import run as schema, SchemaOp
from admin.rails.sync import run as sync


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["CloudOp", "Kind", "McpOp", "N8nOp", "SchemaOp", "StackOp", "cloud", "drive", "ledger", "mcp", "n8n", "schema", "stack", "sync"]
