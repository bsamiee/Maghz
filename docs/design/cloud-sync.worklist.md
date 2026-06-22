# [WORKLIST: cloud-sync]

Realize-ready worklist folded from `docs/design/cloud-sync.md`. The blueprint is the design; this is the execution order, the exact owners, the closed unions, the `.api` members, the new dep, the cross-domain ripples, the prerequisite domains, and the gate. No redesign; no new sanctioned surface beyond the blueprint.

---

## [00]-[DEPENDS_ON]

This domain composes runtime substrate that does not yet exist; its owners must be realized FIRST.

| [DOMAIN KEY] | [OWNER THAT MUST EXIST] | [WHAT cloud-sync CONSUMES] |
| --- | --- | --- |
| `runtime` | `admin/runtime/lanes.py` | `LanePolicy`, `drain`, `Admit.retried`, `DrainReceipt`, `Block.of_seq`, `ContentKey = NewType("ContentKey", str)` (shared session-cache key) |
| `runtime` | `admin/runtime/resilience.py` | `guard(RetryClass.PROC)`, `RetryClass.PROC`, `RetryClass.SECRET`; the `stamina` install path (`StructlogOnRetryHook` registered at startup) |
| `existing-rails` | `admin/core/model.py` | `Detail`, `Envelope`, `Report`, `Row`, `completed`, `fault`, `Status` (already realized — extended only by a new `Detail` subclass) |
| `existing-rails` | `admin/db.py` | `Boundary` (read-only reference; NOT extended here), the `MAGHZ_DATABASE_DSN` shape on `DatabaseConfig` for the `pg_dump`/`pg_restore` DSN |

`runtime` is the hard prerequisite: `LanePolicy.drain` and `guard` are the fan-out and retry primitives, and this domain never opens a raw `anyio.create_task_group()` nor declares a standalone `@stamina.retry`. `automation` and `remote` are DOWNSTREAM consumers (see RIPPLES), not prerequisites.

---

## [01]-[OWNERS]

One new rail file; two settings models + one settings field; two registration edits. No `backup.py`/`restore.py`, no helper file, no second rail file.

| [FILE] | [ACTION] | [SECTION] | [DENSE OWNER] |
| --- | --- | --- | --- |
| `admin/rails/cloud.py` | create | `[TYPES]` | `CloudOp` (StrEnum verb vocabulary), `Remote` (StrEnum `drive`/`onedrive`), `CloudBoundary` (`Literal` fault-case alias), `_RcloneTransient(Exception)` (private rate-limit sentinel carrying `CloudFault`) |
| `admin/rails/cloud.py` | create | `[MODELS]` | `CloudSyncDetail` (`Detail` subclass, `tag="cloud"`, typed receipt), `_RcloneStats` (inner stats struct), `_RcloneLogLine` (outer log-line wrapper), `_RemoteResult` (per-remote drain result) |
| `admin/rails/cloud.py` | create | `[ERRORS]` | `CloudFault` (`msgspec.Struct`, `op: CloudBoundary`, `message`, `remote`, `exit_code`) |
| `admin/rails/cloud.py` | create | `[TABLES]` | `_BUILD` (`CloudOp` -> async builder dispatch), `_rclone_transient_hook` (the one `stamina` backoff hook) |
| `admin/rails/cloud.py` | create | `[OPERATIONS]` | `_env_for(remote, cfg)` (per-remote env correspondence, total `match remote`), `_rclone(*argv, env, timeout_s)` (single subprocess boundary -> `Result[_RcloneStats, CloudFault]`), `_sync_detail`/`_restore_detail` (the two `_BUILD` builders), `run(op, cfg, /)` (the ONE polymorphic entrypoint) |
| `admin/settings/config.py` | modify | `[MODELS]` | `RemoteConfig` (per-remote OAuth credentials), `CloudConfig` (remote paths, content root, filter file, timeout, force-resync, keyring service; `remotes: frozendict[Remote, RemoteConfig]` with `@model_validator(mode="before")`), `MaghzSettings.cloud: CloudConfig` field |
| `admin/__main__.py` | modify | `[CONSTANTS]` + `[COMPOSITION]` + `[ENTRY]` | `_CLOUD` group, `_cloud` sub-app, `cloud sync` + `cloud restore` command registrations dispatching `rails.cloud(CloudOp.SYNC/RESTORE, settings())` |
| `admin/rails/__init__.py` | modify | `[EXPORTS]` | `from admin.rails.cloud import CloudOp, run as cloud`; add `CloudOp`, `cloud` to `__all__` |
| `pyproject.toml` | modify | `[project].dependencies` | admit `frozendict` (see DEPS) |
| `docs/.api/rclone.md` | create | n/a | the `rclone` CLI surface catalog (subprocess boundary; no Python library) — see DEPS catalog note |

