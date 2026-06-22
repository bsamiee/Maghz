# [DESIGN_REMOTE] — admin/remote/

Decision-complete design note for the `remote` domain. Working material; the `maghz` CLI and admin source carry binding truth.

---

## [01]-[CONTEXT]

The `remote` domain owns all VPS-facing operations: `exec` (SSH command execution with implicit working-tree push and optional artifact pull) and `deploy` (push + remote `maghz up`/`maghz schema apply` or `down`/`status`). It is the boundary between the local operator and the live Hostinger VPS. No remote surface exists today; all `admin/` rails operate locally. The domain extends the `admin/` package, mounts onto the `maghz` CLI, and emits the canonical `Envelope` on stdout.

Critical existing owners this domain composes and never duplicates:

| Owner | Concern |
| --- | --- |
| `admin/core/model.py` | `Envelope`, `Detail`, `Report`, `Row`, `completed`, `fault` |
| `admin/rails/stack.py` | `StackOp`, `StackDetail`, `run` — identical verbs fire remotely |
| `admin/settings/config.py` | `MaghzSettings`, `RemoteConfig` (new subgroup) |
| `admin/runtime/rails.py` | `BoundaryFault`, `RuntimeRail[T]`, `async_boundary` |
| `admin/runtime/resilience.py` | `RetryClass`, `guard` |
| `admin/__main__.py` | CLI mount point; `_remote` sub-app appended |

Route conflicts to avoid: no second SSH client, no second known-hosts resolver, no parallel deploy verbs. `StackOp` vocabulary already covers `UP`/`DOWN`/`STATUS`; the remote deploy reuses its discriminant, not a new one. `push` is always implicitly part of `exec` and `deploy` — never a standalone user-facing verb or a `RemoteOp` case. `BoundaryFault` + `RuntimeRail[T]` from `admin/runtime/` are the canonical domain-internal rail — no parallel `RemoteFault` StrEnum.

---

## [02]-[OWNERS]

One new package, two files, plus a settings subgroup. The push sub-operation is shared between `exec` and `deploy` — it is NOT single-caller and lives once in `ops.py`, not duplicated.

### `admin/remote/__init__.py`

Beartype claw hook and package re-exports. No logic.

### `admin/remote/connection.py`

Single owner for the asyncssh connection lifecycle and credential projection. Owns:

- `KnownHostsPolicy` — `type KnownHostsPolicy = Literal["insecure"] | Path`. Replaces the bare `str | None` that would silently pass `None` to asyncssh. Lives in `[TYPES]`.
- `RemoteTarget` — `msgspec.Struct(frozen=True, gc=False, kw_only=True)` value object: `host: str`, `port: int`, `user: str`, `known_hosts: KnownHostsPolicy`, `workroot: str`. Derived from `RemoteConfig` at the CLI boundary via `RemoteTarget.from_config`. No computed-property methods — projection to `SSHClientConnectionOptions` is a module-level operation in `[OPERATIONS]`, not embedded on the struct. Lives in `[MODELS]`.
- `target_options(target: RemoteTarget, cfg: RemoteConfig) -> asyncssh.SSHClientConnectionOptions` — builds the ONE typed options object per connection; resolves `KnownHostsPolicy` in a total `match`: `"insecure"` → logs `ssh.host_key_verification_disabled` and sets `known_hosts=None`; `Path as p` → sets `known_hosts=str(p)`. Also sets `connect_timeout`, `login_timeout`, `keepalive_interval`, `keepalive_count_max` from `cfg`. This is the single site where `asyncssh.SSHClientConnectionOptions` is constructed — never `**dict` keyword soup at the call site. Lives in `[OPERATIONS]`.
- `connection(target: RemoteTarget, cfg: RemoteConfig) -> AsyncContextManager[asyncssh.SSHClientConnection]` — `@asynccontextmanager` that calls `asyncssh.connect(host=target.host, port=target.port, username=target.user, options=target_options(target, cfg))` as an async context manager. `guard(RetryClass.HTTP)` wraps the connect call: `ConnectionLost`, `DisconnectError`, and `ChannelOpenError` are retried; `PermissionDenied` and `HostKeyNotVerifiable` surface immediately as `BoundaryFault.api`. No connection pool — the connection is the resource scope for a single CLI operation. Lives in `[OPERATIONS]`.

No `_ConnectionPool`. Connection pooling for an operator CLI tool adds concurrency risk and lifecycle complexity with zero throughput benefit; each `exec` or `deploy` invocation opens one scoped connection under the `anyio` task scope.

### `admin/remote/ops.py`

