# [N8N] — Realize-Ready Worklist

Realize-ordered fold of `docs/design/n8n.md`. The blueprint is the design; this worklist is the
execution contract the implement pass runs against the live `admin/` tree. Owner files, ADTs, exact
external members, deps, cross-domain ripples, dependency order, and acceptance gates only.

---

## [00]-[REALIZE_DECISIONS] — blueprint-vs-live reconciliations the implement pass MUST apply

These are not redesigns; they are corrections where the blueprint sketch diverges from the live
canonical owner pattern. The live code is the authority.

- **Dispatch table form: `MappingProxyType`, NOT `expression.Map`.** The blueprint (`[02]-[ADTs]`)
  mandates `expression.Map` and asserts `MappingProxyType` "is rejected per table-dispatch law." The
  live codebase contradicts this: every keyed dispatch table is `MappingProxyType` —
  `admin/rails/stack.py` `_BUILD: Mapping[StackOp, Callable[...]] = MappingProxyType({...})` and
  `admin/core/status.py` `_RANK_EXIT: MappingProxyType[...] = MappingProxyType({...})`. `expression`
  is imported only for `Result`/`Ok`/`Error` (`db.py`, `ledger.py`, `schema.py`, `sync.py`), never
  `expression.Map`. **Realize `_BUILD` as `MappingProxyType`**, mirroring `stack.py` exactly. Do not
  introduce `expression.Map` — it is an unused surface and would be a parallel dispatch form.

- **`assert_never` exhaustiveness.** `stack.py` `run()` does NOT use `assert_never`; it relies on the
  closed `StrEnum` + total `_BUILD` map. Match the live pattern: a total `MappingProxyType` keyed by
  every `N8nOp` case is the exhaustiveness guarantee. `assert_never` is acceptable only as an
  unreachable-branch terminator if a `match` is used, but `stack.py` does not — prefer the direct
  `_BUILD[op]` index for parity with the established owner.

- **Container resource must carry `opts=on` (the colima provider).** The blueprint container sketch
  (`[03]`) passes `opts=pulumi.ResourceOptions(depends_on=[db_container])` but omits the colima
  `provider`. Live `stack.py` threads `provider = docker.Provider("colima", host=infra.docker_host)`
  through `on = pulumi.ResourceOptions(provider=provider)` on every resource. The n8n container,
  volume, and `depends_on` MUST compose the provider:
  `opts=pulumi.ResourceOptions(provider=provider, depends_on=[db_container])`; the n8n volume uses
  `opts=on`. Without it the resource lands on the wrong (default) provider.

- **`db` container handle for `depends_on`.** Live `stack.py` does not bind the `db` container to a
  name — it is an inline `docker.Container("db", ...)` call. To honor `depends_on=[db_container]`,
  the implement pass MUST bind the existing `db` container call to a local
  (`db_container = docker.Container("db", ...)`) inside `define()`. This is an in-place edit to the
  existing call, not a new resource.

- **`.api` catalog path is cross-repo and absent here.** The blueprint cites
  `libs/python/.api/anyio.md`; no `libs/python/.api/` directory exists in the Maghz repo (it is a
  Rasm artifact). No `.api` catalog is authored in this repo. The "verify `anyio.run_process`
  signature" obligation is satisfied by reading the live `anyio` distribution via the toolchain
  (`anyio>=4.14.0` in `pyproject.toml`) and the existing live usage in `admin/rails/sync.py` (line
  59: `anyio.run_process(["heptabase", *argv], check=False)`) and `admin/db.py`. The
  `run_process(..., check=False)` + `result.returncode` + `result.stderr.decode()` shape is already
  proven in-repo; reuse it verbatim.

- **`anyio.Path.glob` vs `pathlib.Path.glob`.** The blueprint's count derives from
  `*.json` file enumeration. Use synchronous `pathlib.Path(cfg.n8n.workflows_dir).glob("*.json")`
  counted via `sum(1 for _ in ...)`; the directory is small and the glob is not a hot path. Do not
  reach for `anyio.Path` here — `sync.py` shows no `anyio.Path` precedent.

---

## [01]-[OWNERS]

