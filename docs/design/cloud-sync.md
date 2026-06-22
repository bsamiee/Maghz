# [DESIGN_NOTE: cloud-sync]

Decision-complete design blueprint for the `cloud-sync` domain. Working material; the schema, the `maghz` CLI, and the implementation source carry binding truth once realized.

---

## [01]-[CONTEXT]

The cloud-sync domain owns durable off-site backup and bidirectional content synchronization for the Maghz second brain. It drives the `rclone` CLI (v1.74.3+) to replicate the PostgreSQL ledger dump and the Heptabase content tree to two remotes simultaneously — Google Drive and OneDrive — and owns the restore path. The Sync automation action invokes the domain; the domain emits a typed `CloudSyncDetail` receipt into the `Envelope` contract shared by all rails. The surface works identically on the local machine and on the Hostinger VPS (op service account with pre-authorised token caches).

**What already exists and must be extended:**
- `admin/rails/sync.py` — owns Heptabase card reconciliation (not cloud backup). Name collision risk: the existing `sync` sub-app and `sync_diff`/`sync_generate` re-exports in `admin/rails/__init__.py` occupy the `sync` command namespace. The cloud-sync rail MUST mount under a distinct sub-app — `cloud` — so `maghz cloud sync`, `maghz cloud restore`, and the automation entry point are unambiguous.
- `admin/__main__.py` — the cyclopts entrypoint; the `cloud` sub-app registers here exactly as `_schema` and `_sync` do.
- `admin/core/model.py` — `Detail`, `Envelope`, `completed`, `fault`, `Status` are the shared receipt contract; `CloudSyncDetail` extends `Detail` with tag `"cloud"`.
- `admin/settings/config.py` — `MaghzSettings` must gain one new nested model `CloudConfig`; env prefix `MAGHZ_CLOUD__*`; no other config file.
- `admin/db.py` — `query` + `DbFault` + `Boundary` are shared; `Boundary` is NOT extended here. The cloud-sync domain owns its own closed `CloudBoundary` fault vocabulary in `cloud.py`.
- `admin/runtime/resilience.py` — `guard(RetryClass.PROC)` and `guard(RetryClass.SECRET)` are the retry primitives this domain composes. No standalone `@stamina.retry(...)` in `cloud.py`.
- `admin/runtime/lanes.py` — `LanePolicy.drain(Block.of_seq([Admit.retried(RetryClass.PROC, work)]))` with a `create_memory_object_stream` result channel is the concurrent fan-out primitive. No `asyncio.gather`, no `except* _CloudError`.

---

## [02]-[OWNERS]

One new file; two settings additions; no new standalone modules.

| [FILE] | [SECTION] | [OWNS] |
| --- | --- | --- |
| `admin/rails/cloud.py` | `[TYPES]` | `CloudOp` (StrEnum, closed verb vocabulary); `Remote` (StrEnum, `drive`, `onedrive`); `CloudBoundary` (type alias, closed fault vocabulary) |
| `admin/rails/cloud.py` | `[MODELS]` | `CloudSyncDetail` (Detail subclass, tag `"cloud"`, typed receipt); `_RcloneLogLine` (msgspec.Struct, outer rclone JSON log line wrapper); `_RcloneStats` (msgspec.Struct, rclone stats sub-object decoded from `_RcloneLogLine.stats`) |
| `admin/rails/cloud.py` | `[ERRORS]` | `CloudFault` (msgspec.Struct, carries `op: CloudBoundary`) |
| `admin/rails/cloud.py` | `[TABLES]` | `_BUILD` (frozendict: `CloudOp` → async coroutine builder) |
| `admin/rails/cloud.py` | `[OPERATIONS]` | `_env_for(remote, cfg) -> Mapping[str, str]` — assembles subprocess env; `_rclone(*argv, env, timeout_s) -> Result[_RcloneStats, CloudFault]` — single subprocess boundary returning a typed rail; `run(op, cfg) -> Envelope` — one polymorphic entrypoint |
| `admin/settings/config.py` | `[MODELS]` | `RemoteConfig` — per-remote OAuth credentials; `CloudConfig` — remote paths, content root, filter file, timeout, force-resync, keyring service |
| `admin/settings/config.py` | `[MODELS]` | `MaghzSettings.cloud: CloudConfig` — new field |
| `admin/__main__.py` | `[COMPOSITION]` | `_cloud` sub-app + `cloud sync` and `cloud restore` command registrations |
| `admin/rails/__init__.py` | `[EXPORTS]` | `CloudOp`, `run as cloud` re-export |

The single conceptual concern (drive rclone to back up and restore the maghz system) lives entirely in `admin/rails/cloud.py`. No helper file, no second rail file, no parallel `backup.py` / `restore.py`.

---

## [03]-[ADTs]

### `CloudOp` — the closed verb vocabulary

```python
class CloudOp(StrEnum):
    SYNC    = "sync"    # pg_dump + content bisync to both remotes
    RESTORE = "restore" # pg_restore from remote dump + content bisync back
```

Total match exhaustion is mandatory at every `match op` arm with `assert_never` on the fallthrough. The `_BUILD` dispatch table eliminates imperative branching: every arm is a row.