The single conceptual concern (drive rclone to back up and restore the maghz system) lives entirely in `admin/rails/cloud.py`. The `sync` namespace stays owned by `admin/rails/sync.py` (Heptabase card reconciliation); this domain mounts under the distinct `cloud` sub-app so `maghz cloud sync` / `maghz cloud restore` never collide with `maghz sync diff`/`generate`.

---

## [02]-[ADTs]

### `CloudOp` — closed verb vocabulary (discriminant of `run` and `_BUILD`)

```python
class CloudOp(StrEnum):
    SYNC    = "sync"     # pg_dump + content bisync to both remotes
    RESTORE = "restore"  # pg_restore from remote dump + content bisync back
```

`run(op, cfg, /)` matches on `op`; `_BUILD[op]` selects the coroutine; `assert_never` guards the fallthrough. Anticipatory cases (`VERIFY`, `PRUNE`, `STATUS`) are each one new case + one `_BUILD` row — no structural change to `run`, `CloudSyncDetail`, or `CloudBoundary`.

### `Remote` — closed remote vocabulary (key of `CloudConfig.remotes`, discriminant of `_env_for`)

```python
class Remote(StrEnum):
    DRIVE    = "drive"
    ONEDRIVE = "onedrive"
```

`remote.value` IS the rclone remote name and the `RCLONE_CONFIG_<REMOTE>_*` env prefix key. `CloudConfig.remotes` is `frozendict[Remote, RemoteConfig]` (enum key, never bare string). All iteration uses `tuple(Remote)`. `match remote` in `_env_for` is total with `assert_never`.

### `CloudBoundary` — closed fault vocabulary (the `CloudFault.op` case)

```python
type CloudBoundary = Literal["rclone", "pg_dump", "pg_restore", "spawn"]
```

Own alias in `cloud.py`; does NOT extend `admin.db.Boundary`. `"spawn"` covers `OSError` on `anyio.run_process` (missing binary/path); the other three carry rclone and pg tool exit failures. `CloudFault.op` carries one case, never a bare string.

### `_RcloneTransient(Exception)` — the named platform-forced retry seam

```python
class _RcloneTransient(Exception):
    def __init__(self, fault: CloudFault) -> None:
        self.fault = fault
        super().__init__(str(fault))
```

Single-purpose but justified: `stamina`'s `BackoffHook` receives an `Exception` instance and cannot inspect a `Result.Error` value. `_rclone` raises it ONLY for rclone exit code 7 (rate-limit), carrying the `CloudFault` so the `run` boundary projects without reconstructing the fault. No parallel `_RcloneRateLimit`/`_CloudError` wrapper class anywhere.

---

## [03]-[API_MEMBERS]

### `anyio` (catalog: `docs/.api/anyio.md` if present; floor `anyio>=4.14.0`)