| Module | Action | Section | Owns |
| --- | --- | --- | --- |
| `admin/rails/n8n.py` | CREATE | `[TYPES]`, `[MODELS]`, `[ERRORS]`, `[OPERATIONS]` | `N8nOp` closed `StrEnum` + `N8nDetail` tagged `Detail` receipt + `_N8nProcessError` private exception + `_BUILD` `MappingProxyType` dispatch + `run()` polymorphic entrypoint. Owns workflow export, import, and liveness. |
| `admin/settings/config.py` | MODIFY | `[MODELS]` | Add `N8nConfig(BaseModel)` with `model_config = _GROUP`; nest on `MaghzSettings` as `n8n: N8nConfig = Field(default_factory=N8nConfig)`. `api_url` is a `@computed_field` property. Add `"N8nConfig"` to `__all__`. |
| `admin/infra/stack.py` | MODIFY | `[OPERATIONS]` | Extend `define()` with `n8n_data` volume + `n8n` container reading `cfg.n8n.*`; bind the existing `db` call to `db_container`; add `pulumi.export("n8n_url", cfg.n8n.api_url)`. |
| `admin/rails/__init__.py` | MODIFY | re-export | `from admin.rails.n8n import run as n8n, N8nOp`; add `"N8nOp"`, `"n8n"` to `__all__`. |
| `admin/__main__.py` | MODIFY | `[CONSTANTS]`, `[COMPOSITION]` | Add `_N8N = Group("n8n", sort_key=...)`; `_n8n = App(name="n8n", group=_N8N)`; `app.command(_n8n)`; three `@_n8n.command` registrations (`export`/`import`/`status`) each calling `rails.n8n(rails.N8nOp.<CASE>, settings())`. |

No new files beyond `admin/rails/n8n.py`. `InfraConfig` gains NO n8n fields — all n8n config lives in
`N8nConfig`. `admin/mcp/model.py` is NOT authored here (owned by the `mcp` domain; see RIPPLES + DEPENDS_ON).

---

## [02]-[ADTs]

### `N8nOp` — closed verb set, discriminant for `_BUILD` and the CLI

```python
class N8nOp(StrEnum):
    EXPORT = "export"
    IMPORT = "import"
    STATUS = "status"
```

Discriminant: the `StrEnum` value indexes `_BUILD` and carries into `fault()` `error_context["op"]`
as `op.value`. No `BOOTSTRAP` case now — the `StrEnum` + `_BUILD` map are shaped to absorb it later as
one new case + one row (blueprint `[03]` REST bootstrap, deferred manual Phase 0 step).

### `N8nDetail` — typed receipt, tagged `Detail` subclass

```python
class N8nDetail(Detail, frozen=True, tag="n8n"):
    op: N8nOp
    workflow_count: int = 0
    container: str = ""
    healthy: bool | UnsetType = UNSET
```

Discriminant: `tag="n8n"` (encodes as `$type` in `Envelope.report.detail`). `healthy` uses
`msgspec.UnsetType` / `msgspec.UNSET` so STATUS-confirmed liveness is distinct from never-probed
(EXPORT/IMPORT) — `UNSET` encodes as ABSENT on the wire, not `null`. Extends the existing `Detail`
base from `admin/core/model.py` (line 17, `tag=True`); folds into the existing
`Envelope`/`completed()`/`fault()` surface. No parallel DTO.

Correspondence (`N8nOp` -> builder -> receipt fields):

| `N8nOp` | builder | `workflow_count` | `container` | `healthy` |
| --- | --- | --- | --- | --- |
| `EXPORT` | `_export_detail` | `*.json` count in `workflows_dir` AFTER exec | `cfg.n8n.container_name` | `UNSET` |
| `IMPORT` | `_import_detail` | `*.json` count in `workflows_dir` BEFORE exec | `cfg.n8n.container_name` | `UNSET` |
| `STATUS` | `_status_detail` | `0` | `""` | `True` on /healthz 200; `False` on HTTP non-200 |

`STATUS` returns `healthy=False` (NOT a fault) when `/healthz` returns non-200 — the boundary catches
`httpx.HTTPStatusError` and returns `N8nDetail(op=N8nOp.STATUS, healthy=False)`. Only network/`OSError`
lift to `fault()`.

### `_N8nProcessError` — private exception (ERRORS)

```python
class _N8nProcessError(Exception):
    def __init__(self, returncode: int, stderr: str) -> None: ...
```

Raised inside `_export_detail`/`_import_detail` on non-zero `docker exec` exit, carrying exit code +
stderr; caught at the single `try/except` in `run()`. Private, never exported. Mirrors the closed-set
boundary discipline of `stack.py`.

---