Anticipatory shape: when `VERIFY` (rclone check without sync), `PRUNE` (remove old dumps), or `STATUS` (list remotes + token check) land, each is one new `CloudOp` case and one new `_BUILD` row. No structural change to `run`, `CloudSyncDetail`, or `CloudBoundary`.

### `Remote` — the closed remote vocabulary

```python
class Remote(StrEnum):
    DRIVE    = "drive"
    ONEDRIVE = "onedrive"
```

`remote.value` IS the rclone remote name (the `RCLONE_CONFIG_<REMOTE>_*` env var prefix key). `CloudConfig.remotes` is typed `frozendict[Remote, RemoteConfig]` — the enum is the key, never a bare string. All iteration over remotes uses `tuple(Remote)`.

### `CloudBoundary` — the closed fault vocabulary

```python
type CloudBoundary = Literal["rclone", "pg_dump", "pg_restore", "spawn"]
```

Lives as its own type alias in `cloud.py`; it does NOT extend `admin.db.Boundary`. `CloudFault.op` carries one case, never a bare string. `"spawn"` covers `OSError` on `anyio.run_process` (missing binary or path issue); the other three cases carry the rclone and pg tool exit failures.

### Modal-arity entrypoint

`run(op: CloudOp, cfg: MaghzSettings, /) -> Envelope` is the ONE entrypoint. No `sync(cfg)` / `restore(cfg)` sibling names. `op` is the discriminant; `_BUILD[op]` selects the coroutine; no flag parameters or mode knobs.

---

## [04]-[.api SURFACE]

### `anyio` (`libs/python/.api/anyio.md`)

- `anyio.run_process(command, *, input=None, check=False, env=None, cwd=None)` — the sole subprocess driver for both rclone and pg_dump/pg_restore. `check=False` is mandatory so the boundary adapter owns exit-code interpretation; the caller lifts non-zero exits into `Error(CloudFault(...))` on the closed-fault rail.
- `anyio.create_task_group()` — NOT used for fan-out directly. Fan-out is through `LanePolicy.drain` from `admin/runtime/lanes.py`, which internally uses `create_task_group`. The domain never opens a raw task group.
- `anyio.fail_after(timeout)` — wraps the entire sync or restore operation at the `run` boundary; configurable from `CloudConfig.op_timeout_s`. Never a raw `asyncio.wait_for`.
- `anyio.create_memory_object_stream[Result[_RemoteResult, CloudFault]](max_buffer_size=len(remotes))` — the in-drain result channel collecting typed per-remote outcomes. Results accumulate in the stream; the `run` function reads them after the drain completes and folds into `CloudSyncDetail`. This is the correct concurrency model for accumulating multi-remote results — NOT `except*` over a private exception class.
- `anyio.Path(binary).exists()` — pre-flight check for `rclone`, `pg_dump`, `pg_restore` availability before the operation fires; missing binary lifts to `Error(CloudFault(op="spawn", ...))` before any subprocess call.

`anyio.TemporaryDirectory()` does NOT exist in the anyio API. The dump staging directory uses `tempfile.TemporaryDirectory()` (sync stdlib) entered via `contextlib.AsyncExitStack.enter_async_context(contextlib.asynccontextmanager(lambda: tmp).__call__())` — the correct form is:

```python
# in the sync builder, inside run's anyio.fail_after scope
async with AsyncExitStack() as stack:
    tmp = stack.enter_context(tempfile.TemporaryDirectory())
    # ... pg_dump into tmp, rclone copy from tmp, ...
```

The `AsyncExitStack.enter_context` (sync context manager) plus `with anyio.CancelScope(shield=True)` in `finally` ensures cleanup under cancellation.

Currently, `admin/rails/schema.py` hand-rolls a sequential `[await anyio.run_process(...) for _, argv in steps]` pattern. The cloud-sync domain must not copy that pattern for multi-remote dispatch; it MUST use `LanePolicy.drain` for the concurrent remote fan-out.

### `admin/runtime/resilience.py` — retry composition

The cloud-sync domain does NOT declare its own `@stamina.retry(...)` decorator. It composes `guard(RetryClass.PROC)` from `admin/runtime/resilience.py`, which returns a `BoundAsyncRetryingCaller` memoised per class. The rclone rate-limit exit code 7 case requires a `BackoffHook` override. Two options:

Option A (preferred): extend `resilience.py` with a `RetryClass.CLOUD_RCLONE` case whose `Policy` carries a `BackoffHook` that discriminates on exit code 7 via `CloudFault.exit_code`. The backoff hook inspects `exc` (where `exc` is a temporarily-raised sentinel for the exit-code case, or structured differently per the existing `PROC` hook surface). This keeps the policy table as the single location for retry policy.

Option B (if `RetryClass` is not extended): use `guard(RetryClass.PROC)` for spawn-level `OSError` faults, and wrap `_rclone` with a local `@stamina.retry(on=_rclone_transient, ...)` where `_rclone_transient` is the ONLY private retry hook — this is acceptable when the `PROC` class does not have the domain specificity needed for rclone exit code 7. In this case the hook does NOT produce an intermediate exception class: `_rclone` raises `_RcloneTransient(CloudFault)` only for code 7, and the backoff hook returns `60.0` for it. No `_RcloneRateLimit(Exception)` separate wrapper class; the sentinel IS the `CloudFault` subclass.

