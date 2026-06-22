# `rclone` (CLI v1.74.3+)

Cloud-sync boundary of `admin/rails/cloud.py`. `rclone` and `pg_dump`/`pg_restore` (v18.4+) are
Forge-provisioned binaries on `PATH`, not Python dependencies — there is no SDK to import and no
`pyproject.toml` admission. The sole driver is `anyio.run_process(argv, env=..., check=False)`;
`check=False` is mandatory so the boundary owns exit-code interpretation rather than catching a
`CalledProcessError`. Every invocation reports through the `CloudBoundary` exit-code map below —
`rclone`/`pg_dump`/`pg_restore`/`spawn` are the four cases, the `spawn` case carrying the `OSError`
(missing binary / path) seam that `anyio.run_process` raises before any exit code exists.

## Config — env-var remotes, no `rclone.conf`

```python
# RCLONE_CONFIG_<REMOTE.value.upper()>_<KEY>=value   (one env block per remote)
```

`rclone` reads remote definitions entirely from `RCLONE_CONFIG_*` environment variables passed as
`env=` to `anyio.run_process`; no `rclone.conf` is written or read and no `rclone config` /
device-code flow runs at runtime. `_env_for(remote, cfg)` builds the per-remote block as a
`frozendict[str, str]` (immutable, never mutated after construction), and `remote.value` IS the
rclone remote name and the env-prefix key. The `match remote` arm is total with `assert_never`. Both
remotes share a `common` block of four keys (`TYPE`, `CLIENT_ID`, `CLIENT_SECRET`, `TOKEN`); each arm
then adds the credential-strategy keys it owns, so the key **names** overlap on the four common keys
while the per-strategy keys (`SCOPE`/`SERVICE_ACCOUNT_CREDENTIALS` vs `DRIVE_ID`) are disjoint.

Token JSON and client secrets are fetched at call time, never at import time:
`keyring.get_password(cfg.cloud.keyring_service, remote.value)` is primary, falling back to
`cfg.cloud.remotes[remote].token` (the VPS env path, where `keyring` resolves to the null keyring).

| key (`RCLONE_CONFIG_<REMOTE>_…`) | `Remote.DRIVE` | `Remote.ONEDRIVE` | source |
| --- | :--: | :--: | --- |
| `TYPE` | `drive` | `onedrive` | `remote.value` |
| `CLIENT_ID` | yes | yes | `remotes[remote].client_id` |
| `CLIENT_SECRET` | yes | yes | `remotes[remote].client_secret` |
| `TOKEN` | yes | yes | keyring → `remotes[remote].token` |
| `SCOPE` | `drive` | — | literal |
| `SERVICE_ACCOUNT_CREDENTIALS` | yes (raw JSON) | — | `remotes[remote].service_account_credentials` |
| `DRIVE_ID` | — | yes | `remotes[remote].drive_id` |

`CLIENT_ID`/`CLIENT_SECRET`/`TOKEN` are emitted for both remotes from the shared `common` block; for
Drive they carry empty values (the service-account strategy ignores them) but the keys are still set.

**`drive` — service account.** Authenticates with a service account (`SCOPE=drive`): no user OAuth
token, no refresh problem, credentials do not expire. The `service_account_credentials` option
(`rclone config providers`, `drive` backend) is documented as the **Service Account Credentials JSON
blob** — it takes the **raw service-account key JSON verbatim**, not a base64 wrapper; the file-path
alternative is `service_account_file`. The env value is therefore the literal JSON string;
`RCLONE_CONFIG_DRIVE_SERVICE_ACCOUNT_CREDENTIALS` set to a base64-encoded blob fails the backend's
JSON parse. `service_account_credentials` is Drive-only and empty for OneDrive.

**`onedrive` — OAuth token blob.** Uses `CLIENT_ID` + `CLIENT_SECRET` + a long-lived `TOKEN` JSON
blob (`rclone config providers` documents `token` as the **OAuth Access Token as a JSON blob**)
obtained out of band via `rclone authorize`, plus the personal `DRIVE_ID`; rclone refreshes the
access token internally from the refresh token inside the blob. `drive_id` is OneDrive-only and empty
for Drive. All option names are verified against `rclone config providers` for the `drive` and
`onedrive` backends.

## `copy` — dump transfer (one-directional)

```
rclone copy <src> <remote>:<path>
```

`copy` moves the `pg_dump` artifact only: local dump → `<remote>:<remote_dump_path>` on
`CloudOp.SYNC`, and `<primary>:<remote_dump_path>` → local staging dir on `CloudOp.RESTORE` (the whole
dump directory is copied down, then `_first_dump` selects the first `*.dump` under it for replay). It
is a one-directional file transfer and never reconciles a tree. The restore copy runs with
`--use-json-log --stats 0` and `op="rclone"`, sourced from a single configurable primary remote.

