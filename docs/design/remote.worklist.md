# [WORKLIST_REMOTE] — admin/remote/

Realize-ready worklist for the `remote` domain. The blueprint `remote.md` is the design; this is the execution order. One canonical owner per concept; no parallel surface beyond what the blueprint sanctions.

---

## [00]-[DEPENDS_ON]

These domains' owners MUST be realized before `remote` can compose them. They are hard prerequisites, not soft ripples.

| Domain key | Owner surface this domain consumes | Why blocking |
| --- | --- | --- |
| `runtime` | `admin/runtime/rails.py` (`BoundaryFault`, `RuntimeRail[T]`, `async_boundary`, `CLASSIFY`), `admin/runtime/resilience.py` (`RetryClass`, `guard`), `admin/runtime/receipts.py` (`@receipted`) | The entire domain-internal fault rail. None of these symbols exist in `admin/` today — `admin/runtime/` is absent; `admin/rails/stack.py` is still exception-based (`try/except` at the boundary). The remote domain cannot lift faults, retry transients, or classify exceptions without this substrate. |
| `existing-rails` | `StackOp` + `StackDetail` (relocated to `admin/infra/runner.py`), `SchemaDetail` (reshaped under `SchemaOp` in `admin/rails/schema.py`) | `deploy` discriminates on `StackOp` and decodes `StackDetail`/`SchemaDetail` from remote stdout. `existing-rails` MOVES `StackOp`/`StackDetail` ownership from `admin/rails/stack.py` to `admin/infra/runner.py` and collapses `apply`/`doctor` into `run(op: SchemaOp, ...)`. Import the relocated owners, not the stale `admin/rails/stack.py` paths the remote blueprint's §01 table names. |
| `cloud-sync` | `CloudOp.RESTORE` (`admin/rails/cloud.py`), `CloudConfig` (`MaghzSettings.cloud`) | `deploy(target, StackOp.UP)` invokes `maghz cloud restore` over SSH as the post-restore step (§08 cloud-sync seam). The remote domain does not own restore; it composes it via remote `conn.run`. Soft dependency: realizable as a deferred deploy arm if `cloud-sync` lags, but the canonical sequence assumes `CloudOp.RESTORE` exists. |

Settling order: `runtime` → `existing-rails` → `cloud-sync` → `remote`.

---

## [01]-[OWNERS]

| File | Action | Owns (dense polymorphic type) |
| --- | --- | --- |
| `admin/remote/__init__.py` | create | Beartype claw hook (`beartype_this_package()`) + package re-exports (`RemoteOp`, `RemoteTarget`, `exec`, `deploy`). No logic. |
| `admin/remote/connection.py` | create | The asyncssh connection lifecycle + credential projection. Owns `KnownHostsPolicy` (`[TYPES]`), `RemoteTarget` value object + `from_config` (`[MODELS]`), `target_options` + `connection` async-ctx (`[OPERATIONS]`), `_RETRY_ON` retryable-exception frozenset (`[CONSTANTS]`). |
| `admin/remote/ops.py` | create | All VPS operations in one file: `ExecReceipt` + `DeployReceipt` (`[MODELS]`), `_REMOTE_ENV` env projection (`[CONSTANTS]`/`[TABLES]`), `_push_tree` shared push (`[OPERATIONS]`), `exec` + `deploy` modal entrypoints (`[OPERATIONS]`). `_push_tree` is module-level private (shared by both entrypoints, NOT inlined twice). |
| `admin/settings/config.py` | modify | Add `RemoteConfig(BaseModel)` subgroup (uses `_GROUP` ConfigDict) + `MaghzSettings.remote: RemoteConfig = Field(default_factory=RemoteConfig)`. `known_hosts` stays `str` (raw env ingress); the `KnownHostsPolicy` boundary is at `RemoteTarget.from_config`, not the pydantic model. |
| `admin/settings/__init__.py` | modify | Re-export `RemoteConfig` alongside the existing config subgroups. |
| `admin/__main__.py` | modify | Mount `exec` and `deploy` cyclopts commands under a new `_REMOTE = Group("Remote", sort_key=...)`. `exec` takes `*argv`; `deploy` takes `--op` (`StackOp` discriminant). Each derives `RemoteTarget.from_config(settings().remote)` and calls the `ops` entrypoint. The `__main__` fault handler projects `Error(BoundaryFault)` → `fault(...)`. |
| `admin/remote/.api/asyncssh.md` | create (BEFORE realize) | Domain-facing asyncssh evidence slice (connection/exec/SFTP/TOFU/auth/fault taxonomy), cited against `asyncssh>=2.23.1`. References, never duplicates, the Rasm catalog. |
| `pyproject.toml` | modify | Admit `asyncssh>=2.23.1` + `frozendict` (see [04]); extend the `runtime-evaluated-base-classes`/per-package mypy override pattern for `asyncssh` if stubs are absent. |
| `admin/runtime/rails.py` | modify (cross-domain) | Extend `CLASSIFY` with asyncssh exception rows (see [05]/[06]). One row per exception family, no new function. Owned by `runtime`; the remote pass edits in place. |