- `anyio.run_process(command, *, input=None, check=False, env=None, cwd=None)` — sole subprocess driver for rclone, pg_dump, pg_restore. `check=False` mandatory; the boundary owns exit-code interpretation and lifts non-zero exits to `Error(CloudFault(...))`.
- `anyio.Path(binary).exists()` — pre-flight existence check for `rclone`, `pg_dump`/`pg_restore`; missing binary lifts to `Error(CloudFault(op="spawn", ...))` before any subprocess fires.
- `anyio.fail_after(cfg.cloud.op_timeout_s)` — wraps the entire `run` operation (pg_dump + drain) at the `Envelope`-returning CLI boundary. This is the sanctioned CLI-boundary use of `fail_after` per the `runtime` blueprint; a deadline trip surfaces `anyio.get_cancelled_exc_class()` and propagates (NOT caught into `Result.Error`). Never `asyncio.wait_for`.
- `anyio.get_cancelled_exc_class()` — the deadline-trip exception class the `__main__.py` handler collapses to a generic fault envelope.
- `anyio.CancelScope(shield=True)` — shields temp-dir cleanup in `finally` under cancellation.
- NOT used: `anyio.create_task_group()` directly (fan-out goes through `LanePolicy.drain`), `anyio.TemporaryDirectory()` (does not exist in the anyio API — use `tempfile.TemporaryDirectory()` via `contextlib.AsyncExitStack.enter_context`).

### `admin/runtime/lanes.py` (DEPENDS_ON `runtime`)

- `LanePolicy.drain(policy, units, cache)` / module-level `drain(...)` — the concurrent remote fan-out: `Block.of_seq([Admit.retried(RetryClass.PROC, _work(remote)) for remote in Remote])`.
- `Admit.retried(RetryClass.PROC, work)` — the admission case wrapping each per-remote work unit.
- `DrainReceipt` — `.values` (`Block[_RemoteResult]`), `.faults`, `.accepted`/`.completed`/`.rejected` counts; folded into `CloudSyncDetail` after the drain.
- `ContentKey = NewType("ContentKey", str)` — shared session-cache key threaded into `drain`'s `cache` to short-circuit already-synced artifacts across multi-stage fronts.

### `admin/runtime/resilience.py` (DEPENDS_ON `runtime`)

- `guard(RetryClass.PROC)` — composed for spawn-level `OSError` faults via the drain `Admit.retried`. No standalone `@stamina.retry` decorator declared in `cloud.py` except the single `_rclone` decoration below.
- `RetryClass.PROC`, `RetryClass.SECRET` — the only retry classes this domain references (the blueprint commits to Option B: `RetryClass` is NOT extended with a `CLOUD_RCLONE` case).

### `stamina` (catalog if present; floor `stamina>=26.1.0`)

- `@stamina.retry(on=_rclone_transient_hook, attempts=3, wait_initial=2.0, wait_max=30.0, wait_jitter=1.0)` — decorates `_rclone`; the ONLY retry path in `cloud.py`. `_rclone_transient_hook(exc) -> bool | float` returns `60.0` for `_RcloneTransient` (exit 7), `True` for `OSError` (spawn, exponential backoff), `False` otherwise.
- `stamina.instrumentation.StructlogOnRetryHook` — registered at process startup in `__main__.py` (runtime/existing-rails concern); no per-rail hook setup here.

### `msgspec` (catalog if present; floor `msgspec>=0.21.1`)

- `msgspec.Struct(frozen=True, tag="cloud", gc=False)` — `CloudSyncDetail`.
- `msgspec.Struct(frozen=True, gc=False)` — `_RcloneStats`, `_RcloneLogLine`, `_RemoteResult`, `CloudFault`.
- `msgspec.json.decode(line.encode(), type=_RcloneLogLine)` — decode each rclone `--use-json-log` stderr line inside `try/except msgspec.DecodeError` (skip failures); collect `.stats is not None` lines; sum `transferred`/`errors`/`checks`, take last `elapsedTime`; zero-sentinel `_RcloneStats()` if none decode.
- `msgspec.UNSET` / `msgspec.UnsetType` — `CloudSyncDetail.dump_path` (UNSET on restore), `CloudSyncDetail.restored_from` (UNSET on sync), `_RemoteResult.dump_path`. Same absence pattern as `SyncDetail.card_id`/`card_total`.
- `msgspec.json.encode(envelope)` — existing `Envelope.encode()` contract, unchanged.