Single owner for all VPS operations — `exec` and `deploy` — plus the shared push sub-operation. Collapses what would have been two files into one because `_push_tree` is not a single-caller helper; it is shared between both operations. All private sub-operations that are genuinely single-caller remain inline as local closures. Owns:

- `ExecReceipt` — `Detail` subclass (`msgspec.Struct`, frozen, gc=False, `tag="remote_exec"`). Fields: `target: str`, `host: str`, `exit_status: int | None`, `exit_signal: str | None`, `pushed: int`, `pulled: int`, `notes: tuple[str, ...]`. `exit_status: int | None` and `exit_signal: str | None` match `asyncssh.SSHCompletedProcess` exactly. Lives in `[MODELS]`.
- `DeployReceipt` — `Detail` subclass (`msgspec.Struct`, frozen, gc=False, `tag="remote_deploy"`). Fields: `op: StackOp`, `pushed: int`, `push_notes: tuple[str, ...]`, `up_detail: StackDetail | None`, `schema_detail: SchemaDetail | None`. Carries the decoded `StackDetail`/`SchemaDetail` from the remote run, not the full outer `Envelope` wrapper (which is the CLI wire format, not a receipt carrier). `up_detail` populated for `UP`; `schema_detail` populated for `UP` (schema apply follows); both `None` for `DOWN` and `STATUS`. Lives in `[MODELS]`.
- `_push_tree(sftp: asyncssh.SFTPClient, target: RemoteTarget, cfg: MaghzSettings) -> tuple[int, tuple[str, ...]]` — module-level private because called by both `exec` and `deploy`. Runs `anyio.run_process(("git", "ls-files", "--cached", "--exclude-standard", "-z"))` to obtain the NUL-delimited tracked-file manifest (excludes untracked and git-lfs pointer paths via `.gitattributes` `filter=lfs` — see portability note in §09). Fans out per-directory `sftp.put(files, remotedir, max_requests=cfg.remote.sftp_max_requests, error_handler=...)` under `anyio.CapacityLimiter(cfg.remote.sftp_push_concurrency)` inside one `anyio.create_task_group()`. Per-file `SFTPError` folds into notes via `error_handler`. Returns `(pushed_count, notes_tuple)`. Lives in `[OPERATIONS]`.
- `exec(target: RemoteTarget, argv: tuple[str, ...], *, cfg: MaghzSettings) -> Envelope` — one modal-arity entrypoint. Opens a scoped connection via `connection(target, cfg.remote)`, opens SFTP, calls `_push_tree`, runs `conn.run(command, check=True)` — `ProcessError` is caught by `async_boundary("remote.exec", ...)` and lifted to `BoundaryFault.boundary`; non-zero exit that doesn't raise is not possible when `check=True`. Pulls artifacts via `sftp.mget(remote_paths, localpath=local_dir, recurse=True, error_handler=...)`. Projects `SSHCompletedProcess` into `ExecReceipt`. Returns `completed(receipt)` on success; `async_boundary` lifts SSH/SFTP faults to `BoundaryFault` which the CLI boundary projects to `fault(...)`. Lives in `[OPERATIONS]`.
- `deploy(target: RemoteTarget, op: StackOp, cfg: MaghzSettings) -> Envelope` — total `match` + `assert_never` over `StackOp`. `UP`: `_push_tree`, then `conn.run("uv run --project <workroot> python -m admin up", check=True)`, then `conn.run("uv run --project <workroot> python -m admin schema apply", check=True)`, decode both stdout bytes as `msgspec.json.decode(stdout, type=Envelope)`, extract `detail` from each (type-narrowed to `StackDetail` and `SchemaDetail` via `isinstance`), project into `DeployReceipt(op=UP, ..., up_detail=..., schema_detail=...)`. `DOWN` / `STATUS`: run without push, decode, project into `DeployReceipt`. Lives in `[OPERATIONS]`.

The command builder (inline inside `exec` and `deploy`): `cd <workroot> && <env_exports> <argv>` with `shlex.quote` — no subprocess SSH, no shell-pipe SCP.

### `admin/settings/config.py` (subgroup added)

No separate file. `RemoteConfig` is a new pydantic `BaseModel` subgroup on `MaghzSettings`:

```python
class RemoteConfig(BaseModel):
    model_config = _GROUP  # frozen, extra=forbid

    host: str = Field(default="", validation_alias="MAGHZ_REMOTE_HOST")
    port: int = Field(default=22, ge=0, le=65535, validation_alias="MAGHZ_REMOTE_PORT")
    user: str = Field(default="", validation_alias="MAGHZ_REMOTE_USER")
    known_hosts: str = Field(
        default=str(Path("~/.ssh/known_hosts").expanduser()),
        validation_alias="MAGHZ_REMOTE_KNOWN_HOSTS",
    )
    workroot: str = Field(default="~/maghz", validation_alias="MAGHZ_REMOTE_WORKROOT")
    sftp_push_concurrency: int = Field(default=8, ge=1)
    sftp_max_requests: int = Field(default=128, ge=1)
    connect_timeout: float = Field(default=15.0, gt=0)
    keepalive_interval: float = Field(default=15.0, gt=0)
    keepalive_count_max: int = Field(default=3, ge=1)
```

`known_hosts` stays `str` in `RemoteConfig` because it is raw env-var ingress. `RemoteTarget.from_config` converts it to `KnownHostsPolicy`: the literal string `"insecure"` maps to `Literal["insecure"]`; everything else becomes `Path(value)`. The type boundary is at the `RemoteTarget` derivation, not in the pydantic model. `MaghzSettings` gains `remote: RemoteConfig = Field(default_factory=RemoteConfig)`.

---

## [03]-[ADTs]

### `RemoteOp` — the closed remote verb vocabulary

```python
class RemoteOp(StrEnum):
    EXEC = "exec"
    DEPLOY = "deploy"
```

Two cases only. `PUSH` is excluded — push is always implicit in `exec` and `deploy`, never standalone. `PULL` is excluded — pull is always implicit in `exec`. The CLI mounts `exec` and `deploy` as commands; `--op` on `deploy` selects the `StackOp` discriminant.

### `KnownHostsPolicy` — closed typed vocabulary replacing bare `str | None`

```python
type KnownHostsPolicy = Literal["insecure"] | Path
```

Eliminates the `None`-passes-silently bug at the type level. `target_options` matches exhaustively: `case "insecure"` logs warning and passes `known_hosts=None` to `SSHClientConnectionOptions`; `case Path() as p` passes `known_hosts=str(p)`. Total `match` — no `| None` arm because `None` is not in the vocabulary.

### `RemoteTarget` — value object

`msgspec.Struct(frozen=True, gc=False, kw_only=True)`. Fields: `host: str`, `port: int`, `user: str`, `known_hosts: KnownHostsPolicy`, `workroot: str`. `from_config(cfg: RemoteConfig) -> RemoteTarget` is the one factory — a `@classmethod` on the Struct (valid for msgspec) or a module-level function in `connection.py`. No `connect_kwargs: dict` property — that anti-pattern scattered connection options as a raw dict; `target_options(target, cfg)` builds `SSHClientConnectionOptions` directly. No `url: str` property — log context uses `f"{target.user}@{target.host}:{target.port}"` inline; a property carrying only an f-string is a single-caller helper.

The discriminant choice (msgspec Struct vs dataclass vs pydantic): this is a derived value object post-admission with no validation at construction and no cyclic references. `msgspec.Struct(frozen=True, gc=False)` satisfies `OWNER_CHOOSER` row [06] (immutable value types without cycles → `msgspec.Struct`) and eliminates the import of `dataclasses` for a single type.

### `ExecReceipt` and `DeployReceipt` — closed `Detail` cases

```python
class ExecReceipt(Detail, frozen=True, gc=False, tag="remote_exec"):
    target: str
    host: str
    exit_status: int | None
    exit_signal: str | None        # asyncssh SSHCompletedProcess.exit_signal exact type
    pushed: int
    pulled: int
    notes: tuple[str, ...]


class DeployReceipt(Detail, frozen=True, gc=False, tag="remote_deploy"):
    op: StackOp
    pushed: int
    push_notes: tuple[str, ...]
    up_detail: StackDetail | None       # decoded StackDetail from remote up
    schema_detail: SchemaDetail | None  # decoded SchemaDetail from remote schema apply
```

`DeployReceipt` carries `StackDetail | None` and `SchemaDetail | None` — the decoded domain receipts from the remote run, not the full outer `Envelope` wrapper. The outer `Envelope` is the CLI wire format; nesting `Envelope` inside `DeployReceipt` inside another `Envelope` creates redundant status carriers. Downstream consumers read typed evidence directly without re-parsing.

`msgspec.json.decode(stdout_bytes, type=Envelope)` decodes the remote stdout; then `envelope.report.detail` is type-narrowed (via `isinstance` against the known tag) to extract `StackDetail` / `SchemaDetail`. `msgspec.structs.replace` is not needed here since these are read-only receipts.

Total `match` with `assert_never` at every discriminant site: `StackOp` in `ops.deploy`; `RemoteOp` in the CLI sub-app; `KnownHostsPolicy` in `target_options`.