No `admin/remote/push.py`. No `_ConnectionPool`. No second SSH client, known-hosts resolver, or deploy verb. No `RemoteFault` StrEnum.

---

## [02]-[ADTs]

| ADT | Kind | Cases | Discriminant | Site |
| --- | --- | --- | --- | --- |
| `RemoteOp` | `StrEnum` (closed verb vocabulary) | `EXEC = "exec"`, `DEPLOY = "deploy"` | CLI command selection | `ops.py` `[TYPES]`. `PUSH`/`PULL` excluded — both implicit in `exec`/`deploy`, never standalone. |
| `KnownHostsPolicy` | `type` alias union | `Literal["insecure"] \| Path` | total `match` in `target_options` | `connection.py` `[TYPES]`. Closes the `None`-passes-silently bug at the type level. `case "insecure":` → log `ssh.host_key_verification_disabled`, pass `known_hosts=None`; `case Path() as p:` → `known_hosts=str(p)`. No `None` arm. |
| `RemoteTarget` | `msgspec.Struct(frozen=True, gc=False, kw_only=True)` value object | fields: `host: str`, `port: int`, `user: str`, `known_hosts: KnownHostsPolicy`, `workroot: str` | — (single shape) | `connection.py` `[MODELS]`. One factory `from_config(cfg: RemoteConfig) -> RemoteTarget` (`@classmethod` or module fn) converts `cfg.known_hosts: str` → `KnownHostsPolicy` (`"insecure"` literal → `Literal["insecure"]`, else `Path(value)`). No `connect_kwargs` dict property, no `url` property. |
| `ExecReceipt` | `Detail` subclass `msgspec.Struct(frozen=True, gc=False, tag="remote_exec")` | fields: `target: str`, `host: str`, `exit_status: int \| None`, `exit_signal: str \| None`, `pushed: int`, `pulled: int`, `notes: tuple[str, ...]` | `tag="remote_exec"` | `ops.py` `[MODELS]`. `exit_status`/`exit_signal` types match `asyncssh.SSHCompletedProcess` exactly. |
| `DeployReceipt` | `Detail` subclass `msgspec.Struct(frozen=True, gc=False, tag="remote_deploy")` | fields: `op: StackOp`, `pushed: int`, `push_notes: tuple[str, ...]`, `up_detail: StackDetail \| None`, `schema_detail: SchemaDetail \| None` | `tag="remote_deploy"` | `ops.py` `[MODELS]`. Carries decoded `StackDetail`/`SchemaDetail` — NOT nested `Envelope`. `up_detail`+`schema_detail` populated for `UP`; both `None` for `DOWN`/`STATUS`. |

Total `match` + `assert_never` at every discriminant site: `StackOp` in `ops.deploy`; `RemoteOp` in the CLI sub-app; `KnownHostsPolicy` in `target_options`. `StackOp` itself is consumed read-only from its `existing-rails` owner (`admin/infra/runner.py`) — never re-declared.