## [03]-[API_MEMBERS]

All members already in scope; no new package import.

| Package | Member | Use |
| --- | --- | --- |
| `pulumi_docker` | `docker.Container` | the `n8n` container resource |
| `pulumi_docker` | `docker.Volume` | `n8n-data` named volume (`/home/node/.n8n`) |
| `pulumi_docker` | `docker.ContainerPortArgs` | `internal=5678, external=cfg.n8n.port, ip="127.0.0.1"` — omitted entirely when `protocol == "https"` |
| `pulumi_docker` | `docker.ContainerVolumeArgs` | named-volume mount + host bind of `workflows_dir.resolve()` -> `/home/node/workflows` |
| `pulumi_docker` | `docker.ContainerNetworksAdvancedArgs` | `name=network.name, aliases=["n8n"]` |
| `pulumi_docker` | `docker.ContainerHealthcheckArgs` | `wget -qO- http://localhost:5678/healthz` CMD-SHELL probe |
| `pulumi` | `pulumi.ResourceOptions(provider=provider, depends_on=[db_container])` | provider thread + DB ordering |
| `pulumi` | `pulumi.export` | `pulumi.export("n8n_url", cfg.n8n.api_url)` |
| `anyio` | `anyio.run_process(..., check=False)` | `docker exec -u node <c> n8n export:workflow/import:workflow`; read `.returncode`, `.stderr.decode()` — same shape as `sync.py:59` |
| `httpx` | `httpx.AsyncClient(base_url=..., timeout=...)` + `client.get("/healthz")` + `r.raise_for_status()` | STATUS liveness; same shape as `stack.py` `_pull_embed_model` |
| `httpx` | `httpx.HTTPError`, `httpx.HTTPStatusError` | boundary catch set; `HTTPStatusError` -> `healthy=False`, `HTTPError`/`OSError` -> `fault()` |
| `msgspec` | `msgspec.Struct` (via `Detail` base), `msgspec.UnsetType`, `msgspec.UNSET` | receipt + absent-on-wire `healthy` |
| `pydantic` | `BaseModel`, `Field`, `computed_field`, `ConfigDict` (via `_GROUP`) | `N8nConfig` + derived `api_url` |
| `stamina` | `stamina.retry(on=(httpx.HTTPError, OSError), attempts=3)` | STATUS-only idempotent liveness retry aspect (already in `pyproject.toml` ruff `runtime-evaluated-decorators`) |
| `structlog` | `structlog.get_logger()` bound at `run()` entry | structured `op`/`container`/`workflow_count` to stderr; bind-at-entry, NOT an `@aspect` |
| `pathlib` | `Path.glob("*.json")` counted via `sum(1 for _ in ...)` | EXPORT/IMPORT `workflow_count` |

`_BUILD: Mapping[N8nOp, Callable[[MaghzSettings], Awaitable[N8nDetail]]] = MappingProxyType({...})` —
keyed by all three `N8nOp` cases. `run()` body mirrors `stack.py:132-135`: single
`try: return completed(Status.OK, await _BUILD[op](cfg))` with
`except (httpx.HTTPError, OSError, _N8nProcessError) as exc: return fault(str(exc), {"op": op.value})`.
`STATUS` `healthy=False` is handled INSIDE `_status_detail` (catch `httpx.HTTPStatusError` there),
not at the `run()` boundary.

### `N8nConfig` field surface (config.py `[MODELS]`)

```python
class N8nConfig(BaseModel):
    model_config = _GROUP
    image: str = "n8nio/n8n:<latest-stable-at-implement>"   # blueprint pins 2.26.8; bump to latest
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
        return f"https://{self.host}" if self.protocol == "https" else f"http://{self.host}:{self.port}"
```

`api_url` is a `@computed_field` property — NEVER a stored field, NEVER a `MAGHZ_N8N__API_URL` env var.
`MAGHZ_N8N__` nested prefix (env delimiter `__`) resolves all non-computed fields.

### `__main__.py` registration

```python
_n8n = App(name="n8n", help="Manage n8n automation workflows.", group=_N8N)
app.command(_n8n)

@_n8n.command(name="export")
async def _n8n_export() -> Envelope:
    return await rails.n8n(rails.N8nOp.EXPORT, settings())
# ...import / status mirror, each one-line dispatch
```

Add `_N8N = Group("n8n", sort_key=50)` to `[CONSTANTS]` (after `_SYNC` sort_key=40, before `_GLOBAL`=99).