## `bisync` — content-tree reconciliation (bidirectional)

```
rclone bisync <content_root> <remote>:<remote_content_path> \
  --resync-mode path1 --conflict-resolve newer --conflict-loser pathname \
  --conflict-suffix conflict --resilient --recover \
  --filters-file <filter_file> --check-access \
  --use-json-log --stats <interval> --log-level INFO \
  [--resync]
```

`bisync` is the bidirectional content reconciler. Flag semantics (every value verified against
`rclone bisync --help`, v1.74.3):

- `--resync` / `--resync-mode path1` — `--resync` performs the baseline resync run and is equivalent
  to `--resync-mode path1`; it is appended on `CloudOp.RESTORE` or when `cfg.cloud.force_resync`. The
  **first-ever** run on a path-pair requires `--resync` to establish the path1/path2 baseline
  (without it bisync aborts on a missing prior listing). `--resync-mode path1` makes the local
  content root authoritative when a resync occurs. The `--resync-mode` value vocabulary is
  `path1|path2|newer|older|larger|smaller` (no `none`; default `path1`).
- `--conflict-resolve newer` + `--conflict-loser pathname` + `--conflict-suffix conflict` — on a
  genuine conflict the newer side wins and the loser is **renamed** (suffix `conflict`,
  `--conflict-loser` vocabulary `''|num|pathname|delete`, `pathname` inserts the suffix into the
  filename) rather than discarded. The `--conflict-resolve` vocabulary is
  `none|path1|path2|newer|older|larger|smaller`. No data is lost on conflict.
- `--resilient` — future runs retry after less-serious errors instead of demanding a fresh
  `--resync`. `--recover` — auto-recover from an interrupted run without `--resync`. Together they
  make the lane survive a killed process between runs.
- `--filters-file <filter_file>` — reads exclude/include patterns from `cfg.cloud.filter_file`
  (`.rclone-filter`: `.DS_Store`, `__pycache__`, `.venv`, editor temp files). Passed as a direct
  argument from config, never a module-level constant.
- `--check-access` — aborts **before** any destructive op if the `RCLONE_TEST` sentinel
  (`--check-filename`, default `RCLONE_TEST`) is absent on either Path1 or Path2; the guard against
  syncing into an empty/unmounted remote.

`bisync` honours the global `--use-json-log`, `--stats`, and `--log-level` flags below.

## JSON log stream — `--use-json-log`

`--use-json-log` emits **one JSON object per stderr line**. The transfer tally rides a `stats`
object that rclone nests inside a log-line envelope:

```json
{"time":"…","level":"info","msg":"\nTransferred: …\n","stats":{"bytes":52428800,"checks":0,"deletedDirs":0,"deletes":0,"elapsedTime":0.064,"errors":0,"eta":null,"fatalError":false,"listed":1,"renames":0,"retryError":false,"speed":0,"totalBytes":52428800,"totalChecks":0,"totalTransfers":1,"transferTime":0.063,"transfers":1},"source":"accounting/stats.go:551"}
```

Most lines carry **no** `stats` key (per-object `Copied`/`Checks`/banner lines); they decode as
`_RcloneLogLine` with `stats is None` and are skipped. A single `msgspec.json.Decoder(type=_RcloneLogLine)`
is built once at import (`_LOG_DECODER`) and reused per line — never a per-line `msgspec.json.decode`
that re-resolves the type. Each non-blank line runs `_LOG_DECODER.decode(line)` inside
`try/except msgspec.DecodeError` (skip non-conforming progress/banner noise), keeping the lines where
`.stats is not None`, which fold into the `CloudSyncDetail` receipt. Never parse the human-readable
`msg` text.

**Wire-key truth (verified against v1.74.3 stderr).** The nested `stats` object uses these camelCase
keys. The transfer-count key is **`transfers`** — `transferred` is **not** a key rclone emits, so a
struct field literally named `transferred` decodes to its `0` default on every line. The
`_RcloneStats` files-transferred field must therefore carry the wire key, either named `transfers`
directly or `msgspec.field(name="transfers")` on a differently-named field:

| receipt field | nested `stats` key | note |
| --- | --- | --- |
| files transferred | `transfers` | field named `transfers`, or `msgspec.field(name="transfers")` |
| files checked | `checks` | direct |
| transfer errors | `errors` | direct |
| wall seconds | `elapsedTime` | float (camelCase) |

`_RcloneStats` is a `msgspec.Struct(frozen=True, gc=False)` with `forbid_unknown_fields=False`
(default), so the unmodelled keys (`bytes`, `totalTransfers`, `speed`, …) are ignored. Sum
`transfers`/`checks`/`errors` across all stats-bearing lines; take the run **maximum** `elapsedTime`
(`elapsedTime` is monotone within a run, so the max is the final wall figure even if lines arrive out
of order). If no stats line decodes, yield the zero-sentinel `_RcloneStats()`.