---

## [03]-[API_MEMBERS]

### `asyncssh` (>=2.23.1)

| Member | Composition site |
| --- | --- |
| `asyncssh.connect(host, port=, username=, options=SSHClientConnectionOptions(...))` | `connection()` — one options object, never `**dict` keyword soup |
| `asyncssh.SSHClientConnectionOptions(known_hosts=, connect_timeout=, login_timeout=, keepalive_interval=, keepalive_count_max=, client_keys=)` | `target_options()` — the one options builder |
| `asyncssh.SSHClientConnection` (async ctx mgr) | the connection resource scope |
| `SSHClientConnection.run(command, check=True, encoding=None)` | remote exec; `check=True` raises `ProcessError` on non-zero exit; caught by `async_boundary` (never manual `exit_status` inspection) |
| `SSHClientConnection.start_sftp_client()` | SFTP session (async ctx mgr) |
| `SFTPClient.makedirs(path, exist_ok=True)` | remote run-dir creation before push |
| `SFTPClient.put(locals, remotedir, max_requests=cfg.remote.sftp_max_requests, error_handler=...)` | per-directory push fan-out in `_push_tree` |
| `SFTPClient.mget(remotepaths, localpath=local_dir, recurse=True, error_handler=...)` | artifact pull in `exec` |
| `asyncssh.get_server_host_key(host, port)` | TOFU bootstrap; returns `SSHKey \| None` (`None` aborts) |
| `asyncssh.generate_private_key("ssh-ed25519")`, `asyncssh.read_private_key(filename, passphrase=None) -> SSHKey` | Ed25519 keypair generation/load for `client_keys=` auth |
| `asyncssh.connect_agent(agent_path=None) -> SSHAgentClient`, `SSHAgentClient.get_keys()` | ssh-agent-backed auth without copying private keys |
| `asyncssh.set_log_level(level)`, `asyncssh.set_sftp_log_level(level)` | routed into structlog once at composition |
| `asyncssh.Error`, `asyncssh.DisconnectError`, `asyncssh.ConnectionLost`, `asyncssh.ChannelOpenError`, `asyncssh.HostKeyNotVerifiable`, `asyncssh.PermissionDenied`, `asyncssh.ProcessError`, `asyncssh.SFTPError` | fault taxonomy → `CLASSIFY` rows |
| `asyncssh.SSHCompletedProcess` (`.exit_status`, `.exit_signal`, `.stdout`, `.stderr`) | receipt projection on completed run or `ProcessError` |

`asyncssh` imported unconditionally (NOT under `TYPE_CHECKING`) — `beartype_this_package` resolves annotations at import time. The ruff `TC002` ignore already covers this under the claw.

### `anyio` (admitted)

| Member | Composition site |
| --- | --- |
| `anyio.create_task_group()` | per-directory push fan-out in `_push_tree` |
| `anyio.CapacityLimiter(cfg.remote.sftp_push_concurrency)` | SFTP push concurrency bound |
| `anyio.run_process(("git", "ls-files", "--cached", "--exclude-standard", "-z"))` | NUL-delimited tracked-file manifest; `cwd=` local workroot |

### `msgspec` (admitted)

| Member | Composition site |
| --- | --- |
| `msgspec.json.decode(stdout_bytes, type=Envelope)` | decode remote `maghz` stdout in `deploy` |
| `msgspec.DecodeError` | malformed remote stdout → `BoundaryFault.boundary` via `async_boundary` |
| `Detail` subclassing, `frozen=True, gc=False, tag=...` | `ExecReceipt`/`DeployReceipt` declarations |

### `admin/runtime/` substrate (DEPENDS_ON `runtime`)