The blueprint commits to Option B since `RetryClass.PROC` covers `OSError` (spawn) generically but lacks the 60-second rate-limit backoff specific to rclone exit code 7. One private named hook function; no intermediate exception class beyond the already-declared `CloudFault` hierarchy.

```python
# [TYPES] — private sentinel for rate-limited rclone exits
class _RcloneTransient(Exception):
    """Raised only for rclone exit code 7 (rate-limit); carries the CloudFault for the hook."""
    fault: CloudFault

def _rclone_transient_hook(exc: Exception, /) -> bool | float:
    if isinstance(exc, _RcloneTransient):
        return 60.0  # rate-limit: override wait
    if isinstance(exc, OSError):
        return True  # spawn failure: exponential backoff
    return False
```

`_RcloneTransient` is single-purpose but justified: the backoff hook API requires a raised exception to discriminate the retry strategy — it cannot inspect a `Result.Error` value. This is the named platform-forced seam. The `_RcloneTransient` class carries a `CloudFault` reference so the handler at the `run` boundary can project it without re-constructing the fault.

`stamina.instrumentation.StructlogOnRetryHook` remains active (registered at process startup in `__main__.py`); no per-rail hook setup.

### `admin/runtime/lanes.py` — fan-out

`LanePolicy.drain(Block.of_seq([Admit.retried(RetryClass.PROC, work_for_remote) for remote in Remote]))` with a `create_memory_object_stream` result channel is the concurrent fan-out. Each child work unit:
1. Calls `_rclone` for the content bisync on that remote.
2. For `CloudOp.SYNC` only: also calls `_rclone` for the dump copy on that remote.

Both calls per remote are sequential within the child (dump copy then bisync, or bisync then dump copy per design decision in [06]).

`DrainReceipt[_RemoteResult]` accumulates both per-remote outcomes; the `run` function folds the `DrainReceipt.values` block into `CloudSyncDetail` after the drain completes.

### `msgspec` (`libs/python/.api/msgspec.md`)

- `msgspec.Struct(frozen=True, tag="cloud", gc=False)` — `CloudSyncDetail` wire receipt.
- `msgspec.Struct(frozen=True, gc=False)` — `_RcloneLogLine`: the outer wrapper for rclone `--use-json-log` lines. Fields: `level: str = ""`, `msg: str = ""`, `stats: _RcloneStats | None = None`. Decoded from rclone's stderr line-by-line; a line without a `stats` key decodes but `stats` is `None`, skipped.
- `msgspec.Struct(frozen=True, gc=False)` — `_RcloneStats`: the inner stats sub-object. Fields: `transferred: int = 0`, `errors: int = 0`, `checks: int = 0`, `elapsedTime: float = 0.0` (rclone camelCase). Decoded from `_RcloneLogLine.stats` (not from the top-level log line directly).
- `msgspec.Struct(frozen=True, gc=False)` — `_RemoteResult`: the per-remote result collected from each drain child. Fields: `remote: Remote`, `stats: _RcloneStats`, `dump_path: str | msgspec.UnsetType = msgspec.UNSET`.
- Parse strategy: split stderr into lines, call `msgspec.json.decode(line.encode(), type=_RcloneLogLine)` inside `try/except msgspec.DecodeError`, collect lines where `line_obj.stats is not None`, accumulate stats from all such lines (last wins for `elapsedTime`, sum for `transferred`/`errors`/`checks`). A `msgspec.DecodeError` on a line is silently skipped; if no stats line decodes, yield `_RcloneStats()` as a zero-sentinel.

The two-struct parse (`_RcloneLogLine` wrapping `_RcloneStats`) is the CORRECT model: rclone `--use-json-log` emits `{"level":"info","msg":"Transferred:","stats":{"transferred":N,...}}` — the stats object is nested under the `"stats"` key.

- `msgspec.json.encode(envelope)` — existing contract, no change.
- `msgspec.UNSET` / `msgspec.UnsetType` — used for `CloudSyncDetail.dump_path` and `CloudSyncDetail.restored_from` to distinguish explicit absence (not applicable for this op) from a null value.

### `rclone` CLI (v1.74.3, no Python library — subprocess boundary only)

The rclone CLI is configured entirely through `RCLONE_CONFIG_<REMOTE>_<KEY>=value` environment variables passed as `env=` to `anyio.run_process`. No `rclone.conf` file is written or read; the token JSON blobs are supplied via the env var `RCLONE_CONFIG_<REMOTE>_TOKEN=<json>`, obtained from `keyring` at call time.