### `keyring` (catalog: `libs/python/runtime/.api/keyring.md`; admitted, no floor pin)

- `keyring.get_password(cfg.cloud.keyring_service, remote.value)` — token JSON retrieval at call time (never import time), from `_env_for`; falls back to `cfg.cloud.remotes[remote].token` (VPS env path) when keyring returns `None`.

### `admin/core` (existing, realized)

- `completed(status, detail, *, rows=(), notes=())`, `fault(error, context=None)`, `Status`, `Detail`, `Envelope`, `Row` — the `run` boundary lifts `Result[CloudSyncDetail, CloudFault]` to `Envelope` via `completed`/`fault`. A partial remote failure yields `Status.FAILED` with `Row` items naming the failed remote.

### `pydantic` / `pydantic-settings` (existing; floors `pydantic>=2.13.4`, `pydantic-settings>=2.14.1`)

- `BaseModel` + `model_config = _GROUP` (existing `ConfigDict`) for `RemoteConfig`, `CloudConfig`.
- `pydantic.Field(default_factory=..., gt=0)` for `CloudConfig.op_timeout_s` and `remotes` default.
- `@model_validator(mode="before")` on `CloudConfig` — convert the parsed `dict[str, dict]` from `MAGHZ_CLOUD__REMOTES__<REMOTE>__*` into `frozendict[Remote, RemoteConfig]` at parse time (one admission step, never repeated in domain code).
- `MaghzSettings.cloud: CloudConfig = Field(default_factory=CloudConfig)`.

### `rclone` CLI v1.74.3+ (catalog: `docs/.api/rclone.md` — authored at implement time; subprocess boundary only)

- `RCLONE_CONFIG_<REMOTE.value.upper()>_<KEY>=value` env-var config (no `rclone.conf` written/read). Per-remote keys: `TYPE`, `CLIENT_ID`, `CLIENT_SECRET`, `TOKEN`; Drive adds `SCOPE=drive` + `SERVICE_ACCOUNT_CREDENTIALS` (base64 JSON); OneDrive adds `DRIVE_ID`.
- `rclone copy <src> <remote>:<path>` — dump upload (sync) / dump download (restore).
- `rclone bisync <content_root> <remote>:<remote_content_path>` with flags `--resync-mode path1`, `--conflict-resolve newer`, `--conflict-loser pathname`, `--conflict-suffix conflict`, `--resilient`, `--recover`, `--filters-file <filter_file>`, `--check-access`, `--use-json-log`, `--stats 0`, `--log-level INFO`, and `--resync` when `CloudOp.RESTORE` or `cfg.cloud.force_resync`.
- Exit-code -> `CloudBoundary` mapping: `0`/`9` success (9 = no files transferred, NOT a fault); `1` usage non-retriable; `5` temporary retriable (`RetryClass.PROC`); `7` rate-limit retriable with 60 s override (`_rclone_transient_hook`); `8` transfer-limit non-retriable.
- `pg_dump <DSN> -F c -Z zstd:3 -f <tmp>/<ts>_maghz.dump -O --no-privileges`; `pg_restore -d <DSN> -c -O --no-privileges <tmp>/<dump>`. Forge-provisioned CLI tools on `PATH` (`pg_dump`/`pg_restore` v18.4+), not Python deps.

---

## [04]-[DEPS]

