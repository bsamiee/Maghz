"""Maghz operator package bootstrap.

Installs the beartype import claw before any submodule loads, so every public callable
in `admin.*` is type-checked at its boundary. Logging and settings are resolved by the
entrypoint, not at import, so a config fault can still surface as a fault envelope.
Every submodule declares its annotations in claw-decorable form — a name is defined
before the callable that hints it — so the claw decorates the whole package warning-free.
"""

from beartype import BeartypeConf
from beartype.claw import beartype_this_package


beartype_this_package(conf=BeartypeConf(is_color=False))