| Member | Composition site |
| --- | --- |
| `guard(RetryClass.HTTP)` | wraps `asyncssh.connect` in `connection()` for transient reconnect (`ConnectionLost`/`DisconnectError`/`ChannelOpenError`) |
| `guard(RetryClass.SECRET)` | wraps keyring credential reads for any VPS keychain probe path |
| `async_boundary("remote.exec" \| "remote.deploy", thunk) -> RuntimeRail[T]` | the single fault-lift point at every SSH/SFTP boundary; no inline `try/except` in `ops.py`/`connection.py` |
| `RuntimeRail[T]` = `Result[T, BoundaryFault]` | all internal folds; the CLI boundary projects `Error(BoundaryFault)` → `fault(...)` |
| `BoundaryFault` (`resource`/`api`/`boundary`/`deadline` cases) | the fault vocabulary; remote adds NO new cases |
| `@receipted` (`admin/runtime/receipts.py`) | not directly composed here — telemetry surface when `automation` composes remote ops as `Admit` units |

### `structlog` (admitted)

`structlog.contextvars.bind_contextvars(rail="remote", op=op_name)` at the entrypoint scope; propagates across anyio task boundaries.

---

## [04]-[DEPS]

| Package | Band | `.api` catalog note | Status |
| --- | --- | --- | --- |
| `asyncssh>=2.23.1` | pure-venv | Author `admin/remote/.api/asyncssh.md` BEFORE realize: connection + `SSHClientConnectionOptions`, `run(check=True)` exec surface, `SFTPClient.put`/`mget`/`makedirs`, `get_server_host_key` TOFU, `connect_agent`/`SSHAgentClient`, `read_private_key`/`generate_private_key`, full fault taxonomy. Maghz-local evidence file referencing the Rasm `libs/python/runtime/.api/asyncssh.md` slice, not duplicating it. | NOT admitted — add to `pyproject.toml` `dependencies`. Pure-Python wheel; `uv lock` regenerates cleanly. License EPL-2.0 OR GPL-2.0+ (unmodified library use). |
| `frozendict` | pure-venv | Note in the `pyproject.toml` dependency comment band: backs `_REMOTE_ENV: frozendict[str, str]` (immutable env projection). Already a `ruff runtime-evaluated`-compatible C extension wheel. | NOT admitted — the blueprint §07 claims `frozendict` is "already admitted"; verification of `pyproject.toml` shows it is ABSENT. Admit it, OR substitute `types.MappingProxyType` (already used by `admin/rails/stack.py` `_BUILD`) to avoid a new dep. Decision: prefer `MappingProxyType` for `_REMOTE_ENV` to honor the existing in-repo immutable-map idiom and skip a dependency; if `cloud-sync` admits `frozendict` first (its `_BUILD` uses `frozendict`), align on that. Resolve at realize against whichever lands first. |

No other new packages. `anyio`, `stamina`, `msgspec`, `pydantic`, `pydantic-settings`, `structlog`, `expression` are confirmed admitted in `pyproject.toml`.

---

## [05]-[RIPPLES]

