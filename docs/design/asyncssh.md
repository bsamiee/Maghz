# `asyncssh` (2.23.1)

Pure-Python asyncio SSHv2 client + SFTP over the `cryptography` backend. The sole VPS
transport for `admin/remote/`: `connection` establishment, `conn.run` remote exec, and
`SFTPClient` push/pull. New capability — nothing in `admin/` reaches the VPS today, so there
is no SSH surface to replace; `paramiko`, `subprocess` ssh, and shell-pipe `scp` are
out of scope by construction (blocking-IO peers with no anyio model).

The full provider surface — forward/reverse sessions, streamed `create_process`, the
forwarding family, key/cert mint-import-export, `match_known_hosts`, the complete fault
taxonomy — lives in the Rasm runtime catalog `libs/python/runtime/.api/asyncssh.md`. This
file is the domain-scoped slice: only the connection / exec / SFTP / TOFU / auth members
`admin/remote/connection.py` and `admin/remote/ops.py` compose, plus the exact wire types
the receipts project. It references that catalog; it does not restate it.

Imported unconditionally (never under `TYPE_CHECKING`): `beartype_this_package()` resolves
annotations at import time, so a guarded import breaks resolution. `asyncssh` ships
`py.typed` (verified on the installed wheel) — `ty` and `mypy --strict` type-check it
natively. No per-package mypy override is required; the `pg8000`-pattern hedge in the
worklist does not apply (that override exists only because `pg8000` lacks stubs). `ruff`
`TC002` is already disabled under the claw, so the eager third-party import is clean.
License EPL-2.0 OR GPL-2.0-or-later: consumed as an unmodified library dependency over its
public API, never vendored or modified in-tree.

## Connection — one options object, never keyword soup

`asyncssh.connect` accepts every `SSHClientConnectionOptions` field both as `**kwargs` and
as a single `options=` object. The law is one options object built once in
`target_options(target, cfg)`; the call site passes only the per-connection identity:

```python
async with asyncssh.connect(
    host=target.host,
    port=target.port,
    username=target.user,
    options=target_options(target, cfg),
) as conn:
    ...
```

`connect(host='', port=(), *, options=None, **kwargs)` returns an `SSHClientConnection` that
is itself an async context manager — `async with` closes it deterministically
(`close()` + `wait_closed()`) on scope exit. No connection pool: one `exec`/`deploy`
invocation owns one scoped connection under the anyio task scope. `guard(RetryClass.HTTP)`
wraps the `connect` coroutine for transient reconnect (see the fault taxonomy below).

`SSHClientConnectionOptions` is the only config carrier. The members `target_options` sets,
all verified present on `2.23.1`:

```python
asyncssh.SSHClientConnectionOptions(
    known_hosts=<str path | None>,          # resolved from KnownHostsPolicy match — see below
    connect_timeout=cfg.connect_timeout,    # float seconds
    login_timeout=cfg.connect_timeout,      # auth-phase deadline
    keepalive_interval=cfg.keepalive_interval,
    keepalive_count_max=cfg.keepalive_count_max,
    client_keys=[...],                      # Ed25519 SSHKey list, or agent keys
)
```

`known_hosts` is `str | Sequence | SSHKnownHosts | None`. The boundary is the
`KnownHostsPolicy` match in `target_options`, never a bare `None` flowing in from config:

```python
match policy:
    case "insecure":
        log.warning("ssh.host_key_verification_disabled")
        known_hosts = None           # the ONLY admitted None-source, behind an explicit arm + warning
    case Path() as p:
        known_hosts = str(p)
```

`None` is excluded from the `KnownHostsPolicy` vocabulary (`Literal["insecure"] | Path`), so
the `match` is total with no `| None` arm — the `None`-passes-silently failure mode is closed
at the type level, and `known_hosts=None` reaches `SSHClientConnectionOptions` only through
the audited `"insecure"` arm.

## `conn.run` — `check=True` is mandatory and explicit

```python
completed = await conn.run(command, check=True)   # check DEFAULTS to False
```