---

## [04]-[.api SURFACE]

### `asyncssh` (catalog: `admin/remote/.api/asyncssh.md`, authored before realize)

The domain-facing slice of `libs/python/runtime/.api/asyncssh.md`, scoped to the ops this domain uses. Authored before any production source.

| Member | Usage |
| --- | --- |
| `asyncssh.connect(host, port=, username=, options=SSHClientConnectionOptions(...))` | `connection()` — one options object, never keyword soup |
| `asyncssh.SSHClientConnectionOptions(known_hosts=, connect_timeout=, login_timeout=, keepalive_interval=, keepalive_count_max=)` | `target_options()` — the one options builder |
| `SSHClientConnection` (async ctx mgr) | the connection resource scope |
| `SSHClientConnection.run(command, check=True, encoding=None)` | remote execution; `check=True` raises `ProcessError` on non-zero exit; caught by `async_boundary` |
| `SSHClientConnection.start_sftp_client()` | SFTP session (async ctx mgr) |
| `SFTPClient.makedirs(path, exist_ok=True)` | remote run-dir creation before push |
| `SFTPClient.put(locals, remotedir, max_requests=cfg.sftp_max_requests, error_handler=...)` | per-directory push fan-out |
| `SFTPClient.mget(remotepaths, localpath=local_dir, recurse=True, error_handler=...)` | artifact pull |
| `asyncssh.get_server_host_key(host, port)` | TOFU bootstrap: fetch and pin the VPS host key on first connect |
| `asyncssh.SSHClientConnectionOptions` | see above |
| `asyncssh.Error`, `asyncssh.DisconnectError`, `asyncssh.ConnectionLost`, `asyncssh.HostKeyNotVerifiable`, `asyncssh.ProcessError`, `asyncssh.SFTPError`, `asyncssh.ChannelOpenError`, `asyncssh.PermissionDenied` | fault taxonomy; `ConnectionLost`/`DisconnectError`/`ChannelOpenError` are retryable via `guard(RetryClass.HTTP)`; `PermissionDenied`/`HostKeyNotVerifiable` are non-retryable → `BoundaryFault.api` |
| `asyncssh.SSHCompletedProcess` (`.exit_status`, `.exit_signal`, `.stdout`, `.stderr`) | receipt projection on `ProcessError` or completed run |
| `asyncssh.set_log_level(level)` / `asyncssh.set_sftp_log_level(level)` | routed into the structlog pipeline once at composition |
| `asyncssh.connect_agent(agent_path=None) -> SSHAgentClient` | ssh-agent client for agent-forwarded credentials on the VPS |
| `asyncssh.read_private_key(filename, passphrase=None) -> SSHKey` | load the Ed25519 private key from settings-model path for explicit `client_keys=` auth |

`asyncssh` is imported unconditionally (not behind `TYPE_CHECKING`). The ruff config disables `TC002` (third-party type-only imports under the beartype claw); `beartype_this_package` resolves annotations at import time. A `TYPE_CHECKING`-guarded asyncssh import would break annotation resolution. Import unconditionally.

No `paramiko`. No `subprocess` SSH. No shell-pipe SCP. No `known_hosts=None` passed directly — only via the `SSHClientConnectionOptions` built by `target_options` after the `KnownHostsPolicy` match. `sftp_max_requests` from `RemoteConfig` threads into every `SFTPClient.put()` call.

### `anyio`

| Member | Usage |
| --- | --- |
| `anyio.create_task_group()` | per-directory push fan-out in `_push_tree` |
| `anyio.CapacityLimiter(n)` | SFTP push concurrency bound (from `RemoteConfig.sftp_push_concurrency`) |
| `anyio.run_process(("git", "ls-files", "--cached", "--exclude-standard", "-z"))` | NUL-delimited tracked-file manifest; `cwd` set to local workroot |

### `admin/runtime/resilience.py` — `guard` and `RetryClass`

`guard(RetryClass.HTTP)` wraps the `asyncssh.connect` call in `connection()`. `RetryClass.HTTP` is the correct class: `ConnectionLost`, `DisconnectError`, `ChannelOpenError` are transient network faults structurally equivalent to `httpx.ConnectError`. The `POLICY[RetryClass.HTTP]` target must cover asyncssh transient exception types (`ConnectionLost`, `DisconnectError`, `ChannelOpenError`) alongside httpx transients; if the policy table's current `target` is typed as a specific httpx exception set, the remote domain's implement pass broadens it to a tuple that includes asyncssh transients within the same `RetryClass.HTTP` policy, or adds `RetryClass.SSH` as a distinct class. The `stamina` policy parameters for `RetryClass.HTTP` already cover SSH transient faults at the timing level (connect_timeout, retries) — no separate retry class is required unless the timing parameters diverge materially. `PermissionDenied` and `HostKeyNotVerifiable` are terminal; they must not appear in `RetryClass.HTTP`'s `target` tuple and surface immediately as `BoundaryFault.api` via `CLASSIFY`.

