"""MCP fleet wire vocabulary: the server discriminant, the op discriminant, the spec record, the receipt, the table.

Every type that crosses an `admin/mcp/` module boundary lives here. `ServerKind` is the closed
fleet vocabulary; `McpOp` is the entrypoint modal discriminant. `ServerSpec` is the per-server wire
record — `command`, `args`, the top-level `env` map, and the Docker `docker_env` map folded into
`-e KEY=VAL` pairs by `_render`. `McpConfigDetail` extends the envelope `Detail` base with `tag=True`
so the report stays one shape and carries the rendered `ServerKind` members (precisely typed in
memory, encoded to their `.value` keys on the wire) as load-bearing evidence. `_SERVER_TABLE` is the
`ServerKind` -> `ServerSpec` correspondence; it lives in `[TABLES]`
after `[MODELS]` because it references the `ServerSpec` runtime class, and the env/docker_env values
carry `${MAGHZ_MCP__*}` placeholder literals (with the two bare `${GOOGLE_OAUTH_*}` keys per the
integrations seam) that resolve at the `op run` process boundary, never at generate time. Adding a
server is one `ServerKind` case plus one `_SERVER_TABLE` row; every consumer closes via `match` /
`assert_never`. No operations and no fault rail live here — those are `ops.py`.
"""

from enum import StrEnum

from frozendict import frozendict
import msgspec

from admin.core.model import Detail


# --- [TYPES] ---------------------------------------------------------------------------


class ServerKind(StrEnum):
    """The closed MCP server fleet; one member per `.mcp.json` server, value is the JSON key.

    `_render`'s row-to-JSON projection matches over this enum and closes with `assert_never`, so a
    new server lands as one case here plus one `_SERVER_TABLE` row with no branch proliferation. The
    member value is the `mcpServers` object key and the wire encoding of each `McpConfigDetail.servers`
    member, which stays a typed `ServerKind` in memory.
    """

    POSTGRES = "postgres"
    N8N = "n8n"
    EXA = "exa"
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    WORKSPACE = "workspace"
    NOTEBOOKLM = "notebooklm"


class McpOp(StrEnum):
    """The `maghz mcp` modal discriminant; the single `mcp(op, cfg)` entrypoint matches and dispatches.

    `GENERATE` runs `_render` -> `_write`; `VALIDATE` runs `_validate`. A future `DIFF`/`AUDIT` op is
    one new member dispatched from the same entrypoint — never a sibling function or module.
    """

    GENERATE = "generate"
    VALIDATE = "validate"


# --- [MODELS] --------------------------------------------------------------------------


class ServerSpec(msgspec.Struct, frozen=True, gc=False):
    """The per-server invocation shape: launch `command`, its `args`, and the two env maps.

    `env` is the top-level Claude Code `env` object; `docker_env` carries the Docker `-e KEY=VAL`
    pairs `_render` folds into `args` for the Docker invocation, empty for every non-Docker server.
    Both maps are `frozendict[str, str]` per the immutable-map policy; values are `${MAGHZ_MCP__*}`
    (or bare `${GOOGLE_OAUTH_*}`) placeholder literals resolved at the process boundary. `gc=False`
    is load-bearing: only `str` and `frozendict` fields, no reference cycles, so GC tracking is waste.
    """

    command: str
    args: tuple[str, ...]
    env: frozendict[str, str] = frozendict()
    docker_env: frozendict[str, str] = frozendict()


class McpConfigDetail(Detail, frozen=True, tag=True):
    """The single typed receipt `mcp()` emits; rides inside `report.detail`.

    `op` distinguishes the generate path from the validate path; `path` is the filesystem artifact;
    `server_count` is the machine-verifiable fleet size; `servers` carries the rendered `ServerKind`
    members as load-bearing evidence so an agent enumerates the fleet without re-reading the source —
    each member encodes to its `.value` key on the wire and decodes back to the closed enum, so the
    evidence is precisely typed in memory yet byte-identical in JSON. Every field is load-bearing —
    this receipt never degrades to a generic envelope.
    """

    op: McpOp
    path: str
    server_count: int
    servers: tuple[ServerKind, ...]


# --- [TABLES] --------------------------------------------------------------------------

# The fleet declaration: `ServerKind` -> `ServerSpec`. Placed after `[MODELS]` because it references
# the `ServerSpec` runtime class (Python overlay law: a runtime table follows the model it builds).
# Each row is the EXCLUSIVE invocation surface for its server; `env`/`docker_env` values are the
# `${MAGHZ_MCP__*}` placeholder literals committed to `.mcp.json` verbatim, except `GOOGLE_OAUTH_*`
# which emit bare per the integrations seam (`setup-env.sh` injection). The key set equals `ServerKind`
# exactly, so direct subscription is total and `_render`'s `assert_never` is unreachable.
# `WORKSPACE_MCP_CREDENTIALS_DIR` (the server's canonical credentials-dir env key) and the conditional
# `GOOGLE_OAUTH_REDIRECT_URI` are settings-sourced (`workspace_token_dir` /
# `workspace_oauth_redirect_uri`), so `_render` injects them onto the WORKSPACE env rather than the
# static table carrying them.
_SERVER_TABLE: frozendict[ServerKind, ServerSpec] = frozendict({
    ServerKind.POSTGRES: ServerSpec(
        command="uvx", args=("postgres-mcp", "--access-mode=restricted"), env=frozendict({"DATABASE_URI": "${MAGHZ_MCP__DATABASE_URI}"})
    ),
    ServerKind.N8N: ServerSpec(
        command="docker",
        args=("run", "-i", "--rm", "--init", "ghcr.io/czlonkowski/n8n-mcp:latest"),
        docker_env=frozendict({
            "MCP_MODE": "stdio",
            "LOG_LEVEL": "error",
            "DISABLE_CONSOLE_OUTPUT": "true",
            "N8N_API_URL": "${MAGHZ_MCP__N8N_API_URL}",
            "N8N_API_KEY": "${MAGHZ_MCP__N8N_API_KEY}",
        }),
    ),
    ServerKind.EXA: ServerSpec(command="npx", args=("-y", "exa-mcp-server"), env=frozendict({"EXA_API_KEY": "${MAGHZ_MCP__EXA_API_KEY}"})),
    ServerKind.PERPLEXITY: ServerSpec(
        command="npx", args=("-y", "perplexity-mcp"), env=frozendict({"PERPLEXITY_API_KEY": "${MAGHZ_MCP__PERPLEXITY_API_KEY}"})
    ),
    ServerKind.TAVILY: ServerSpec(command="npx", args=("-y", "tavily-mcp"), env=frozendict({"TAVILY_API_KEY": "${MAGHZ_MCP__TAVILY_API_KEY}"})),
    ServerKind.WORKSPACE: ServerSpec(
        command="uvx",
        args=("workspace-mcp", "--tool-tier", "extended"),
        env=frozendict({"GOOGLE_OAUTH_CLIENT_ID": "${GOOGLE_OAUTH_CLIENT_ID}", "GOOGLE_OAUTH_CLIENT_SECRET": "${GOOGLE_OAUTH_CLIENT_SECRET}"}),
    ),
    ServerKind.NOTEBOOKLM: ServerSpec(command="notebooklm-mcp", args=()),
})


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = ["McpConfigDetail", "McpOp", "ServerKind", "ServerSpec"]
