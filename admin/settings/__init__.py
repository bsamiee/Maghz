"""Settings package: the one validated config surface the CLI, Pulumi infra, and every rail read.

`MaghzSettings` is the single owner of every environment value — no other code reads `os.environ`.
Re-exports the canonical owner in `admin.settings.config`: the `MaghzSettings` root, its nine
validated subgroups in field-declaration order (`DatabaseConfig`, `OllamaConfig`, `InfraConfig`,
`RemoteConfig`, `IntegrationsConfig`, `McpServerSettings`, `AutomationConfig`, `CloudConfig`,
`ObservabilityConfig`), the `RemoteCredentials` per-remote credential surface, the closed `Remote`
cloud-backup vocabulary, the `RemoteTable` typed credential map, the `LogFormat`/`LogLevel`
observability axes, and the process-wide `settings` accessor. This barrel is the public config
surface every CLI command, Pulumi program, and rail imports from; reaching past it into
`admin.settings.config` is a boundary leak. The beartype import claw is installed once at the
`admin.*` package root, so every re-exported callable is already type-checked at its boundary; this
barrel adds no logic.
"""

from admin.settings.config import (
    AutomationConfig,
    CloudConfig,
    DatabaseConfig,
    InfraConfig,
    IntegrationsConfig,
    LogFormat,
    LogLevel,
    MaghzSettings,
    McpServerSettings,
    ObservabilityConfig,
    OllamaConfig,
    Remote,
    RemoteConfig,
    RemoteCredentials,
    RemoteTable,
    settings,
)


# --- [EXPORTS] -------------------------------------------------------------------------

__all__ = [
    "AutomationConfig",
    "CloudConfig",
    "DatabaseConfig",
    "InfraConfig",
    "IntegrationsConfig",
    "LogFormat",
    "LogLevel",
    "MaghzSettings",
    "McpServerSettings",
    "ObservabilityConfig",
    "OllamaConfig",
    "Remote",
    "RemoteConfig",
    "RemoteCredentials",
    "RemoteTable",
    "settings",
]