`guard(RetryClass.SECRET)` wraps keyring credential reads in the remote domain for any VPS path that probes the OS keychain.

### `admin/runtime/rails.py` — `async_boundary` and `RuntimeRail`

`async_boundary("remote.exec", thunk)` and `async_boundary("remote.deploy", thunk)` are the fault-lift points at every SSH/SFTP boundary. `RuntimeRail[T]` = `Result[T, BoundaryFault]` is the domain-internal rail; the CLI boundary projects `Error(BoundaryFault)` to `fault(str(bf), {...})` `Envelope` via the handler in `__main__.py`.

The `CLASSIFY` table in `rails.py` maps `asyncssh.ProcessError` → `boundary`, `asyncssh.SFTPError` → `boundary`, `asyncssh.PermissionDenied` → `api`, `asyncssh.HostKeyNotVerifiable` → `api`, `asyncssh.ConnectionLost`/`DisconnectError` → `resource`, `msgspec.DecodeError` → `boundary`. If asyncssh exceptions are not yet in `CLASSIFY`, the remote domain's `async_boundary` call site adds them as rows — one row per exception family, no new function.

### `msgspec`

`msgspec.json.decode(stdout_bytes, type=Envelope)` decodes remote `maghz` stdout. `ExecReceipt` and `DeployReceipt` are `msgspec.Struct(frozen=True, gc=False)` tagged subclasses of `Detail`. `msgspec.json.encode` is not used directly in this domain — `Envelope.encode()` already owns that. `msgspec.DecodeError` on remote stdout decode lifts via `async_boundary` to `BoundaryFault.boundary`.

---

## [05]-[RAILS + ASPECTS]

### Result/Option rails

`RuntimeRail[T]` = `Result[T, BoundaryFault]` from `admin/runtime/rails.py` for all internal folds. No parallel `RemoteFault(StrEnum)`. `BoundaryFault` already covers the full fault space: `resource` for connection loss, `api` for authentication/host-key denial, `boundary` for command failure and decode error, `deadline` for timeout. Projects to `Envelope` at the CLI boundary via the `__main__.py` handler. No bare `try/except` in domain logic; `async_boundary` is the single conversion point.

### Closed fault vocabulary — `BoundaryFault`

The remote domain adds no new `BoundaryFault` cases. Existing tags cover the entire fault surface:

| asyncssh fault | `BoundaryFault` case |
| --- | --- |
| `ConnectionLost`, `DisconnectError`, `ChannelOpenError` | `resource` |
| `PermissionDenied`, `HostKeyNotVerifiable` | `api` |
| `ProcessError`, `SFTPError`, `msgspec.DecodeError` | `boundary` |
| `anyio.TimeoutError` | `deadline` |

If the `CLASSIFY` table in `admin/runtime/rails.py` does not yet include asyncssh exception types, the remote domain's implement pass adds the rows. This is a seam (see §07).

### anyio structured-concurrency boundary

One `anyio.create_task_group()` per push fan-out (inside `_push_tree`). The exec and deploy operations are otherwise sequential (push → exec → pull; or push → remote up → remote schema apply). `anyio.run` in `__main__.py` is the sole event-loop owner; no nested `asyncio.run`, no `asyncio.gather`.

### @aspect stacking

The `admin/runtime/` aspects own cross-cutting concerns. This domain composes them:

1. `guard(RetryClass.HTTP)` — wraps `asyncssh.connect` in `connection()` for transient reconnect. Applied as a bound caller, not a manual retry loop.
2. `async_boundary("remote.exec" | "remote.deploy" | "remote.push", thunk)` — the single fault-lift point at every SSH/SFTP boundary call. No inline `try/except` in `ops.py` or `connection.py` outside `async_boundary`.
3. `structlog.contextvars.bind_contextvars(rail="remote", op=op_name)` — binds at the entrypoint scope; propagates across anyio task boundaries.

No direct OTel span decoration in this domain. `admin/runtime/receipts.py` (`@receipted`) is the telemetry surface when the automation domain composes the remote operations as `Admit` units.

---

## [06]-[PAYLOADS + TABLES]

### `RemoteConfig` — pydantic `BaseModel` (validated ingress)