**Per-remote env vars** (assembled by `_env_for(remote, cfg)` for each `Remote` case, returns `Mapping[str, str]`):
- `RCLONE_CONFIG_<REMOTE.value.upper()>_TYPE` → `remote.value` (drive / onedrive)
- `RCLONE_CONFIG_<REMOTE.value.upper()>_CLIENT_ID` → `cfg.cloud.remotes[remote].client_id`
- `RCLONE_CONFIG_<REMOTE.value.upper()>_CLIENT_SECRET` → `cfg.cloud.remotes[remote].client_secret`
- `RCLONE_CONFIG_<REMOTE.value.upper()>_TOKEN` → token from `keyring.get_password(cfg.cloud.keyring_service, remote.value)` first; falls back to `cfg.cloud.remotes[remote].token` (VPS env path) when keyring returns `None`.
- Drive only: `RCLONE_CONFIG_DRIVE_SCOPE=drive`; Drive credential strategy: service account JSON via `RCLONE_CONFIG_DRIVE_SERVICE_ACCOUNT_CREDENTIALS` env var (base64-encoded JSON) — no user OAuth token needed, no token refresh problem.
- OneDrive only: `RCLONE_CONFIG_ONEDRIVE_DRIVE_ID` → `cfg.cloud.remotes[remote].drive_id`; OneDrive credential strategy: client credentials flow (`RCLONE_CONFIG_ONEDRIVE_CLIENT_SECRET` + `RCLONE_CONFIG_ONEDRIVE_TOKEN` with a long-lived service-account token obtained via `az ad sp` grant with `Files.ReadWrite.All` scope) — no interactive device-code flow on VPS.

**`CloudOp.SYNC` sequence (per `run` call):**

1. Pre-flight: `anyio.Path(binary).exists()` for `rclone`, `pg_dump`. Fail immediately on missing binary.
2. Open `AsyncExitStack`; enter `tempfile.TemporaryDirectory()` (sync context manager via `stack.enter_context`).
3. Run `pg_dump` sequentially (one process, one `_rclone`-like boundary call): `pg_dump <DSN> -F c -Z zstd:3 -f <tmp_dir>/<timestamp>_maghz.dump -O --no-privileges`. Lift failure to `Error(CloudFault(op="pg_dump", ...))`.
4. Fan out via `LanePolicy.drain` to BOTH remotes concurrently. Each drain child runs in sequence:
   a. `rclone copy <tmp_dir>/<dump_file> <remote>:<remote_dump_path>` (dump upload).
   b. `rclone bisync <content_root> <remote>:<remote_content_path> [flags]` (content sync).
   Each child collects a `_RemoteResult(remote=remote, stats=summed_stats, dump_path=<remote:path>)`.
5. Fold `DrainReceipt.values` into `CloudSyncDetail`.

**`CloudOp.RESTORE` sequence:**

1. Pre-flight: `rclone`, `pg_restore`.
2. Open `AsyncExitStack`; enter `tempfile.TemporaryDirectory()`.
3. Download latest dump from the primary remote (Drive first, fallback to OneDrive if empty): `rclone copy <remote>:<remote_dump_path>/<dump_file> <tmp_dir>/`.
4. `pg_restore -d <DSN> -c -O --no-privileges <tmp_dir>/<dump_file>`. Lift to `Error(CloudFault(op="pg_restore", ...))`.
5. Fan out bisync to BOTH remotes with `--resync` flag (always on restore). Collect `_RemoteResult` per remote.
6. Fold into `CloudSyncDetail(op=CloudOp.RESTORE, restored_from=<remote:path/dump_file>, ...)`.

**Sync verb — content bisync flags:**
```
rclone bisync <content_root> <remote>:<remote_content_path>
  --resync-mode path1            # local wins on first resync
  --conflict-resolve newer       # newer file wins on conflicts
  --conflict-loser pathname      # loser renamed with --conflict-suffix
  --conflict-suffix conflict     # loser renamed with this suffix
  --resilient                    # survive transient errors, retry next run
  --recover                      # auto-recover from interrupted runs
  --filters-file <filter_file>   # exclude .DS_Store, __pycache__, .venv, etc.
  --check-access                 # abort if RCLONE_TEST marker file absent
  --use-json-log                 # structured stderr for _RcloneStats parse
  --stats 0                      # emit one summary stats line at end only
  --log-level INFO
  [--resync]                     # if CloudOp.RESTORE or cfg.cloud.force_resync
```

**rclone exit codes** (authoritative for `CloudBoundary` fault mapping):
- `0` — success
- `1` — syntax / usage error; non-retriable
- `5` — temporary error; retriable via `RetryClass.PROC`
- `7` — too many errors (rate-limit); retriable with 60 s override via `_rclone_transient_hook`
- `8` — transfer limit exceeded; non-retriable
- `9` — successful but no files transferred; NOT a fault (treat as success)

### `keyring` (`admin/settings/config.py` already admits it)

- `keyring.get_password(service, username)` — retrieve OAuth token JSON blobs and client secrets at call time (never at import time). Called from `_env_for(remote, cfg)`. On the VPS where `keyring` resolves to the null keyring, tokens are supplied via env vars (`MAGHZ_CLOUD__REMOTES__DRIVE__TOKEN`, `MAGHZ_CLOUD__REMOTES__ONEDRIVE__TOKEN`) read through `RemoteConfig` fields with empty-string defaults, then merged into the subprocess env via `_env_for`.

---

## [05]-[RAILS + ASPECTS]

### Rail selection

The cloud-sync domain runs on `Result[_RemoteResult, CloudFault]` per drain child, and `Result[CloudSyncDetail, CloudFault]` at the `run` boundary. `run` lifts to `Envelope` at the single boundary point using `completed`/`fault` from `admin.core`. No bare exceptions escape `_rclone`; `OSError` (spawn, including missing binary) and non-zero exit are both lifted to `Error(CloudFault(...))`.

