"""Runtime substrate: the typed rail, lane drain, resilience, and receipt owners every domain composes.

`rails` carries the domain-internal `RuntimeRail`/`BoundaryFault`; `lanes` the one bounded `drain`;
`resilience` the `RetryClass` policy table and `guard`/`retrying`/`install`; `receipts` the `Receipt`
evidence family and the `Signals` log service plus the `@receipted`/`@drained` aspects. No domain
re-implements these — it composes the canonical owners re-exported here.
"""

from admin.runtime.lanes import Admit, ContentKey, drain, DrainReceipt, LanePolicy
from admin.runtime.rails import async_boundary, boundary, BoundaryFault, RuntimeRail
from admin.runtime.receipts import drained, Receipt, ReceiptContributor, receipted, Signals
from admin.runtime.resilience import guard, install, Policy, RetryClass, retrying, RetryMode


__all__ = [
    "Admit",
    "BoundaryFault",
    "ContentKey",
    "DrainReceipt",
    "LanePolicy",
    "Policy",
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
    "guard",
    "install",
    "receipted",
    "retrying",
]