Fields listed in §02. `validation_alias` maps `MAGHZ_REMOTE_*` env vars. Admitted once via `MaghzSettings.remote`; beartype claw enforces at call boundaries. `sftp_max_requests` is threaded into `SFTPClient.put(max_requests=cfg.remote.sftp_max_requests)`.

### `RemoteTarget` — msgspec frozen Struct (derived value object)

`msgspec.Struct(frozen=True, gc=False, kw_only=True)`. No computed properties. Projected at admission via `RemoteTarget.from_config(cfg.remote)`. `from_config` converts `cfg.known_hosts: str` to `KnownHostsPolicy`. Projection to `SSHClientConnectionOptions` is `target_options(target, cfg)` in `connection.py`.

### `ExecReceipt(Detail)` — msgspec frozen Struct, gc=False

Tag `"remote_exec"`. `exit_signal: str | None` matches asyncssh exact type. Emitted as `Envelope.report.detail`.

### `DeployReceipt(Detail)` — msgspec frozen Struct, gc=False

Tag `"remote_deploy"`. Carries `up_detail: StackDetail | None` and `schema_detail: SchemaDetail | None` — the decoded domain receipts, not nested `Envelope` objects. Nesting `Envelope` inside `DeployReceipt` inside another `Envelope` creates redundant status carriers and violates the law that `Envelope` is the CLI wire format, not a receipt inner type.

### Correspondence tables

`_RETRY_ON: frozenset[type[asyncssh.Error]]` — the retryable exception set (`ConnectionLost`, `DisconnectError`, `ChannelOpenError`). Module-level constant in `connection.py`, used to configure `RetryClass.HTTP`'s target if the runtime substrate's policy table does not already include these. (Corrected: `frozenset`, not `frozendict`.)

`_REMOTE_ENV: frozendict[str, str]` — minimal env projection forwarded to the remote process: `MAGHZ_DATABASE_DSN` (from `cfg.database.dsn`), `MAGHZ_LOG__FORMAT=json`. Module-level in `ops.py` (once, not duplicated between `exec` and `deploy`). `frozendict` enforces no mutation after construction.

---

## [07]-[DEPS]

### New packages to admit (`pyproject.toml` `dependencies`)

| Package | Band | Why |
| --- | --- | --- |
| `asyncssh>=2.23.1` | runtime | SSHv2 client + SFTP. EPL-2.0 OR GPL-2.0+ (consumed as unmodified library). |

No other new packages. `anyio`, `stamina`, `msgspec`, `pydantic`, `pydantic-settings`, `structlog`, `expression`, `frozendict` are already admitted. `admin/runtime/` substrate is already admitted by the `runtime` domain before this domain realizes.

### `.api` catalog to author before realize

`admin/remote/.api/asyncssh.md` — domain-facing slice: connection with `SSHClientConnectionOptions`, `run(check=True)`/`create_process` exec surface, `SFTPClient.put`/`mget`/`makedirs`, `get_server_host_key` TOFU, `connect_agent`/`SSHAgentClient`, `read_private_key`, and the full fault taxonomy, cited against `asyncssh>=2.23.1`. This is a Maghz-local evidence file referencing but not duplicating the Rasm catalog at `libs/python/runtime/.api/asyncssh.md`. The implement pass writes it before any production source.

---

## [08]-[SEAMS]

### `BoundaryFault` + `RuntimeRail` — remote vs. runtime substrate

The remote domain composes `RuntimeRail[T]` and `BoundaryFault` from `admin/runtime/rails.py` as its sole domain-internal fault rail. No parallel `RemoteFault` StrEnum. The seam is one-directional: `runtime.md` declares the rail; `remote.md` consumes it. When asyncssh exception types are not in the `CLASSIFY` table, the remote implement pass extends `CLASSIFY` with the missing rows — a one-row-per-family extension, no new function.

### `StackOp` — remote vs. local stack rails

`admin/rails/stack.py` owns `StackOp`. `admin/remote/ops.deploy` imports it as the discriminant for remote deploy ops. No copy, no alias. When `StackOp` gains a new case (e.g. `RESTART`), `ops.deploy`'s `match` must extend its arms; `assert_never` catches the gap at static-analysis time.

### `DeployReceipt` — remote vs. existing-rails receipts

`DeployReceipt.up_detail: StackDetail | None` and `schema_detail: SchemaDetail | None` carry the typed receipts decoded from remote stdout. `StackDetail` is owned by `admin/rails/stack.py`; `SchemaDetail` is owned by `admin/rails/schema.py`. Both are imported read-only; the remote domain never re-declares them.

### `KnownHostsPolicy` fix — remote vs. Rasm assay engine