### Closed fault vocabulary

```python
type CloudBoundary = Literal["rclone", "pg_dump", "pg_restore", "spawn"]

class CloudFault(msgspec.Struct, frozen=True, gc=False):
    op: CloudBoundary
    message: str
    remote: Remote | None = None    # which remote failed (None for pg_ tools and spawn)
    exit_code: int | None = None    # rclone/pg tool exit code for structlog context
```

Never a bare `str` for `op`; never a generic `Exception` message left unwrapped.

### Concurrency model — `LanePolicy.drain` over `create_memory_object_stream`

Fan-out over both remotes uses `LanePolicy.drain(Block.of_seq([Admit.retried(RetryClass.PROC, _work(remote)) for remote in Remote]))`. Each work unit is an async callable that returns `Result[_RemoteResult, CloudFault]`. The drain collects results into a `DrainReceipt[_RemoteResult]`; `DrainReceipt.values` is the `Block[_RemoteResult]` of successful results; `DrainReceipt.faults` carries any `BoundaryFault` lifted from retry exhaustion.

NO `except* _CloudError`. NO `_CloudError(Exception)` wrapper class. Results accumulate through the drain's memory-object-stream; the `run` function folds `DrainReceipt.values` after the drain. A partial failure (one remote's drain child exhausted retries) is reported as `Status.FAILED` with `Row` items naming which remote failed; the other remote's result is present in the receipt.

The `run` function opens `anyio.fail_after(cfg.cloud.op_timeout_s)` around the entire operation (pg_dump + drain). A deadline trip surfaces as `anyio.get_cancelled_exc_class()` and propagates — it is NOT caught into a `Result.Error`. The domain acknowledges this: a deadline trip is a process-level failure, not a `CloudFault`. The CLI handler in `__main__.py` catches `anyio.get_cancelled_exc_class()` as a generic fault envelope.

### `stamina` retry aspect — backoff hook

```python
class _RcloneTransient(Exception):
    """Raised inside _rclone when exit code is 7; carries the CloudFault for projection."""
    def __init__(self, fault: CloudFault) -> None:
        self.fault = fault
        super().__init__(str(fault))

def _rclone_transient_hook(exc: Exception, /) -> bool | float:
    if isinstance(exc, _RcloneTransient):
        return 60.0        # exit code 7: override wait to 60 s
    if isinstance(exc, OSError):
        return True        # spawn failure: exponential backoff
    return False           # any other exception: non-retriable
```

`_rclone` is decorated with `@stamina.retry(on=_rclone_transient_hook, attempts=3, wait_initial=2.0, wait_max=30.0, wait_jitter=1.0)`. This is the ONLY retry path. `_RcloneTransient` is justified as the named platform-forced seam: the `BackoffHook` API receives an `Exception` instance — a `Result.Error` value cannot be inspected at retry hook time.

`stamina.instrumentation.StructlogOnRetryHook` remains active (registered at process startup in `__main__.py`). No per-rail hook setup.

### Cross-cutting aspects (stacking order on `_rclone`)

1. `@stamina.retry(on=_rclone_transient_hook, ...)` — outermost: resilience boundary; each attempt starts fresh.
2. `anyio.fail_after(cfg.cloud.op_timeout_s)` — deadline scope wrapping `run`; the deadline applies across all drain work, not per-attempt.
3. `structlog.contextvars.bound_contextvars(remote=remote.value, op=op.value)` — context bound before the drain, inside each drain work unit.
4. `_rclone` body: exit-code lift to `Error(CloudFault(...))` or `_RcloneTransient(CloudFault(...))` for exit code 7 (innermost).

---

## [06]-[PAYLOADS + TABLES]

### `CloudSyncDetail` — the typed receipt

```python
class CloudSyncDetail(Detail, frozen=True, tag="cloud", gc=False):
    op: CloudOp
    remotes: tuple[Remote, ...]             # which remotes were targeted
    transferred: int = 0                    # total files transferred (sum across remotes)
    errors: int = 0                         # total rclone errors (sum)
    checks: int = 0                         # total files checked (sum)
    elapsed_s: float = 0.0                  # wall time for the full operation
    dump_path: str | msgspec.UnsetType = msgspec.UNSET   # remote:path the dump was written to (sync only)
    restored_from: str | msgspec.UnsetType = msgspec.UNSET  # remote:path dump was read from (restore only)
```

`dump_path` and `restored_from` use `msgspec.UNSET` (not `None`) for explicit absence — aligning with `SyncDetail.card_id` / `card_total` pattern in `existing-rails.md`. `msgspec.UNSET` is distinct from `null` on the wire; `omit_defaults=True` would suppress them entirely, but here explicit absence is preferred for receipt clarity. The `match op` arm in `_BUILD` fills only the relevant field.

Never a generic `dict` or `Mapping`; every field carries domain evidence.

### `_RcloneLogLine` and `_RcloneStats` — subprocess wire decode

```python
class _RcloneStats(msgspec.Struct, frozen=True, gc=False):
    transferred: int = 0
    errors: int = 0
    checks: int = 0
    elapsedTime: float = 0.0  # rclone JSON field name (camelCase)

class _RcloneLogLine(msgspec.Struct, frozen=True, gc=False):
    level: str = ""
    msg: str = ""
    stats: _RcloneStats | None = None  # present only on stats-bearing log lines
```