---

## [04]-[DEPS]

No new Python packages. Every member composes from already-admitted `pyproject.toml` deps:
`pulumi-docker`, `anyio`, `httpx`, `msgspec`, `pydantic`, `pydantic-settings`, `structlog`, `stamina`.
`pydantic.computed_field` ships in `pydantic>=2.13.4` (admitted). No `.api` catalog authored — no
`libs/python/.api/` directory exists in this repo, and no new library is admitted.

`czlonkowski/n8n-mcp` is NOT a Python dep — it is a `docker`-launched MCP server row owned by the
`mcp` domain's `_SERVER_TABLE` (`admin/mcp/model.py`, not yet realized), generated into `.mcp.json`.
Band-equivalent note for the mcp domain when it lands: `cli` (a `docker run` invocation of
`ghcr.io/czlonkowski/n8n-mcp:latest`, `MCP_MODE=stdio`).

| Package | Band | Catalog note |
| --- | --- | --- |
| (none) | — | n8n domain admits zero new packages; no catalog authored in-repo |

---

## [05]-[RIPPLES]

| Domains | Claim |
| --- | --- |
| `n8n`, `infra` | `N8nConfig` in `admin/settings/config.py` is the SOLE owner of n8n image tag, port, container name, URL shape (`api_url` computed), VPS-proxy fields, `workflows_dir`, and `encryption_key_file`. `define()` in `admin/infra/stack.py` reads `cfg.n8n.*` for every n8n resource; `InfraConfig` carries NO n8n fields. The `DB_POSTGRESDB_HOST=db` env value depends on `stack.py`'s `aliases=["db"]` on the `db` container — a stable fact owned by `infra`; if that alias changes, the n8n container env must change in lock-step. The n8n container MUST thread the colima `provider` (`opts=on`) like every other resource in `define()`. |
| `n8n`, `mcp` | The `czlonkowski/n8n-mcp` server row lives ONLY in the mcp domain's `_SERVER_TABLE` (`admin/mcp/model.py`) under `ServerKind.N8N`, generated into `.mcp.json` by `maghz mcp generate`. The n8n domain NEVER declares or re-states the row and never invokes the MCP server. Canonical shared shape: `N8N_API_URL` in that row MUST equal `str(cfg.n8n.api_url)` at deploy time (equal to Pulumi's exported `n8n_url`); the mcp domain sets `McpServerSettings.n8n_api_url` to this value. `N8N_API_KEY` flows through `McpServerSettings.n8n_api_key` (mcp-owned), generated post-first-boot via `POST /api/v1/users/me/api-key` (HTTP Basic, admin user). If this domain changes the image tag or env keys, the `_SERVER_TABLE` row updates in lock-step. |
| `n8n`, `remote` | On the Hostinger VPS, `define()` omits `ContainerPortArgs` entirely when `cfg.n8n.protocol == "https"` — the reverse proxy owns the public port on the `maghz` network. All VPS-shape fields (`host`, `protocol`, `webhook_url`, `proxy_hops`) resolve from `N8nConfig` via `MAGHZ_N8N__*` env overrides; NO `STACK=vps` branch inside `stack.py`. `remote` owns reverse-proxy/TLS; this domain specifies which `N8nConfig` fields carry those values. `webhook_url` is independently configurable (public webhook URL differs from internal `api_url` behind the proxy). |
| `n8n`, `secrets` | `N8N_ENCRYPTION_KEY` is injected via `N8N_ENCRYPTION_KEY_FILE` (the `_FILE` suffix pattern) pointing at a root-owned file at `cfg.n8n.encryption_key_file`; it MUST NOT appear in `N8nConfig`, `.env`, or any git-tracked file, and is never in the Pulumi state file (provisioned by `forge-provision` at bootstrap). `N8N_API_KEY` follows the keychain route, loaded into `McpServerSettings.n8n_api_key` at operator-session time via `op run`. The `secrets`/`mcp` domains own the keychain wiring; the n8n domain owns the service that GENERATES the key. |
| `n8n`, `runtime` | The n8n rail composes the runtime-owned contract surface: `Envelope`/`Report`/`Detail`/`completed()`/`fault()` (`admin/core/model.py`), `Status` (`admin/core/status.py`), `MaghzSettings`/`settings()` (`admin/settings/config.py`), the cyclopts `App`/`Group` meta-launcher + `anyio.run` loop ownership (`admin/__main__.py`), and the `MappingProxyType` dispatch-table + `try/except`-boundary house pattern proven in `admin/rails/stack.py`. These shapes are runtime-owned; n8n extends them, never forks them. |