The real bound signature is `run(*args, check=False, timeout=None, **kwargs)` — `check`
defaults to `False`, so it must be passed explicitly. With `check=True`, a non-zero exit
raises `asyncssh.ProcessError`; the exit status is never inspected by hand. `ProcessError` is
caught by `async_boundary("remote.exec", ...)` and classified `boundary` — there is no manual
`completed.exit_status != 0` branch anywhere in `ops.py`. `encoding`/`input`/`env` and the
rest of `create_process`'s parameters pass through `**kwargs` (`run` is a thin
`create_process`+`communicate` wrapper); the remote command is built with `shlex.quote`, not
raw interpolation.

`SSHCompletedProcess` is a `Record` (not a stdlib namedtuple), with these exact field types —
this is the receipt-projection contract and the design's `ExecReceipt` typing must match it:

```text
exit_status : int | None
exit_signal : tuple[str, bool, str, str] | None     # (signal_name, core_dumped, msg, lang)
returncode  : int | None
stdout      : bytes | str | None
stderr      : bytes | str | None
env         : Mapping[str, str] | None
command     : str | None
subsystem   : str | None
```

`exit_signal` is a 4-tuple, NOT `str | None`. To land `ExecReceipt.exit_signal: str | None`
the projection extracts the signal name: `signal[0] if (signal := completed.exit_signal) else
None`. `ProcessError` carries the identical field set (`env`/`command`/`exit_status`/
`exit_signal`/`returncode`/`stdout`/`stderr`) plus `reason`/`lang`, so the receipt projects
the same way whether the run completes or raises — one projection, both paths.

## SFTP — push fan-out and artifact pull

`await conn.start_sftp_client()` yields an `SFTPClient` (async context manager). The members
`_push_tree` and `exec` compose:

```python
async with conn.start_sftp_client() as sftp:
    await sftp.makedirs(target.workroot, exist_ok=True)        # remote run-dir
    await sftp.put(                                            # per-directory push
        local_paths, remotedir,
        max_requests=cfg.remote.sftp_max_requests,             # threaded from RemoteConfig
        error_handler=_collect,                                # per-file fault -> notes
    )
    await sftp.mget(                                           # artifact pull (exec only)
        remote_paths, localpath=local_dir,
        recurse=True, error_handler=_collect,
    )
```

`put(localpaths, remotepath=None, *, recurse=False, max_requests=-1, error_handler=None)` and
`mget(remotepaths, localpath=None, *, recurse=False, max_requests=-1, error_handler=None)`:
`max_requests` is the parallel-outstanding-request bound (`-1` = library default), set per
call from `cfg.remote.sftp_max_requests`. The outer push fan-out across directories is owned
by `anyio.create_task_group()` under `anyio.CapacityLimiter(cfg.remote.sftp_push_concurrency)`
— `max_requests` is the per-transfer parallelism, the limiter is the per-directory
concurrency; they are orthogonal bounds, both load-bearing.

`error_handler` has the verified type `None | Literal[False] | Callable[[Exception], None]`
and these three modes:

- `None` (default): the first error raises after collecting; the transfer stops.
- `Literal[False]`: errors are silently ignored; the transfer continues.
- `Callable[[Exception], None]`: the handler is invoked per failing path and the transfer
  **continues** — the canonical mode. The callable receives the full `Exception` (typically
  `SFTPError`, but any exception the transfer raises), folds it into the notes tuple, and
  returns `None`; it does not re-raise. This is how a per-file `SFTPError` becomes a
  `DeployReceipt.push_notes` / `ExecReceipt.notes` entry instead of aborting the whole push.

`makedirs(path, attrs=SFTPAttrs(...), *, exist_ok=False)` — pass `exist_ok=True` so a
re-deploy is a clean no-op when the workroot already exists.

## TOFU bootstrap and credentials

```python
host_key: asyncssh.SSHKey | None = await asyncssh.get_server_host_key(host, port)
```

`get_server_host_key(host, port=(), *, options=None, ...) -> SSHKey | None` fetches the
server host key without authenticating — the one-time TOFU pin into `~/.ssh/known_hosts`
(or `MAGHZ_REMOTE_KNOWN_HOSTS`). A `None` return means the host offered no key and the
bootstrap **aborts**; it never proceeds to pin nothing.

Credentials are Ed25519 keys or ssh-agent — the exclusive mechanisms (no password literals,
no OP token, no device-code flow):

