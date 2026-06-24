"""Infrastructure package: the Pulumi stack runner and its folded desired-state program.

`runner.run` is the single polymorphic stack verb over `StackOp`; the desired-state program it converges
is folded into `runner` as the function-local `_define`, so the runner and the resources it converges are
one owner. The CLI mounts `run` directly.
"""

from admin.infra.runner import run, StackDetail, StackOp


__all__ = ["StackDetail", "StackOp", "run"]