The `KnownHostsPolicy` typed vocabulary in `admin/remote/connection.py` closes the `None`-passes-silently bug at the type level. The analogous fix to Rasm `tools/assay/core/engine.py` `_insecure_host_key` (replacing `str | None` with a typed vocabulary or adding an explicit `case None:` arm logging `"ssh.host_key_verification_disabled"`) is a cross-repo concern that does not block the Maghz remote domain.

### `MaghzSettings` / `RemoteConfig` — settings domain

`RemoteConfig` is a peer subgroup alongside `InfraConfig` under `MaghzSettings`. `InfraConfig` owns local Pulumi state; `RemoteConfig` owns remote SSH facts. `ops.deploy` reads both (infra for stack identity, remote for SSH target).

### `Envelope` — all rails

Every rail in `admin/` emits exactly one `Envelope`. The remote domain emits the same `Envelope` shape and decodes remote `maghz` stdout via `msgspec.json.decode(stdout, type=Envelope)` — never `json.loads` or a hand-rolled parser. `DeployReceipt` carries `StackDetail`/`SchemaDetail` extracted from the decoded remote `Envelope.report.detail`, not the outer `Envelope` itself.

### `ExecReceipt` — remote vs. assay

The Rasm `tools/assay/core/model.py` `ExecReceipt` is a carrier field on `Completed`/`Report` (not a `Detail` subclass) because the assay engine folds multi-outcome fans. The Maghz `ExecReceipt` is a `Detail` subclass because the remote domain emits one receipt per invocation. The shapes are analogous but not shared. Canonical field names `target`/`host`/`exit_status`/`exit_signal`/`pushed`/`pulled`/`notes` must remain stable across both.

### `CLASSIFY` extension — remote vs. runtime

The `CLASSIFY: Final[tuple[...]]` in `admin/runtime/rails.py` maps exception families to `BoundaryFault` builders. The remote implement pass verifies asyncssh's exception types are present as rows and adds any missing entries. The canonical rows required are:
```
(asyncssh.ProcessError, asyncssh.SFTPError)                  → boundary
(asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable)   → api
(asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.ChannelOpenError) → resource
```
These rows must appear before the `(OSError,)` catch-all and before `(Exception,)`. The `runtime` domain owns `CLASSIFY`; the remote implement pass extends it by editing `admin/runtime/rails.py` in place — no new function, no parallel table.

### `cloud-sync` restore — remote vs. cloud-sync

`cloud-sync`'s `run(CloudOp.RESTORE, cfg)` is the data-recovery primitive for the remote domain's deploy sequence. Remote deploy (`deploy(target, StackOp.UP, cfg)`) invokes `maghz cloud restore` (via SSH `conn.run`) followed by `maghz schema apply` as the post-restore sequence on the VPS. The DSN configuration (`MaghzSettings.database.dsn`) and keyring/env-var credential surface are shared; `RemoteConfig` and `CloudConfig` both read from `MaghzSettings`. `StackOp` gaining a new case (e.g. `RESTART`) requires `ops.deploy`'s `match` to extend with a new arm; `assert_never` catches any gap at type-check time.

---

## [09]-[PORTABILITY / VPS]

### Hostinger VPS topology

The live Hostinger VPS runs the same Docker Compose stack (`maghz-db`, `maghz-ollama`) provisioned by the remote Pulumi run. `MaghzSettings` is configured on the VPS via `.env` (gitignored) or env vars injected at deploy time. The `maghz` CLI is installed from the repo's `pyproject.toml` entry point via `uv`.

### Bootstrap sequence (one-time, per VPS)

1. `asyncssh.get_server_host_key(host, port)` fetches the VPS host key; the operator pins it into `~/.ssh/known_hosts` or a dedicated `MAGHZ_REMOTE_KNOWN_HOSTS` path (TOFU). Returns `SSHKey | None` — `None` means the host returned no key, which should abort, not proceed.
2. SSH key auth: a dedicated Ed25519 keypair is generated locally via `asyncssh.generate_private_key("ssh-ed25519")` and `asyncssh.read_private_key(path)` for load. Public key is added to the VPS `~/.ssh/authorized_keys`. `SSHClientConnectionOptions` takes `client_keys=[key]` or defers to `ssh-agent` via `asyncssh.connect_agent()`.
3. `MAGHZ_REMOTE_HOST`, `MAGHZ_REMOTE_USER`, and `MAGHZ_REMOTE_WORKROOT` are set in the local `.env` (gitignored) before `maghz deploy`.
4. `MAGHZ_REMOTE_KNOWN_HOSTS` defaults to `~/.ssh/known_hosts`. Setting it to `"insecure"` disables host key verification (dev only; logs a warning via `ssh.host_key_verification_disabled`).
5. ssh-agent: on the VPS, `asyncssh.connect_agent()` opens the agent if `SSH_AUTH_SOCK` is set; `SSHClientConnectionOptions(client_keys=await agent.get_keys())` enables agent-backed auth without copying private keys to the VPS.