```python
key = asyncssh.generate_private_key("ssh-ed25519")             # mint a new keypair locally
key = asyncssh.read_private_key(path, passphrase=None)         # load from the settings-model path
async with asyncssh.connect_agent() as agent:                  # agent_path defaults to '' -> $SSH_AUTH_SOCK
    client_keys = await agent.get_keys()                       # Sequence[SSHKeyPair], no private-key copy
```

`generate_private_key(alg_name, comment=None, **kwargs) -> SSHKey`,
`read_private_key(filename, passphrase=None) -> SSHKey`, and
`connect_agent(agent_path='') -> SSHAgentClient` (empty-string default falls back to
`SSH_AUTH_SOCK`, not `None`). `SSHAgentClient.get_keys() -> Sequence[SSHKeyPair]` feeds
`SSHClientConnectionOptions(client_keys=...)`. All credential paths are gitignored; the
`gitleaks` gate fires on commit.

## Fault taxonomy → `CLASSIFY` — MRO precedence is load-bearing

The remote pass adds asyncssh rows to `CLASSIFY` in `admin/runtime/rails.py` (one row per
family, no new function, no parallel table). `remote` adds NO `BoundaryFault` case — the
four existing tags cover the surface:

| asyncssh fault | `BoundaryFault` | retryable |
| --- | --- | --- |
| `ConnectionLost`, `ChannelOpenError` | `resource` | yes — `guard(RetryClass.HTTP)` |
| `PermissionDenied`, `HostKeyNotVerifiable` | `api` | no — terminal |
| `ProcessError`, `SFTPError` | `boundary` | no |
| `msgspec.DecodeError` | `boundary` | no |
| `anyio.TimeoutError` | `deadline` | no |

The verified inheritance graph forces row ORDER. Every one of `ConnectionLost`,
`PermissionDenied`, and `HostKeyNotVerifiable` subclasses `DisconnectError`
(`ConnectionLost(DisconnectError)`, `PermissionDenied(DisconnectError)`,
`HostKeyNotVerifiable(DisconnectError)`), and `DisconnectError(Error)`. An `isinstance`-based
`CLASSIFY` scan therefore MUST place the narrow `api` rows
(`PermissionDenied`, `HostKeyNotVerifiable`) BEFORE any row that names the broad
`DisconnectError`, or a terminal auth/host-key failure is mis-scanned as retryable `resource`
and the connect guard retries an unauthorized credential. The resource row names the leaf
types `ConnectionLost`/`ChannelOpenError` explicitly — bare `DisconnectError` must NOT appear
in the resource row. Required scan order:

```text
(asyncssh.PermissionDenied, asyncssh.HostKeyNotVerifiable)        -> api        # narrow leaves first
(asyncssh.ConnectionLost, asyncssh.ChannelOpenError)             -> resource   # leaf transients only
(asyncssh.ProcessError, asyncssh.SFTPError)                      -> boundary
(msgspec.DecodeError,)                                            -> boundary
... before the (OSError,) and (Exception,) catch-alls
```

The same precedence governs `RetryClass.HTTP`'s `target`: the retry set is exactly
`{ConnectionLost, ChannelOpenError}` (transient network faults at the httpx timing band).
`PermissionDenied`/`HostKeyNotVerifiable` MUST NOT be in any retry `target` — they surface as
`BoundaryFault.api` on the first attempt. No `RetryClass.SSH` is introduced unless timing
parameters diverge materially from the HTTP band.

`Error(code, reason, lang)` and `SFTPError(code, reason, lang)` carry the numeric SSH
disconnect / SFTP status code, but the rail discriminates by exception TYPE, never by reading
the numeric field. `ProcessError(env, command, subsystem, exit_status, exit_signal,
returncode, stdout, stderr, reason='', lang='en-US')` carries the full completed-process
field set for receipt projection on the failure path.

## Logging

`asyncssh.set_log_level(level)` and `asyncssh.set_sftp_log_level(level)` route the package
logger into the structlog pipeline once at composition (in `__init__` under the claw), not
per call. `structlog.contextvars.bind_contextvars(rail="remote", op=op_name)` at the
entrypoint scope propagates across the anyio task boundaries the push fan-out opens.
