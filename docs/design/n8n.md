# [N8N] — Automation Platform Design Blueprint

n8n is the automation layer of the Maghz operator: it holds durable workflow definitions for every scheduled
and event-driven Maghz task (ledger sync, embed sweeps, content ingestion). It is managed as a Pulumi
resource, git-backed through the native `n8n` Server CLI, and authored through the `czlonkowski/n8n-mcp`
MCP server (invocation declared in `admin/mcp/model.py` `_SERVER_TABLE`, not re-stated here). Its
canonical n8n REST API key is `N8N_API_KEY`, a Phase 0 secret.

---

## [01]-[OWNERS]

| Module | Section | Owns |
| --- | --- | --- |
| `admin/settings/config.py` | `[MODELS]` | `N8nConfig` — a single `BaseModel` nested in `MaghzSettings` as `n8n: N8nConfig`; owns every n8n env knob, port, URL shape, VPS overrides, and `workflows_dir`; `api_url` is a `@computed_field` derived from `host`, `protocol`, and `port` |
| `admin/infra/stack.py` | `[OPERATIONS]` | `define()` — extended with the `n8n` container and volume resource alongside `db` and `ollama`; reads `cfg.n8n.*` directly |
| `admin/rails/n8n.py` | `[TYPES]`, `[MODELS]`, `[OPERATIONS]` | `N8nOp` closed union + `N8nDetail` receipt + `run()` polymorphic entrypoint; owns workflow export, import, and liveness |
| `admin/__main__.py` | `[COMPOSITION]` | `_n8n` sub-app and its three command registrations wired into the root `app` |

No new files beyond `admin/rails/n8n.py`. `N8nConfig` is a new nested block on `MaghzSettings` in
`config.py`. `InfraConfig` gains no n8n fields: all n8n configuration — including docker image tag,
container name, port, and VPS-shape URL fields — lives in `N8nConfig`. The `define()` body reads
`cfg.n8n.*` for every n8n resource. The `_n8n` sub-app in `__main__.py` follows the `_schema` pattern.

---

## [02]-[ADTs]

### `N8nOp` — closed verb set for the `run` entrypoint

```python
class N8nOp(StrEnum):
    EXPORT = "export"   # docker exec n8n export:workflow --all --output /home/node/workflows --separate
    IMPORT = "import"   # docker exec n8n import:workflow --input /home/node/workflows
    STATUS = "status"   # GET /healthz — liveness only
```

`run(op: N8nOp, cfg: MaghzSettings, /) -> Envelope` is the single modal-arity entrypoint. It dispatches
via `_BUILD: Map[N8nOp, Callable[[MaghzSettings], Awaitable[N8nDetail]]]` using `expression.Map`
(the admitted keyed dispatch form for static definition-time tables; `MappingProxyType` is rejected
per table-dispatch law and `frozendict` requires explicit admission). No `export_workflow`/`import_workflow`/`status_workflow`
siblings. `assert_never` terminates the exhaustiveness check if `_BUILD` is ever missing a case.

### `N8nDetail` — typed receipt

```python
class N8nDetail(Detail, frozen=True, tag="n8n"):
    op: N8nOp
    workflow_count: int = 0          # files written (EXPORT) or read (IMPORT); 0 for STATUS
    container: str = ""              # the docker container name actually exec-d; "" for STATUS
    healthy: bool | UnsetType = UNSET  # populated only by STATUS; UNSET for EXPORT/IMPORT
```

`healthy` uses `msgspec.UnsetType` / `msgspec.UNSET` to distinguish "liveness confirmed true/false"
(STATUS op) from "liveness never checked" (EXPORT/IMPORT). `UNSET` encodes on the wire as absent
rather than `null`, which preserves the semantic distinction for downstream agent consumers. No default
`True` for un-probed ops — conflating process exit-0 with container health is a semantic error.

Extends `Detail` with `tag="n8n"`, folds directly into the existing `Envelope` / `completed()` /
`fault()` surface from `admin/core`. No parallel DTO, no generic envelope field.

---

## [03]-[.api SURFACE]

### `pulumi_docker` — `docker.Container` (already admitted)