Decoded from rclone's `stderr` when `--use-json-log --stats 0` is active. The outer `_RcloneLogLine` wrapper is mandatory because rclone wraps stats inside a log-line envelope (`{"level":"info","msg":"...","stats":{...}}`). Parse strategy: split stderr into lines, decode each as `_RcloneLogLine` inside `try/except msgspec.DecodeError` (skip failures), collect lines where `.stats is not None`, sum `transferred`/`errors`/`checks`, take the last `elapsedTime`. If no stats line decodes, yield `_RcloneStats()` as a zero-sentinel.

### `_RemoteResult` — per-remote drain result

```python
class _RemoteResult(msgspec.Struct, frozen=True, gc=False):
    remote: Remote
    stats: _RcloneStats
    dump_path: str | msgspec.UnsetType = msgspec.UNSET  # set for sync op dump upload only
```

Collected from each drain child via the memory-object-stream; folded into `CloudSyncDetail` by the `run` boundary.

### `RemoteConfig` — per-remote credentials model

```python
class RemoteConfig(BaseModel):
    model_config = _GROUP

    client_id: str = ""
    client_secret: str = ""
    token: str = ""                  # MAGHZ_CLOUD__REMOTES__DRIVE__TOKEN (VPS env path; keyring is primary)
    drive_id: str = ""               # OneDrive only: personal drive ID
    service_account_credentials: str = ""  # Drive only: base64-encoded JSON service account key
```

`service_account_credentials` is Drive-specific and empty for OneDrive. `drive_id` is OneDrive-specific and empty for Drive. The `_env_for` boundary adapter ignores irrelevant fields per remote.

### `CloudConfig` — settings model

```python
class CloudConfig(BaseModel):
    model_config = _GROUP

    remotes: frozendict[Remote, RemoteConfig] = Field(
        default_factory=lambda: frozendict({r: RemoteConfig() for r in Remote})
    )
    remote_content_path: str = "maghz/content"     # path on each remote for content tree
    remote_dump_path: str = "maghz/dumps"           # path on each remote for pg_dump files
    content_root: Path = Path(".")                  # local Heptabase content root
    filter_file: Path = Path(".rclone-filter")      # bisync filter rules file
    op_timeout_s: float = Field(default=3600.0, gt=0)  # per-operation deadline (aspect, not sig param)
    force_resync: bool = False                      # pass --resync to bisync on sync op
    keyring_service: str = "maghz"                  # keyring service name
```

`remotes: frozendict[Remote, RemoteConfig]` uses the `Remote` enum as key — typed, not stringly-keyed. Domain call sites use `cfg.cloud.remotes[remote]` where `remote: Remote`. The pydantic-settings env-prefix resolution `MAGHZ_CLOUD__REMOTES__DRIVE__*` requires a `@model_validator(mode="before")` or a custom pydantic validator that converts the parsed `dict[str, dict]` into `frozendict[Remote, RemoteConfig]` — the validator is a single admission step at settings parse time, not repeated in domain code. `frozendict` must be in `pyproject.toml`; see `[07]-[DEPS]`.

`MaghzSettings` gains `cloud: CloudConfig = Field(default_factory=CloudConfig)`.

`op_timeout_s` is a configuration policy value, not a signature parameter; it feeds `anyio.fail_after` inside `run` as the deadline aspect.

### `_BUILD` dispatch table

```python
_BUILD: frozendict[CloudOp, Callable[[MaghzSettings], Awaitable[Result[CloudSyncDetail, CloudFault]]]] = frozendict({
    CloudOp.SYNC:    _sync_detail,
    CloudOp.RESTORE: _restore_detail,
})
```

Each builder is an async function that assembles argument sequences, opens the temp dir via `AsyncExitStack`, spawns subprocesses via `_rclone`, folds `_RemoteResult` results, and returns `Result[CloudSyncDetail, CloudFault]`. The table eliminates all imperative branching in `run`; `assert_never` guards the fallthrough.

### `_env_for` — correspondence table function

```python
def _env_for(remote: Remote, cfg: CloudConfig) -> Mapping[str, str]: ...
```

Returns an immutable `Mapping[str, str]` (not a plain mutable `dict`) passed as `env=` to `anyio.run_process`; never stored or mutated after construction. The env key prefix is `RCLONE_CONFIG_{remote.value.upper()}_*`. Drive and OneDrive arms differ in which fields are included: Drive uses `SERVICE_ACCOUNT_CREDENTIALS` + `TYPE=drive` + `SCOPE=drive`; OneDrive uses `TOKEN` + `CLIENT_ID` + `CLIENT_SECRET` + `DRIVE_ID` + `TYPE=onedrive`. The `match remote` dispatch inside `_env_for` is total with `assert_never`.

### Immutability policy

`_BUILD` uses `frozendict` (matching the existing codebase preference per `existing-rails.md`). The filter file path is config-driven and passed as a direct `--filters-file` argument inside `_rclone`, eliminating the module-level-vs-call-time contradiction.

---

## [07]-[DEPS]