### Git-lfs and push manifest

`anyio.run_process(("git", "ls-files", "--cached", "--exclude-standard", "-z"))` enumerates tracked files. If the repo contains git-lfs tracked paths (declared in `.gitattributes` with `filter=lfs`), `git ls-files` will return the lfs pointer files, not the binary objects. The push will transfer the pointer files (a few hundred bytes each) but not the actual binary. Before realize, confirm whether the Maghz repo uses git-lfs; if it does, add a `--exclude` filter via `.gitattributes` `export-ignore` attribute or a post-manifest filter step that skips lfs-tracked paths. If the repo does not use git-lfs, the standard manifest is correct.

### Token cache policy

No OP service account token or device-code flow is required for SSH auth — key-based auth and ssh-agent are the exclusive mechanisms. All credential paths are gitignored; the `gitleaks` gate checks on commit.

### On-VPS operator account

The `maghz` CLI runs as a non-root UNIX user (`maghz` or provisioned user) with Docker socket access via `docker` group membership. No `sudo`. The remote `workroot` (default `~/maghz`) is owned by the operator user.

### VPS `maghz` invocation

After `_push_tree` transfers the working tree to the VPS workroot, the deploy step runs `uv run --project ~/maghz python -m admin <subcommand>` inside the pushed working tree. `uv` is pre-installed on the VPS by the bootstrap. `pyproject.toml` is part of the pushed manifest (it is tracked by git). The command is built via `shlex.quote` composition, never string interpolation without quoting.

---

## [10]-[ACCEPTANCE]

- `ruff check admin/remote/ --select=ALL` — zero diagnostics (same ignore table as `pyproject.toml`).
- `ty check admin/remote/` — zero errors (the binding type gate; `asyncssh` must have stubs or `# type: ignore[import-untyped]` handled by the ignore table).
- `mypy admin/remote/` — advisory; zero errors under `strict=True` with the existing `pg8000` override pattern extended to `asyncssh` if stubs are absent.
- `asyncssh` admitted in `pyproject.toml` `dependencies`; `uv lock` regenerates cleanly.
- `asyncssh.connect()` called with `options=SSHClientConnectionOptions(...)` via `target_options()` — never with raw `**dict` keyword soup. Every call site routes through `target_options`.
- `conn.run(command, check=True)` — non-zero exit raises `asyncssh.ProcessError`; caught by `async_boundary`; never manually inspected via `exit_status` field check.
- `target_options` `match policy:` — `case "insecure":` and `case Path() as p:` — exhaustive, no bare `None` arm.
- `match op: case StackOp.UP: ... case StackOp.DOWN: ... case StackOp.STATUS: ... case _ as unreachable: assert_never(unreachable)` — exhaustive arms in `ops.deploy`.
- No `RemoteFault` StrEnum anywhere in `admin/remote/`. All fault paths use `BoundaryFault` from `admin/runtime/rails.py`.
- `DeployReceipt.up_detail` is `StackDetail | None`; `DeployReceipt.schema_detail` is `SchemaDetail | None` — not `Envelope | None`.
- `asyncssh` imported unconditionally (not behind `TYPE_CHECKING`) in all `admin/remote/` modules.
- `_push_tree` is a module-level private function in `ops.py`, not inlined separately in two files.
- `_REMOTE_ENV: frozendict[str, str]` declared once in `ops.py`; not duplicated.
- `sftp_max_requests` threaded into `SFTPClient.put(max_requests=cfg.remote.sftp_max_requests)`.
- `RemoteTarget` is `msgspec.Struct(frozen=True, gc=False)`, not `@dataclass`.
- `admin/runtime/rails.py` `CLASSIFY` includes asyncssh exception rows; remote implement pass verifies and extends if absent.
- `git ls-files --cached --exclude-standard -z` is the push manifest command; git-lfs posture confirmed before realize.
- Remote `maghz` stdout decode: a unit test feeds synthetic `Envelope` bytes and asserts the decode returns `Ok(envelope)` with `BoundaryFault` on malformed input.
- `guard(RetryClass.HTTP)` wraps `asyncssh.connect` in `connection()`; transient faults retry; terminal faults surface as `BoundaryFault.api` immediately.
