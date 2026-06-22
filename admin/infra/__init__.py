"""Infrastructure package: the Pulumi stack definition and its Automation API runner.

`runner.run` is the single polymorphic stack verb over `StackOp`; `stack.define` is the
desired-state program it converges. The CLI mounts `run` directly.
"""

from admin.infra.runner import run, StackDetail, StackOp
from admin.infra.stack import define


__all__ = ["StackDetail", "StackOp", "define", "run"]