| [PACKAGE] | [VERSION FLOOR] | [CAPABILITY MINED] | [ACTION] |
| --- | --- | --- | --- |
| `anyio>=4.14.0` | already admitted | `run_process`, `fail_after`, `create_memory_object_stream`, `Path.exists` | no change |
| `stamina>=26.1.0` | already admitted | `@retry` with `BackoffHook` discriminator (`_rclone_transient_hook`) | no change |
| `msgspec>=0.21.1` | already admitted | `_RcloneLogLine`/`_RcloneStats` nested decode; `UNSET`/`UnsetType` on receipt | no change |
| `expression>=5.6.0` | already admitted | `Result`/`Error`/`Ok`; `Block.of_seq`; `Admit.retried` | no change |
| `keyring` | already admitted (no version pin) | `get_password` for token retrieval | no change |
| `pydantic>=2.13.4` + `pydantic-settings>=2.14.1` | already admitted | `RemoteConfig`, `CloudConfig`, `@model_validator` for `frozendict[Remote, RemoteConfig]` | no change |
| `frozendict` | NOT YET admitted | `frozendict[Remote, RemoteConfig]` for typed remote config table; `frozendict[str, str]` for env var correspondence | **ADD to `pyproject.toml`**: `"frozendict"` (no version pin; newest stable; stdlib injection pending PEP 603 successor — use `frozendict.frozendict` explicitly until stdlib promotion lands) |

`rclone` (v1.74.3+) and `pg_dump`/`pg_restore` (v18.4+) are Forge-provisioned CLI tools on `PATH`; they are not Python dependencies.

**.api catalog note for the implement pass:** `docs/.api/rclone.md` — authored at implement time. Captures: `bisync` flag surface (all flags above), `copy` verb (dump upload/download), env var config pattern (`RCLONE_CONFIG_<REMOTE>_<KEY>`), `--use-json-log` stderr format (JSON log line with nested `stats` object), `--stats 0`, exit codes, and per-remote credential env vars (service account for Drive; client credentials for OneDrive). Verify `frozendict` stdlib injection status against py3.15 changelog before realize; if not injected, import from `frozendict` package explicitly.

---

## [08]-[SEAMS]

| domains | claim |
| --- | --- |
| `["cloud-sync", "automation"]` | `cloud-sync` emits `Envelope(status=Status.OK, report=Report(detail=CloudSyncDetail(op=CloudOp.SYNC, ...)))` on success; the `automation` domain's `Sync` action with a future `op` literal invokes `run(CloudOp.SYNC, cfg)` and reads `envelope.status` and `envelope.report.detail` to populate `AutomationReceipt.rows_affected`. The automation engine is skill-agnostic and never reads cloud-sync internals directly; it reads only the returned `Envelope` and `CloudSyncDetail`. |
| `["cloud-sync", "runtime"]` | `cloud-sync` emits a typed `Detail` subclass (`tag="cloud"`) within the shared `Envelope` contract; the `runtime` receipt consumer dispatches on `detail.tag == "cloud"` and projects `transferred`, `errors`, `checks`, `elapsed_s`, `dump_path`/`restored_from` (as `msgspec.UNSET`-defaulting fields) as named evidence. |
| `["cloud-sync", "remote"]` | `cloud-sync` restore path (`run(CloudOp.RESTORE, cfg)`) is the data-recovery primitive for the `remote` domain's deploy sequence; `vps-deploy` invokes `maghz cloud restore` followed by `maghz schema apply` as the post-restore sequence. The DSN configuration and keyring/env-var credential surface are shared between the two domains. |
| `["cloud-sync", "runtime"]` | `cloud-sync` composes `LanePolicy.drain(Block.of_seq([Admit.retried(RetryClass.PROC, work)]))` from `admin/runtime/lanes.py` as the concurrent fan-out primitive; `DrainReceipt[_RemoteResult]` is the canonical result carrier from the drain phase; the domain never opens a raw `anyio.create_task_group()`. `ContentKey = NewType("ContentKey", str)` is the shared session-cache key type owned by `admin/runtime/lanes.py` and consumed by both the automation and cloud-sync domains. `anyio.fail_after(cfg.cloud.op_timeout_s)` wraps the entire `run` operation (pg_dump + drain) as a process-level deadline at the `Envelope`-returning boundary — this is the permitted CLI-boundary use of `fail_after`; domain functions internal to cloud-sync use `move_on_after`. |
| `["cloud-sync", "existing-rails"]` | `CloudSyncDetail.dump_path` and `CloudSyncDetail.restored_from` use `str | msgspec.UnsetType = msgspec.UNSET` — the same absence pattern as `SyncDetail.card_id` / `card_total` declared in `existing-rails.md`. Any change to `msgspec.UNSET` policy in `existing-rails.md` propagates to this blueprint. |
| `["cloud-sync", "runtime"]` | `DeployReceipt.up_detail: StackDetail` and `DeployReceipt.schema_detail: SchemaDetail` are imported from `admin/rails/stack.py` and `admin/rails/schema.py`. If these gain new required fields in the existing-rails realize pass, `DeployReceipt`'s msgspec decode of remote stdout must remain forward-compatible via the default `msgspec.Struct(forbid_unknown_fields=False)` behavior. The cloud-sync domain does not own these types; it consumes them read-only via the Envelope decode path. |