**`--stats <interval>` is required for a tally.** `--stats 0` disables the **entire** stats emitter on
v1.74.3 (`--stats Duration … (0 to disable)`): it suppresses periodic lines **and** the end-of-run
summary, so a run under `--stats 0 --use-json-log --log-level INFO` emits **zero** `stats` objects and
the fold returns the zero-sentinel — the `CloudSyncDetail` transfer tally is then identically zero
regardless of how many files moved (empirically: `--stats 0` → 0 stats objects, `--stats 200ms` → the
summary object above). Materializing the tally requires a **non-zero** interval longer than the op
(e.g. `--stats 1m`): the backup finishes before the first tick, so only the single end-of-run summary
line fires and periodic noise stays suppressed while the count survives.

## Exit-code → `CloudBoundary` map

| exit | rclone meaning | rail |
| :--: | --- | --- |
| `0` | success | success |
| `9` | success, no files transferred | success (**NOT** a fault) |
| `1` | syntax / usage error | non-retriable `Error(CloudFault(op="rclone"))` |
| `5` | temporary error | retriable — `raise _RcloneTransient` |
| `7` | fatal (rate-limit / quota) | retriable — `raise _RcloneTransient` |
| `8` | transfer limit reached | non-retriable `Error(CloudFault(op="rclone"))` |

Both retriable exits take the **same** path: `_spawn` raises `_RcloneTransient(CloudFault(...))` for
exit `5` **and** `7`, because the retry decoration is `_spawn`'s own `@stamina.retry` and `stamina`'s
backoff hook inspects an `Exception` instance — it cannot read a `Result.Error` value. A returncode is
not an exception, so neither code is retriable through `RetryClass.PROC`: that class targets `OSError`
only (`Policy(target=(OSError,))` in `admin/runtime/resilience.py`) and never sees an exit code. The
hook returns `60.0` for any `_RcloneTransient`, so both `5` and `7` retry with the same 60 s wait
override. Every other non-`{0,5,7,9}` exit returns
`Error(CloudFault(op="rclone", exit_code=<code>, remote=<remote>))` with no retry; `_rclone` lowers an
exhausted-retry `_RcloneTransient` escape to that same `Error` rail so interior code never sees a
raised exit. The decoration is

```python
@stamina.retry(on=_rclone_transient_hook, attempts=3, wait_initial=2.0, wait_max=30.0, wait_jitter=1.0)
```

and `_rclone_transient_hook(exc) -> bool | float` returns `60.0` for `_RcloneTransient`, `True` for
`OSError` (spawn, exponential backoff), `False` otherwise. (rclone's documented exit codes:
`2` uncategorized, `3` dir-not-found, `4` file-not-found, `6` less-serious — none are produced by the
`copy`/`bisync` happy paths and all fall through to the non-retriable arm.)

## `pg_dump` / `pg_restore` — the database half

```
pg_dump <DSN> -F c -Z zstd:3 -f <tmp>/<ts>_maghz.dump -O --no-privileges
pg_restore -d <DSN> -c -O --no-privileges <tmp>/<dump>
```

`pg_dump` writes a custom-format archive (`-F c`), zstd-compressed at level 3 (`-Z zstd:3`, the
`-Z METHOD[:DETAIL]` form on PostgreSQL 18.4), ownerless (`-O --no-privileges`); `pg_restore -c`
drops-and-recreates objects before reload, also ownerless. `<DSN>` is the `MAGHZ_DATABASE_DSN` shape
on `DatabaseConfig`. The dump file is staged by the `_staging()` async context manager —
`tempfile.mkdtemp` yields an `anyio.Path`, and the `finally` offloads `shutil.rmtree(..., ignore_errors=True)`
to a worker thread inside `anyio.CancelScope(shield=True)` so a `fail_after` deadline that fires
mid-operation still tears the dir down. The builder enters it via
`stack.enter_async_context(_staging())` on the per-op `contextlib.AsyncExitStack`. Both tools run via
`anyio.run_process` under the same `CloudBoundary` exit map (the `"pg_dump"` / `"pg_restore"` arms;
any non-zero exit lifts to `Error(CloudFault(...))`).

The entire `run` operation — `pg_dump` plus the both-remote `drain` fan-out — is bounded by
`anyio.fail_after(cfg.cloud.op_timeout_s)` at the `Envelope`-returning CLI edge. `anyio.fail_after`
raises `TimeoutError` when the body misses the deadline (it converts the internal cancellation at its
own scope boundary), so the trip surfaces as a process-level failure, not a `CloudFault`. It
propagates out of `run` unwrapped; the `__main__.py` process-boundary handler's broad `except`
collapses it to a single fault envelope. This is the one sanctioned CLI-boundary use of
`fail_after`; the domain never opens a raw `anyio.create_task_group()` and never calls
`asyncio.wait_for`.