| Domains | Claim |
| --- | --- |
| `remote` ↔ `runtime` | `BoundaryFault` + `RuntimeRail[T]` + `async_boundary` are the sole domain-internal fault rail; `runtime` owns them, `remote` consumes read-only. NO parallel `RemoteFault` StrEnum. One-directional seam: `runtime.md` declares, `remote.md` consumes. |
| `remote` ↔ `runtime` | `CLASSIFY` (in `admin/runtime/rails.py`) gains asyncssh rows: `(ProcessError, SFTPError)` → `boundary`; `(PermissionDenied, HostKeyNotVerifiable)` → `api`; `(ConnectionLost, DisconnectError, ChannelOpenError)` → `resource`; `msgspec.DecodeError` → `boundary`. Rows ordered before `(OSError,)` and `(Exception,)` catch-alls. `runtime` owns the table; `remote` pass adds rows in place — no new function, no parallel table. |
| `remote` ↔ `runtime` | `RetryClass.HTTP` covers asyncssh transients (`ConnectionLost`/`DisconnectError`/`ChannelOpenError`) at the same timing band as httpx transients. If the `POLICY[RetryClass.HTTP]` `target` is typed to a specific httpx exception set, `runtime` broadens it to include asyncssh transients within the SAME class — no new `RetryClass.SSH` unless timing parameters diverge materially. `PermissionDenied`/`HostKeyNotVerifiable` MUST NOT appear in any retry `target` (terminal → `api`). |
| `remote` ↔ `existing-rails` | `StackOp` + `StackDetail` ownership is RELOCATED by `existing-rails` to `admin/infra/runner.py` (not `admin/rails/stack.py`). `ops.deploy` imports `StackOp` from its relocated owner as the deploy discriminant; `DeployReceipt.up_detail: StackDetail \| None` carries the read-only decoded `StackDetail`. No copy, no alias, no re-declaration. When `StackOp` gains a case (e.g. `RESTART`), `ops.deploy`'s `match` extends an arm; `assert_never` catches the gap at static-analysis time. |
| `remote` ↔ `existing-rails` | `SchemaDetail` is owned by `admin/rails/schema.py` (reshaped under `SchemaOp` by `existing-rails`). `DeployReceipt.schema_detail: SchemaDetail \| None` imports it read-only; `remote` never re-declares it. |
| `remote` ↔ `cloud-sync` | `cloud-sync`'s `run(CloudOp.RESTORE, cfg)` is the data-recovery primitive `deploy(target, StackOp.UP)` invokes over SSH (`maghz cloud restore` then `maghz schema apply`). Shared surface: `MaghzSettings.database.dsn` and the keyring/env credential layer; `RemoteConfig` and `CloudConfig` are peer subgroups both reading `MaghzSettings`. |
| `remote` ↔ `cloud-sync` (`settings`) | `RemoteConfig` is a peer subgroup alongside `InfraConfig`/`CloudConfig` under `MaghzSettings`. `InfraConfig` owns local Pulumi state; `RemoteConfig` owns remote SSH facts; `CloudConfig` owns cloud-remote OAuth. `ops.deploy` reads `infra` (stack identity) and `remote` (SSH target). |
| `remote` ↔ `existing-rails` / all rails (`Envelope`) | Every `admin/` rail emits exactly one `Envelope`. `remote` emits the same shape AND decodes remote `maghz` stdout via `msgspec.json.decode(stdout, type=Envelope)` — never `json.loads` or hand-rolled parsing. `DeployReceipt` carries `StackDetail`/`SchemaDetail` extracted from the decoded remote `Envelope.report.detail`, never the outer `Envelope`. |
| `remote` ↔ `automation` | `@receipted` (telemetry) fires when the `automation` domain composes remote ops as `Admit` units. `remote` itself adds no OTel span decoration; the receipt surface is `automation`'s composition concern. |
| `remote` ↔ Rasm assay (cross-repo, non-blocking) | The `KnownHostsPolicy` typed-vocabulary fix mirrors the `None`-passes-silently bug in Rasm `tools/assay/core/engine.py` `_insecure_host_key`. Cross-repo concern; does NOT block Maghz `remote`. |
| `remote` ↔ Rasm assay (`ExecReceipt` naming) | Rasm `tools/assay/core/model.py` `ExecReceipt` is a `Completed`/`Report` carrier field (multi-outcome fold), NOT a `Detail` subclass. Maghz `ExecReceipt` IS a `Detail` subclass (one receipt per invocation). Shapes analogous, not shared; canonical field names `target`/`host`/`exit_status`/`exit_signal`/`pushed`/`pulled`/`notes` stay stable across both. |

---

## [06]-[SEAMS] (in-repo edits this domain triggers)

- `admin/runtime/rails.py` `CLASSIFY` — add asyncssh rows (see [05]). The remote pass verifies presence and extends in place. This is the single mutation of a `runtime`-owned file.
- `admin/runtime/resilience.py` `POLICY[RetryClass.HTTP]` `target` — broaden to admit asyncssh transients if not already structural. No new `RetryClass` member unless timing diverges.
- `admin/settings/config.py` — append `RemoteConfig` subgroup + `MaghzSettings.remote` field.
- `admin/settings/__init__.py` — re-export `RemoteConfig`.
- `admin/__main__.py` — mount `exec`/`deploy` commands + `_REMOTE` group; the existing `fault` handler already collapses `Error(BoundaryFault)` (no new handler).