| [PACKAGE] | [BAND] | [ACTION] | [.api CATALOG NOTE] |
| --- | --- | --- | --- |
| `frozendict` | pure-venv | ADD to `pyproject.toml` `[project].dependencies` (no version pin; newest stable). Used for `frozendict[Remote, RemoteConfig]` (typed remote table) and `frozendict[str, str]` env correspondence. | Author `docs/.api/frozendict.md`: `frozendict.frozendict` constructor, typed-key mapping behavior, hashability/immutability, pydantic v2 compatibility for the `@model_validator(mode="before")` admission. Verify stdlib injection status against the py3.15 changelog before realize; PEP 603 successor not yet merged, so import `frozendict.frozendict` explicitly until stdlib promotion lands. |
| `rclone` (v1.74.3+) | cli | no pyproject change — Forge-provisioned on `PATH` | Author `docs/.api/rclone.md` at implement time: `bisync` flag surface, `copy` verb, `RCLONE_CONFIG_<REMOTE>_<KEY>` env config pattern, `--use-json-log` nested-`stats` stderr format, `--stats 0`, exit codes, per-remote credential env vars (service account for Drive; client credentials for OneDrive). |
| `anyio` / `stamina` / `msgspec` / `expression` / `keyring` / `pydantic` / `pydantic-settings` | pure-venv | already admitted — no change | existing catalogs / floors in `pyproject.toml` |

DEP RECONCILE (name in RIPPLES): the `runtime` blueprint explicitly does NOT admit `frozendict` (it routes every keyed dispatch table through `expression.Map` and rejects `frozendict` for py3.15). The cloud-sync blueprint REQUIRES `frozendict` for the typed `frozendict[Remote, RemoteConfig]` pydantic-settings table and the `frozendict[str, str]` env correspondence — a pydantic-validatable immutable mapping that `expression.Map` does not serve at the settings boundary. The conditional-package-prep step admits `frozendict` and authors its catalog; the implement pass must NOT retro-convert the `runtime` domain's `Map`-based dispatch tables to `frozendict`, and must NOT block on the runtime blueprint's "not admitted" stance — the two table forms coexist (`expression.Map` for runtime dispatch, `frozendict` for the pydantic settings table and the env correspondence).

---

## [05]-[RIPPLES]

| domains | claim |
| --- | --- |
| `["cloud-sync", "automation"]` | `cloud-sync` emits `Envelope(status=Status.OK, report=Report(detail=CloudSyncDetail(op=CloudOp.SYNC, ...)))` on success; the `automation` domain's `Sync` action with a future `op` literal invokes `run(CloudOp.SYNC, cfg)` and reads `envelope.status` and `envelope.report.detail` to populate `AutomationReceipt.rows_affected`. The automation engine is skill-agnostic and reads only the returned `Envelope` and `CloudSyncDetail`, never cloud-sync internals. `automation` owns `AutomationReceipt`. |
| `["cloud-sync", "runtime"]` | `cloud-sync` emits a typed `Detail` subclass (`tag="cloud"`) inside the shared `Envelope`; the `runtime` receipt consumer dispatches on `detail.tag == "cloud"` and projects `transferred`/`errors`/`checks`/`elapsed_s`/`dump_path`/`restored_from` (`msgspec.UNSET`-defaulting) as named evidence. `runtime` owns `Receipt`/`Signals`/the receipt projection. |
| `["cloud-sync", "runtime"]` | `cloud-sync` composes `LanePolicy.drain(Block.of_seq([Admit.retried(RetryClass.PROC, work)]))` for the concurrent remote fan-out; `DrainReceipt[_RemoteResult]` is the canonical result carrier; the domain never opens a raw `anyio.create_task_group()`. `ContentKey = NewType("ContentKey", str)` is the shared session-cache key owned by `admin/runtime/lanes.py` and consumed by both `automation` and `cloud-sync`. `anyio.fail_after(cfg.cloud.op_timeout_s)` wraps the entire `run` operation as the permitted CLI-boundary deadline. `runtime` owns `LanePolicy`/`drain`/`DrainReceipt`/`ContentKey`/`RetryClass`. |
| `["cloud-sync", "runtime"]` | DEP TENSION: `runtime` rejects `frozendict` (uses `expression.Map` for dispatch tables); `cloud-sync` admits `frozendict` for `frozendict[Remote, RemoteConfig]` (pydantic-settings table) and `frozendict[str, str]` (env correspondence). The two forms coexist by domain — `Map` for runtime keyed dispatch, `frozendict` for the cloud-sync settings/env tables. Neither domain converts the other's table form. `runtime` owns the `Map`-based dispatch convention; `cloud-sync` owns the `frozendict` settings/env tables. |
| `["cloud-sync", "remote"]` | `cloud-sync` restore (`run(CloudOp.RESTORE, cfg)`) is the data-recovery primitive for the `remote` domain's deploy sequence; `vps-deploy` invokes `maghz cloud restore` then `maghz schema apply` as the post-restore sequence. The DSN and keyring/env-var credential surface are shared. `remote` owns `DeployReceipt`/`deploy`. |
| `["cloud-sync", "existing-rails"]` | `CloudSyncDetail.dump_path` and `CloudSyncDetail.restored_from` use `str | msgspec.UnsetType = msgspec.UNSET` — the same absence pattern as `SyncDetail.card_id`/`card_total` in `existing-rails.md`. Any change to `msgspec.UNSET` policy there propagates here. `existing-rails` owns `SyncDetail`/the `Detail` base. |
| `["cloud-sync", "existing-rails"]` | `cloud-sync` mounts under the `cloud` sub-app to avoid the `sync` namespace owned by `admin/rails/sync.py` (Heptabase card reconciliation); the `sync_diff`/`sync_generate` re-exports in `admin/rails/__init__.py` are untouched. `existing-rails` owns the `sync` rail and namespace. |

