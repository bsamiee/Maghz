# Claude Workspace Setup

## [01]-[SESSION_START]

`settings.json` runs `hooks/setup-env.sh` on startup, resume, and compaction. The hook writes selected API tokens plus optional PATH additions to `CLAUDE_ENV_FILE` for sub-agent/tool inheritance. It does not source local shell files, install tools, write profiles, or call network services.

[VARIABLES]:
- `CLAUDE_ENV_EXPORT_KEYS` - Extra env var names to persist, separated by spaces or commas.
- `CLAUDE_TOOL_PATHS` - Colon-separated PATH entries to prepend when directories exist.
- `CLAUDE_EXTRA_PATH` - Backward-compatible alias used when `CLAUDE_TOOL_PATHS` is unset.
- `CLAUDE_ALLOW_MISSING_TOOL_PATHS=1` - Preserve explicit PATH entries even when the directory is absent.

## [02]-[HOST_BOOTSTRAP]

`scripts/bootstrap-cli-tools.sh` is manual. Default mode is `check`, which reports missing tools without mutating the host.

[COMMANDS]:
- `bash .claude/scripts/bootstrap-cli-tools.sh check`
- `bash .claude/scripts/bootstrap-cli-tools.sh apply`

[MUTATION_FLAGS]:
- `CLAUDE_BOOTSTRAP_BIN_DIR` - User-local binary install directory; defaults to `CARGO_HOME/bin`.
- `CLAUDE_BOOTSTRAP_ALLOW_SUDO=1` - Permit package-manager prerequisite installs.
- `CLAUDE_BOOTSTRAP_WRITE_PROFILE=1` - Permit profile PATH writes.
- `CLAUDE_BOOTSTRAP_PROFILE=/path/to/profile` - Profile target for PATH writes.
- `CLAUDE_BOOTSTRAP_ALLOW_NETWORK=1` - Permit package and tool downloads.
- `CLAUDE_BOOTSTRAP_ALLOW_REMOTE_INSTALLERS=1` - Permit remote installer scripts and release assets.

## [03]-[BOUNDARIES]

[CRITICAL]:
- [ALWAYS] Keep startup non-mutating and deterministic.
- [ALWAYS] Require explicit variables before host, profile, sudo, or network changes.
- [NEVER] source local shell files during startup.
- [NEVER] wire host bootstrap into `SessionStart`.