---

## [06]-[DEPENDS_ON]

| Domain | Why it must be realized first |
| --- | --- |
| `runtime` | Owns `Envelope`/`Detail`/`completed()`/`fault()`/`Status`, `MaghzSettings`/`settings()`, the cyclopts meta-launcher + `anyio.run` loop, and the `MappingProxyType` dispatch + boundary `try/except` house pattern. Already realized in `admin/core/`, `admin/settings/`, `admin/__main__.py`, `admin/rails/stack.py`; n8n composes them directly. |
| `infra` | `admin/infra/stack.py` `define()` + the colima `provider`, `network`, and the `db` container (whose `aliases=["db"]` the n8n container env depends on) must exist before the n8n container is folded in. Already realized; n8n edits `define()` in place. |
| `mcp` | The `czlonkowski/n8n-mcp` `_SERVER_TABLE` row + `McpServerSettings.n8n_api_url`/`.n8n_api_key` are mcp-owned. `admin/mcp/model.py` does NOT yet exist. The n8n RAIL + CONFIG land independently of mcp (no code coupling); only the deploy-time `N8N_API_URL == cfg.n8n.api_url` equality + the `.mcp.json` n8n row require mcp realized. Realize mcp before the MCP-tool-list acceptance gate, NOT before the n8n rail. |
| `secrets` | Owns the `forge-provision` encryption-key-file provisioning and the keychain route for `N8N_API_KEY`. Required before the `maghz up` -> healthy-container and the no-secret-in-git acceptance gates pass, NOT before the rail compiles. |

n8n's Python surface (config + rail + CLI) has zero hard code-dependency on `mcp`/`secrets`/`remote`;
those are deploy-time and cross-domain-contract dependencies gating the runtime acceptance signals.

---

## [07]-[ACCEPTANCE]

Static gate (zero diagnostics each):
- `ruff check admin/settings/config.py admin/infra/stack.py admin/rails/n8n.py admin/rails/__init__.py admin/__main__.py`
- `ty check admin/`
- `mypy admin/`

Behavioral / runtime:
- `N8nConfig(protocol="https", host="n8n.example.com").api_url == "https://n8n.example.com"` and
  `N8nConfig().api_url == "http://127.0.0.1:5678"`.
- `maghz up` converges the stack; Pulumi output includes `n8n_url`.
- `docker ps` shows `maghz-n8n` with status `healthy`.
- `maghz n8n export` exits `0`; `Envelope` has `status="ok"`, `detail.$type="n8n"`,
  `detail.op="export"`, `detail.workflow_count >= 0`; `*.json` appear under `workflows/n8n/`;
  `detail.healthy` is ABSENT from the wire JSON (UNSET -> omitted).
- `maghz n8n import` exits `0` after a clean export; re-import idempotent (same workflow IDs).
- `maghz n8n status` exits `0` with `detail.healthy=true` when running; `detail.healthy=false`
  (NOT a fault envelope) when `/healthz` returns non-200.
- `GET http://127.0.0.1:5678/healthz` -> HTTP 200.
- `MAGHZ_N8N__PROTOCOL=https maghz up` -> container with NO published host port (empty port list);
  `n8n` network alias is the only ingress; `cfg.n8n.api_url` resolves to `https://<host>` without a port.
- `run()` boundary `try/except` catches ONLY `(httpx.HTTPError, OSError, _N8nProcessError)` — NOT
  `pulumi.automation.errors.CommandError` (an infra/stack concern).

Cross-domain (gated on mcp/secrets realized):
- `admin/mcp/model.py` `_SERVER_TABLE[ServerKind.N8N]` docker-env carries `N8N_API_URL` == `cfg.n8n.api_url`
  value; `maghz mcp generate` regenerates `.mcp.json` with the n8n row; MCP tool list shows the server
  connected with >= 39 tools when `N8N_API_URL` + `N8N_API_KEY` are populated.
- `N8N_ENCRYPTION_KEY` does not appear in `git log --all -p`, `.env`, or the Pulumi state file.
- `workflows/n8n/*.json` are git-tracked (`.gitignore` must NOT exclude them) and round-trip
  export -> import without workflow ID collision.