---

## [06]-[ACCEPTANCE]

Static gate (zero-diagnostic on every signal):
- `ruff check admin/rails/cloud.py admin/settings/config.py admin/__main__.py admin/rails/__init__.py` — zero.
- `ty check admin/` — zero errors (binding type gate).
- `mypy admin/` — zero errors; `exhaustive-match` proves every `match op` and `match remote` arm exhausted with `assert_never`.
- `uv lock` regenerates cleanly after `frozendict` admission.

Runtime verbs:
- `maghz cloud sync` against a test remote — exit 0, stdout one valid JSON `Envelope` with `status="ok"` and `detail.tag="cloud"`.
- `maghz cloud restore` — exit 0, one valid `Envelope`; `pg_restore` replays; `maghz schema doctor` reports healthy extensions.
- Both remotes receive dump + content tree (`rclone ls drive:maghz/dumps`, `rclone ls onedrive:maghz/dumps`).

Receipts / structural:
- Pre-flight: `anyio.Path("rclone").exists()` and `anyio.Path("pg_dump").exists()` return `True`; `run` emits `Error(CloudFault(op="spawn", ...))` immediately on either absent.
- Concurrent dispatch: `DrainReceipt.accepted == 2` and `DrainReceipt.completed == 2`; structlog shows overlapping drive/onedrive timestamps.
- Fault path: a non-zero rclone exit for one remote yields `Status.FAILED` with a `Row` naming the failed remote; `DrainReceipt.completed == 1`, `DrainReceipt.rejected == 1`; the other remote's `_RemoteResult` materializes.
- `_env_for(Remote.DRIVE, cfg)` and `_env_for(Remote.ONEDRIVE, cfg)` produce non-overlapping key sets with correct `RCLONE_CONFIG_<REMOTE.value.upper()>_*` prefixes.
- `RemoteConfig` fields resolve from `MAGHZ_CLOUD__REMOTES__DRIVE__*` / `MAGHZ_CLOUD__REMOTES__ONEDRIVE__*`; `CloudConfig.remotes` is `frozendict[Remote, RemoteConfig]`.
- `msgspec.json.decode(line, type=_RcloneLogLine)` for a stats line decodes `.stats` non-`None`; a plain log line decodes `.stats is None`.
- `CloudSyncDetail.dump_path` is `msgspec.UNSET` for restore; `restored_from` is `msgspec.UNSET` for sync.
- No `asyncio` import anywhere in `admin/rails/cloud.py`; `_RcloneTransient` exists only there; no parallel `_RcloneRateLimit`/`_CloudError` wrapper.
