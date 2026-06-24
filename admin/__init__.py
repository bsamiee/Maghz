"""Maghz operator package bootstrap.

Installs the beartype import claw before any submodule loads, so every public callable
in `admin.*` is type-checked at its boundary. Logging and settings are resolved by the
entrypoint, not at import, so a config fault can still surface as a fault envelope.
"""

import warnings

from beartype import BeartypeConf
from beartype.claw import beartype_this_package
from beartype.roar import BeartypeClawDecorWarning


# The claw cannot decorate the PEP 695 generic `DrainReceipt[T]` or the cycle-deferred `spawn`
# (its `RetryClass | None` forward ref); it skips them with a warning and type-checks every other
# callable. Filter the benign warning rather than force it fatal, so the package still imports.
warnings.filterwarnings("ignore", category=BeartypeClawDecorWarning)
beartype_this_package(conf=BeartypeConf(is_color=False))