The existing `stack.py` pattern is the floor. The n8n container follows the same shape as `db` and
`ollama`. The `define()` body reads `cfg.n8n.*` throughout. The `db` container uses
`POSTGRES_HOST_AUTH_METHOD=trust`; n8n therefore connects without a password — no
`DB_POSTGRESDB_PASSWORD` field is injected. The DB host uses the Docker network alias `"db"` (a
stable fact owned by `stack.py`'s `aliases=["db"]`):

```python
n8n_data = docker.Volume("n8n-data", name="n8n-data")

db_container = ...  # already declared above in define()

docker.Container(
    "n8n",
    name=cfg.n8n.container_name,
    image=cfg.n8n.image,
    restart="unless-stopped",
    envs=[
        f"N8N_ENCRYPTION_KEY_FILE={cfg.n8n.encryption_key_file}",
        "DB_TYPE=postgresdb",
        "DB_POSTGRESDB_HOST=db",
        "DB_POSTGRESDB_PORT=5432",
        "DB_POSTGRESDB_DATABASE=n8n",
        "DB_POSTGRESDB_USER=maghz",
        "NODE_ENV=production",
        f"N8N_HOST={cfg.n8n.host}",
        f"N8N_PROTOCOL={cfg.n8n.protocol}",
        f"WEBHOOK_URL={cfg.n8n.webhook_url}",
        f"N8N_PROXY_HOPS={cfg.n8n.proxy_hops}",
        "GENERIC_TIMEZONE=UTC",
    ],
    ports=[docker.ContainerPortArgs(internal=5678, external=cfg.n8n.port, ip="127.0.0.1")] if cfg.n8n.protocol == "http" else [],
    volumes=[
        docker.ContainerVolumeArgs(volume_name=n8n_data.name, container_path="/home/node/.n8n"),
        docker.ContainerVolumeArgs(host_path=str(cfg.n8n.workflows_dir.resolve()), container_path="/home/node/workflows"),
    ],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=["n8n"])],
    healthcheck=docker.ContainerHealthcheckArgs(
        tests=["CMD-SHELL", "wget -qO- http://localhost:5678/healthz || exit 1"],
        interval="15s", timeout="5s", retries=5, start_period="30s",
    ),
    opts=pulumi.ResourceOptions(depends_on=[db_container]),
)
pulumi.export("n8n_url", cfg.n8n.api_url)
```

`N8N_MCP_MANAGED_BY_ENV` / `N8N_MCP_ACCESS_ENABLED` are NOT injected. The built-in n8n MCP server
and `czlonkowski/n8n-mcp` are separate surfaces; the design uses the external `czlonkowski/n8n-mcp`
(declared in `admin/mcp/model.py` `_SERVER_TABLE`). Injecting the built-in server env vars alongside
an external bridge creates an ambiguous MCP surface — omit them.

When `cfg.n8n.protocol == "https"` the port mapping is omitted entirely — the reverse proxy owns the
public port on the `maghz` network. Members used: `docker.Container`, `docker.ContainerPortArgs`,
`docker.ContainerVolumeArgs`, `docker.ContainerNetworksAdvancedArgs`, `docker.ContainerHealthcheckArgs`,
`docker.Volume`, `pulumi.ResourceOptions(depends_on=)`, `pulumi.export`. All already in scope.

### `anyio` — `run_process` for `docker exec`

EXPORT and IMPORT ops exec into the running container via `anyio.run_process(..., check=False)`
(already admitted; `subprocess.run` is banned in `pyproject.toml`). `check=False` is mandatory so the
boundary in `run()` owns exit-code interpretation; a non-zero exit lifts to `fault()` rather than
raising `anyio.ProcessError` uncaught. Workflow files land in the host-mounted `workflows/n8n/`
directory, making them git-trackable without any copy step.

n8n's `export:workflow --all --separate` writes one `<id>.json` file per workflow into
`/home/node/workflows`. The workflow count for EXPORT is derived from the number of JSON files present
after the command completes — `anyio.Path(cfg.n8n.workflows_dir).glob("*.json")` counted via
`sum(1 for _ in ...)` inside `_export_detail`, not from stdout parsing (stdout is user-facing prose,
not machine-parseable). For IMPORT, the count is the number of `*.json` files read from the directory
before the command fires.

```python
# sketch — admin/rails/n8n.py [OPERATIONS]
async def _export_detail(cfg: MaghzSettings) -> N8nDetail:
    result = await anyio.run_process(
        ["docker", "exec", "-u", "node", cfg.n8n.container_name,
         "n8n", "export:workflow", "--all", "--output=/home/node/workflows", "--separate"],
        check=False,
    )
    if result.returncode != 0:
        raise _N8nProcessError(result.returncode, result.stderr.decode())
    count = sum(1 for _ in cfg.n8n.workflows_dir.glob("*.json"))
    return N8nDetail(op=N8nOp.EXPORT, workflow_count=count, container=cfg.n8n.container_name)
```

`_N8nProcessError` is a private exception raised inside the builder and caught at the single
`try/except` boundary in `run()`. It carries the exit code and stderr for the fault message. It is
not a public type.

Members used: `anyio.run_process` (from `anyio`, already admitted). The implement pass must verify
the exact `anyio.run_process` signature (args, env, cwd, check, stdout, stderr capture) against the
admitted `anyio>=4.14.0` catalog at `libs/python/.api/anyio.md` before writing bodies.

### `httpx` — liveness check for STATUS op (already admitted)

```python
async def _status_detail(cfg: MaghzSettings) -> N8nDetail:
    async with httpx.AsyncClient(base_url=cfg.n8n.api_url, timeout=cfg.n8n.connect_timeout) as client:
        r = await client.get("/healthz")
        r.raise_for_status()
    return N8nDetail(op=N8nOp.STATUS, healthy=True)
```

`raise_for_status()` propagates to the single `try/except` boundary in `run()` — consistent with the
`_pull_embed_model` pattern in `stack.py`. No exception escapes into domain logic.

### `czlonkowski/n8n-mcp` — MCP server

The `czlonkowski/n8n-mcp` MCP server row is declared exclusively in `admin/mcp/model.py`'s `_SERVER_TABLE`
under `ServerKind.N8N` (command `docker`, image `ghcr.io/czlonkowski/n8n-mcp:latest`). The `docker_env`
block carries `MCP_MODE=stdio`, `LOG_LEVEL=error`, `DISABLE_CONSOLE_OUTPUT=true` as static values plus
`N8N_API_URL=${MAGHZ_MCP__N8N_API_URL}` and `N8N_API_KEY=${MAGHZ_MCP__N8N_API_KEY}` as placeholders.
This blueprint does NOT restate the invocation mechanism; the mcp domain is the sole authority on the
fleet declaration. The `.mcp.json` is the single owner of this server declaration; `admin/rails/n8n.py`
never invokes the MCP server directly. If this blueprint changes the image tag or required env keys,
the `_SERVER_TABLE` row in the mcp blueprint must update in lock-step.

The canonical claim: the `N8N_API_URL` value in that row must equal `str(cfg.n8n.api_url)` at deploy
time (equal to the `n8n_url` exported by Pulumi from `stack.py`). `McpServerSettings.n8n_api_url` must
be set to this value. `N8N_API_KEY` flows through `McpServerSettings.n8n_api_key`, generated
post-first-boot via `POST /api/v1/users/me/api-key` with HTTP Basic auth against the admin user.

### n8n REST API bootstrap for `N8N_API_KEY`

`N8N_API_KEY` is generated once post-first-boot via n8n's REST API:
`POST /api/v1/users/me/api-key` with HTTP Basic auth (admin user credentials created during first-run
setup). The resulting key is stored in the OS keychain under the `maghz` service name and injected into
the MCP server's env by the `mcp` domain's settings surface (`McpServerSettings.n8n_api_key`). A
future `maghz n8n bootstrap` verb (extending `N8nOp.BOOTSTRAP`) would automate this; until then it is
a documented manual Phase 0 step. No new Python code is required now, but `N8nOp` is shaped to absorb
the new case as a single row in `_BUILD` and one new `StrEnum` case.

---

## [04]-[RAILS + ASPECTS]

**Result rail**: the single `try/except` boundary in `run()` catches the closed set
`(httpx.HTTPError, OSError, _N8nProcessError)`. It does NOT catch
`pulumi_automation.errors.CommandError` — that is a `stack.py` concern, not an n8n concern. The happy
path returns a typed `N8nDetail`. The fault message for `_N8nProcessError` carries the exit code and
stderr. No bare `Exception` catch.

**Fault vocabulary** — the `error_context` key `"op"` carries `op.value` (an `N8nOp` `StrEnum`
member): `"export"`, `"import"`, or `"status"`. This is the closed vocabulary, enforced by
`N8nOp`'s own `StrEnum` case set. No separate `type N8nFaultOp = Literal[...]` alias —
`N8nOp` is already the single bounded name for each verb; duplicating it as a `Literal` introduces
a parallel name for the same concept and adds no type safety not already provided by `op.value`.

**anyio structured-concurrency boundary**: every `docker exec` subprocess runs under
`anyio.run_process(..., check=False)` and every `httpx` call runs under
`async with httpx.AsyncClient(...)`. No bare `asyncio.gather`; no `subprocess.run`. The
`_up_blocking`/`run_sync` pattern from `runner.py` does not apply — n8n rail ops are natively async.

**`@aspect` stacking** — stacking order declared here, outermost first:

| Op | Aspects (outermost → innermost) | Rationale |
| --- | --- | --- |
| `STATUS` | `@stamina.retry(on=(httpx.HTTPError, OSError), attempts=3)` → `_status_detail` | liveness probes are idempotent and network-fragile |
| `EXPORT` | no retry aspect | `docker exec` export is idempotent by caller re-run; process errors surface in `run()` boundary |
| `IMPORT` | no retry aspect | same: idempotent re-run is the caller's concern |

Observability: `structlog.get_logger()` bound at `run()` entry, emitting `op`, `container`, and
`workflow_count` as structured fields to stderr. Logging is not an `@aspect` in the Maghz house
pattern — it is a single bind-at-entry call inside `run()`, not a wrapper.

---

## [05]-[PAYLOADS + TABLES]

### `N8nConfig` — `pydantic.BaseModel`, `frozen=True, extra="forbid"` — the single config owner

```python
class N8nConfig(BaseModel):
    model_config = _GROUP   # frozen+forbid ConfigDict from config.py

    image: str = "n8nio/n8n:2.26.8"         # bump to latest-stable at implement time
    container_name: str = "maghz-n8n"
    port: int = Field(default=5678, ge=1024, le=65535)
    host: str = "127.0.0.1"
    protocol: Literal["http", "https"] = "http"
    webhook_url: str = "http://127.0.0.1:5678/"
    proxy_hops: int = Field(default=0, ge=0)
    connect_timeout: float = Field(default=10.0, gt=0)
    workflows_dir: Path = Path("workflows/n8n")
    encryption_key_file: str = "/run/secrets/n8n_encryption_key"

    @computed_field
    @property
    def api_url(self) -> str:
        """Canonical n8n API URL derived from protocol, host, and port. Never stored redundantly."""
        if self.protocol == "https":
            return f"https://{self.host}"
        return f"http://{self.host}:{self.port}"
```

`api_url` is a `pydantic.computed_field` property, never a stored field. This eliminates the
parallel-name violation where a stored `api_url` can drift from `host` + `protocol` + `port`. The
VPS override sets `MAGHZ_N8N__PROTOCOL=https` and `MAGHZ_N8N__HOST=n8n.example.com`; `api_url`
derives automatically — no `MAGHZ_N8N__API_URL` env var required.

`MaghzSettings` gains `n8n: N8nConfig = Field(default_factory=N8nConfig)`. The `MAGHZ_N8N__`
env-nested-delimiter prefix resolves all non-computed fields. `InfraConfig` gains no n8n fields.

`N8N_ENCRYPTION_KEY` is NOT stored in `N8nConfig` — it lives in the OS keychain / secret file.
`webhook_url` is legitimately independent of `api_url` because on VPS it may differ (the public
webhook URL behind a reverse proxy differs from the internal API URL).

### `N8nDetail` — `msgspec.Struct`, `frozen=True, tag="n8n"`

Fields: `op: N8nOp`, `workflow_count: int`, `container: str`, `healthy: bool | UnsetType`.
`healthy` encodes as absent on the wire when `UNSET` (STATUS never ran). Encodes into
`Envelope.report.detail` via `msgspec.json.encode`. The `tag="n8n"` discriminant allows future
upstream consumers to switch on `detail["$type"]`. No generic envelope wrapper; typed receipt only.

### Correspondence table for `N8nOp` → builder → receipt fields

| `N8nOp` | builder | `workflow_count` | `container` | `healthy` |
| --- | --- | --- | --- | --- |
| `EXPORT` | `_export_detail` | `*.json` file count in `workflows_dir` after exec | `cfg.n8n.container_name` | `UNSET` |
| `IMPORT` | `_import_detail` | `*.json` file count in `workflows_dir` before exec | `cfg.n8n.container_name` | `UNSET` |
| `STATUS` | `_status_detail` | `0` | `""` | `True` on /healthz 200; `False` on any HTTP error |

`STATUS` sets `healthy=False` (not `UNSET`) when `/healthz` returns a non-200 status — the boundary
catches `httpx.HTTPStatusError` and returns `N8nDetail(op=N8nOp.STATUS, healthy=False)` rather
than faulting. A `STATUS` that reaches the n8n service and receives a non-200 is not a rail fault;
it is a domain-level result. Only network errors and `OSError` lift to `fault()`.

### Workflow git directory

`workflows/n8n/` in the repo root is the host-side bind-mount target. Each workflow exports as
`<id>.json` via `--separate`. The directory is committed to git. `.gitignore` must NOT exclude
`workflows/n8n/*.json`. Credential stubs inside exported JSON must be reviewed before commit —
node names are included; credential IDs are not sensitive.

### `__main__.py` CLI registration

The `_n8n` sub-app follows the `_schema` pattern:

```python
_n8n = App(name="n8n", help="Manage n8n automation workflows.")
app.command(_n8n)

@_n8n.command(name="export")
async def _n8n_export() -> Envelope:
    return await rails.n8n(rails.N8nOp.EXPORT, settings())

@_n8n.command(name="import")
async def _n8n_import() -> Envelope:
    return await rails.n8n(rails.N8nOp.IMPORT, settings())

@_n8n.command(name="status")
async def _n8n_status() -> Envelope:
    return await rails.n8n(rails.N8nOp.STATUS, settings())
```

`admin/rails/__init__.py` gains `from admin.rails.n8n import run as n8n, N8nOp` and updates `__all__`.

---

## [06]-[DEPS]

No new Python packages are required. The full n8n domain composes from already-admitted deps:
`pulumi-docker`, `anyio`, `httpx`, `msgspec`, `pydantic`, `pydantic-settings`, `structlog`, `stamina`.

`pydantic.computed_field` is available in `pydantic>=2.0`; already admitted.

**czlonkowski/n8n-mcp** is declared in `admin/mcp/model.py` `_SERVER_TABLE`; it is not a Python dep
and is not declared in this domain. The mcp blueprint owns its invocation shape and env-var contract.

**`.api` catalog note**: no new Python library needs a catalog. The implement pass must verify the
exact `anyio.run_process` signature (args, env, cwd, check, stdout/stderr capture mode) against the
admitted `anyio>=4.14.0` catalog at `libs/python/.api/anyio.md` before writing the
`_export_detail` / `_import_detail` bodies. `anyio.Path.glob` availability must also be confirmed;
if `anyio.Path` does not expose `glob`, use `pathlib.Path(cfg.n8n.workflows_dir).glob("*.json")`
(synchronous, safe for a small directory).

---

## [07]-[SEAMS]

| Domains | Claim |
| --- | --- |
| `n8n`, `infra` | `N8nConfig` in `admin/settings/config.py` is the single owner of the n8n container image tag, port, container name, URL shape (via `api_url` computed field), VPS-proxy fields, and `workflows_dir` bind-mount path. The `define()` body in `admin/infra/stack.py` reads `cfg.n8n.*` for every n8n resource. `InfraConfig` carries no n8n-prefixed fields. The `DB_POSTGRESDB_HOST=db` alias in the container env is a stable fact owned by `stack.py`'s `aliases=["db"]` declaration; if that alias changes, the n8n container env must change too. |
| `n8n`, `mcp` | The `czlonkowski/n8n-mcp` MCP server row lives in `admin/mcp/model.py` `_SERVER_TABLE` under `ServerKind.N8N`, with invocation declared there and generated into `.mcp.json` by `maghz mcp generate`. The n8n domain does not declare or re-state the server row. The `N8N_API_URL` value in that row must equal `cfg.n8n.api_url` at deploy time; the mcp blueprint is the authority on the injection mechanism (`McpServerSettings.n8n_api_url` must be set to this value). `N8N_API_KEY` flows through `McpServerSettings.n8n_api_key` (owned by the mcp domain), generated post-first-boot via `POST /api/v1/users/me/api-key`. |
| `n8n`, `remote` | On the Hostinger VPS, `define()` conditionally omits the `ContainerPortArgs` port mapping when `cfg.n8n.protocol == "https"` — the reverse proxy owns the public port on the `maghz` network. All VPS-shape fields (`host`, `protocol`, `webhook_url`, `proxy_hops`) are resolved from `N8nConfig` via env overrides; no conditional branching on a `STACK=vps` discriminant inside `stack.py`. The remote blueprint owns the reverse-proxy and TLS surface; this blueprint specifies which `N8nConfig` fields carry those values. `webhook_url` is independently configurable because the public webhook URL differs from the internal `api_url` behind the proxy. |
| `n8n`, `secrets` | `N8N_ENCRYPTION_KEY` is injected via `N8N_ENCRYPTION_KEY_FILE` (the `_FILE` suffix pattern) pointing at a root-owned file; the path is `cfg.n8n.encryption_key_file`. It must not appear in `N8nConfig`, `.env`, or any git-tracked file. `N8N_API_KEY` follows the same keychain route and is loaded into `McpServerSettings.n8n_api_key` at operator session time via `op run`. The mcp domain owns the wiring; the n8n domain owns the service that generates the key. |

---

## [08]-[PORTABILITY/VPS]

The Pulumi `define()` function closes over `MaghzSettings`. VPS deploy shape is fully resolved by
pydantic-settings env overrides at process start — no conditional branching inside `define()` beyond
the `protocol`-driven port-mapping omission:

- `MAGHZ_N8N__PROTOCOL=https` → port mapping omitted; traffic arrives via reverse proxy; `api_url`
  computes as `https://<host>` automatically from the `@computed_field`
- `MAGHZ_N8N__HOST=n8n.example.com` → sets `N8N_HOST` env var in the container and drives `api_url`
- `MAGHZ_N8N__WEBHOOK_URL=https://n8n.example.com/` → sets `WEBHOOK_URL` (independently configurable)
- `MAGHZ_N8N__PROXY_HOPS=1` → sets `N8N_PROXY_HOPS=1` (behind caddy/nginx)

No `MAGHZ_N8N__API_URL` env var is needed or accepted — `api_url` is a computed property.

`N8N_ENCRYPTION_KEY` is provisioned by `forge-provision` during bootstrap into a root-owned secret
file (path = `cfg.n8n.encryption_key_file`), injected via `N8N_ENCRYPTION_KEY_FILE`. It is never
stored in the Pulumi state file. `N8N_API_KEY` is generated post-first-boot via the n8n REST API
(`POST /api/v1/users/me/api-key` with admin credentials), stored in keyring, and loaded into the
`McpServerSettings.n8n_api_key` field at authoring time by the mcp domain's wiring.

Device-code / OAuth flows do not apply to n8n; it uses static API keys.

---

## [09]-[ACCEPTANCE]

- `ruff check admin/settings/config.py admin/infra/stack.py admin/rails/n8n.py admin/__main__.py` → zero diagnostics.
- `ty check admin/` → zero errors.
- `mypy admin/` → zero errors under the strict config.
- `pydantic` `computed_field` on `N8nConfig.api_url`: `N8nConfig(protocol="https", host="n8n.example.com").api_url == "https://n8n.example.com"` and `N8nConfig().api_url == "http://127.0.0.1:5678"`.
- `maghz up` converges the stack; Pulumi output includes `n8n_url`.
- `docker ps` shows `maghz-n8n` with status `healthy`.
- `maghz n8n export` exits `0` and emits an `Envelope` with `status="ok"`, `detail.$type="n8n"`,
  `detail.op="export"`, and `detail.workflow_count >= 0`; JSON files appear under `workflows/n8n/`;
  `detail.healthy` is absent from the wire JSON (UNSET encodes as omitted).
- `maghz n8n import` exits `0` after a clean export; re-import is idempotent (same workflow IDs).
- `maghz n8n status` exits `0` with `detail.healthy=true` when the container is running; `detail.healthy=false` (not a fault envelope) when `/healthz` returns non-200.
- `GET http://127.0.0.1:5678/healthz` returns HTTP 200.
- `admin/mcp/model.py` `_SERVER_TABLE[ServerKind.N8N]` docker-env block carries `N8N_API_URL` pointing at `cfg.n8n.api_url` value; `maghz mcp generate` regenerates `.mcp.json` including the n8n row; MCP tool list shows the server connected with at least 39 tools when `N8N_API_URL` and `N8N_API_KEY` are populated.
- `N8N_ENCRYPTION_KEY` does not appear in `git log --all -p`, `.env`, or the Pulumi state file.
- `workflows/n8n/*.json` files are git-tracked and round-trip through export → import without
  workflow ID collision.
- `MAGHZ_N8N__PROTOCOL=https maghz up` produces a container without a published host port (port
  mapping list is empty); the `maghz` network alias `n8n` is the only ingress; `cfg.n8n.api_url`
  resolves to `https://<host>` without a port number.
- `run()` boundary `try/except` does NOT catch `pulumi_automation.errors.CommandError`; only
  `(httpx.HTTPError, OSError, _N8nProcessError)` are in scope.