---

## [09]-[PORTABILITY / VPS]

On the Hostinger VPS:

**rclone config**: no interactive `rclone config` or device-code flow at runtime.

- **Google Drive**: service account JSON credentials. The base64-encoded service account JSON is stored in `MAGHZ_CLOUD__REMOTES__DRIVE__SERVICE_ACCOUNT_CREDENTIALS` env var (VPS `.env`, gitignored). `_env_for(Remote.DRIVE, cfg)` passes it as `RCLONE_CONFIG_DRIVE_SERVICE_ACCOUNT_CREDENTIALS`. No token refresh needed; service account credentials do not expire.
- **OneDrive**: client credentials flow. A service principal with `Files.ReadWrite.All` scope is registered in Azure AD. `MAGHZ_CLOUD__REMOTES__ONEDRIVE__CLIENT_ID`, `MAGHZ_CLOUD__REMOTES__ONEDRIVE__CLIENT_SECRET`, and the initial `MAGHZ_CLOUD__REMOTES__ONEDRIVE__TOKEN` (long-lived refresh token obtained via `rclone authorize --auth-no-open-browser`) are set in the VPS `.env`. rclone handles refresh internally when the token JSON blob is passed via env var. A scheduled `rclone config reconnect onedrive:` step or a token rotation script refreshes the stored token blob before expiry; the refreshed blob is written back to the VPS `.env` by the rotation script (outside this domain's scope).

**op service account**: `rclone` is invoked as the operator user account on the VPS. No system-level `rclone.conf` is used; the `env=` dict passed to `anyio.run_process` carries the full remote configuration.

**content root on VPS**: `CloudConfig.content_root` points to the Heptabase export directory on the VPS, which is a scheduled pull target. The cloud-sync domain does not own this delivery; it consumes the directory that already exists.

**pg_dump DSN**: the VPS `MAGHZ_DATABASE_DSN` points to the local PostgreSQL instance running in the Docker container (same network). The dump path is local to the VPS container network.

**LanePolicy on VPS**: `LanePolicy` capacity default is sufficient for 2 drain children (one per remote). No VPS-specific capacity tuning required.

**gitignore**: `.env` is already gitignored. No credentials or dump files are committed.

---

## [10]-[ACCEPTANCE]

Gate signals for the implement pass:

- `ruff check admin/rails/cloud.py admin/settings/config.py admin/__main__.py admin/rails/__init__.py` — zero diagnostics.
- `ty check admin/` — zero errors.
- `mypy admin/` — zero errors (`exhaustive-match` enabled; every `match op` arm exhausted).
- Pre-flight: `anyio.Path("rclone").exists()` and `anyio.Path("pg_dump").exists()` return `True` on the target machine; `run` emits `Error(CloudFault(op="spawn", ...))` immediately if either is absent.
- `maghz cloud sync` against a test remote — exits 0, stdout is one valid JSON `Envelope` with `status="ok"` and `detail.tag="cloud"`.
- `maghz cloud restore` — exits 0, stdout is one valid `Envelope`; `pg_restore` replays against the ledger and `maghz schema doctor` reports healthy extensions.
- Both remotes receive the dump and the content tree (verified via `rclone ls drive:maghz/dumps` and `rclone ls onedrive:maghz/dumps`).
- Concurrent remote dispatch verified: `DrainReceipt.accepted == 2` and `DrainReceipt.completed == 2`; structlog shows overlapping timestamps for drive and onedrive rclone calls.
- Fault path: a non-zero rclone exit for one remote produces `Status.FAILED` envelope with a `Row` naming the failed remote; `DrainReceipt.completed == 1`, `DrainReceipt.rejected == 1`; the other remote's `_RemoteResult` materializes in the receipt.
- `match op` arms in `_BUILD` cover all `CloudOp` cases; `assert_never` fires at type-check time on an unhandled arm.
- `match remote` arms in `_env_for` cover all `Remote` cases; `assert_never` fires on an unhandled arm.
- `_env_for(Remote.DRIVE, cfg)` and `_env_for(Remote.ONEDRIVE, cfg)` produce non-overlapping key sets with correct `RCLONE_CONFIG_<REMOTE.value.upper()>_*` prefixes.
- `RemoteConfig` fields resolve from `MAGHZ_CLOUD__REMOTES__DRIVE__*` and `MAGHZ_CLOUD__REMOTES__ONEDRIVE__*` env vars in pydantic-settings validation; `CloudConfig.remotes` type is `frozendict[Remote, RemoteConfig]`.
- `msgspec.json.decode(line, type=_RcloneLogLine)` for a rclone stats log line with nested `stats` object decodes to `_RcloneLogLine` with non-`None` `.stats`; a plain log line (no `stats` key) decodes with `.stats is None`.
- `CloudSyncDetail.dump_path` is `msgspec.UNSET` for restore op; `CloudSyncDetail.restored_from` is `msgspec.UNSET` for sync op.
- `frozendict` admitted in `pyproject.toml`; `uv lock` regenerates cleanly.
- No `asyncio` import anywhere in `admin/rails/cloud.py`.
- `_RcloneTransient` class exists only in `cloud.py`; no parallel `_RcloneRateLimit` or `_CloudError` wrapper classes.
