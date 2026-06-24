"""Runtime substrate: the typed rail, lane drain, resilience, and receipt owners every domain composes.

`rails` carries the domain-internal `RuntimeRail`/`BoundaryFault`, the `trapped` boundary aspect, the
`traversed` disposition fold, the `railed` do-notation builder, and the `lower` CLI seam; `lanes` the
one bounded `drain`; `resilience` the `RetryClass` policy table and `guard`/`retrying`/`install`;
`receipts` the `Receipt` evidence family and the `Signals` log service plus the `@receipted`/`@drained`
aspects. No domain re-implements these — it composes the canonical owners re-exported here.
"""

from admin.runtime.lanes import Admit, ContentKey, drain, DrainReceipt, feed, LanePolicy, LaneSource, StagePlan
from admin.runtime.rails import async_boundary, boundary, BoundaryFault, Disposition, lower, railed, RuntimeRail, trapped, traversed
from admin.runtime.receipts import drained, Receipt, ReceiptContributor, receipted, Signals
from admin.runtime.resilience import guard, guard_sync, guarded, guarded_sync, install, Policy, RetryClass, retrying, RetryMode


__all__ = [
    "Admit",
    "BoundaryFault",
    "ContentKey",
    "Disposition",
    "DrainReceipt",
    "LanePolicy",
    "LaneSource",
    "Policy",
    "StagePlan",
    "Receipt",
    "ReceiptContributor",
    "RetryClass",
    "RetryMode",
    "RuntimeRail",
    "Signals",
    "async_boundary",
    "boundary",
    "drain",
    "drained",
    "feed",
    "guard",
    "guard_sync",
    "guarded",
    "guarded_sync",
    "install",
    "lower",
    "railed",
    "receipted",
    "retrying",
    "trapped",
    "traversed",
]