---

## [07]-[PORTABILITY / VPS NOTES] (realize-gate confirmations)

- Git-lfs posture: `git ls-files --cached --exclude-standard -z` returns lfs POINTER files (not binaries) for `filter=lfs` paths. Confirm before realize whether Maghz uses git-lfs; if so, add a post-manifest filter skipping lfs-tracked paths. If not, the standard manifest is correct.
- VPS invocation: after `_push_tree`, deploy runs `uv run --project <workroot> python -m admin <subcommand>` (`uv` pre-installed by bootstrap; `pyproject.toml` is tracked and pushed). Command built via `shlex.quote` composition — never raw interpolation.
- TOFU bootstrap: `asyncssh.get_server_host_key` pins the host key into `~/.ssh/known_hosts` (or `MAGHZ_REMOTE_KNOWN_HOSTS`); `None` return aborts. Ed25519 key auth or ssh-agent are the exclusive credential mechanisms; no OP token / device-code flow. All credential paths gitignored; `gitleaks` gate on commit.
- `_REMOTE_ENV` forwards `MAGHZ_DATABASE_DSN` (from `cfg.database.dsn`) + `MAGHZ_LOG__FORMAT=json` only.

---

## [08]-[ACCEPTANCE]

- `ruff check admin/remote/ --select=ALL` — zero diagnostics (same ignore table as `pyproject.toml`).
- `ty check admin/remote/` — zero errors (the binding type gate; `asyncssh` stubs present or `import-untyped` handled by the ignore table).
- `mypy admin/remote/` — advisory; zero errors under `strict=True` with the `pg8000`-pattern per-package override extended to `asyncssh` if stubs absent.
- `asyncssh>=2.23.1` admitted in `pyproject.toml` `dependencies`; `uv lock` regenerates cleanly. `_REMOTE_ENV` immutable-map dep decision (frozendict vs MappingProxyType) resolved and consistent with `cloud-sync`.
- `admin/remote/.api/asyncssh.md` authored before any production source.
- `asyncssh.connect()` always routes through `target_options()` — never raw `**dict` keyword soup.
- `conn.run(command, check=True)` — non-zero exit raises `ProcessError`, caught by `async_boundary`; never manual `exit_status` inspection.
- `target_options` `match policy:` exhaustive — `case "insecure":` + `case Path() as p:`, no bare `None` arm.
- `ops.deploy` `match op:` exhaustive over `StackOp` with `case _ as unreachable: assert_never(unreachable)`.
- No `RemoteFault` StrEnum anywhere in `admin/remote/`; all fault paths use `BoundaryFault` from `admin/runtime/rails.py`.
- `DeployReceipt.up_detail` is `StackDetail | None`; `schema_detail` is `SchemaDetail | None` — never `Envelope | None`.
- `asyncssh` imported unconditionally (not behind `TYPE_CHECKING`) in all `admin/remote/` modules.
- `_push_tree` is one module-level private function in `ops.py` (not inlined in two files); `_REMOTE_ENV` declared once.
- `sftp_max_requests` threaded into every `SFTPClient.put(max_requests=cfg.remote.sftp_max_requests)`.
- `RemoteTarget` is `msgspec.Struct(frozen=True, gc=False)`, not `@dataclass`.
- `admin/runtime/rails.py` `CLASSIFY` includes the asyncssh exception rows (verified/extended by the remote pass).
- `git ls-files --cached --exclude-standard -z` is the push manifest; git-lfs posture confirmed before realize.
- Unit test: synthetic `Envelope` bytes decode to `Ok(envelope)`; malformed input yields `BoundaryFault`.
- `guard(RetryClass.HTTP)` wraps `asyncssh.connect`; transient faults retry, terminal faults (`PermissionDenied`/`HostKeyNotVerifiable`) surface as `BoundaryFault.api` immediately.
