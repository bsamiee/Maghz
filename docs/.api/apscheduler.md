# `apscheduler` (4.x async-first)

Schedule-trigger lane of the automation engine. APScheduler 4.x is the async-first release:
`AsyncScheduler` drives its own `anyio` task group internally and integrates with the engine's
`anyio` lane group. The 3.x `AsyncIOScheduler`+`AsyncIOExecutor` path is asyncio-native only
and couples the engine to the asyncio backend, violating the anyio mandate — it is rejected.
4.x final is unpublished on PyPI; the manifest pins `apscheduler>=4.0.0a6` (latest prerelease).
Lift the floor to `>=4.0.0` once final lands.

## `AsyncScheduler` — async context manager

```python
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger

async with AsyncScheduler() as scheduler:
    await scheduler.add_schedule(
        func,
        CronTrigger.from_crontab(spec.cron, timezone=spec.timezone),
        id=spec_id,
        conflict_policy=ConflictPolicy.replace,
        misfire_grace_time=120,
    )
    await scheduler.run_until_stopped()
```

`AsyncScheduler` is one instance per lane, entered as `async with` inside the engine's anyio
task group; its `__aenter__`/`__aexit__` own the full lifecycle, so there is no `shutdown(wait=True)`
to offload via `anyio.to_thread.run_sync`. `add_schedule(func_or_task_id, trigger, *, id=,
conflict_policy=, misfire_grace_time=, ...)` registers a schedule; `run_until_stopped()` blocks
the lane until the scope tears down.

## `CronTrigger.from_crontab`

```python
from apscheduler.triggers.cron import CronTrigger

trigger = CronTrigger.from_crontab(spec.cron, timezone=spec.timezone)
```

`from_crontab(expr, timezone=...)` parses a standard 5-field crontab string into a trigger.
This is the sole cron entry — do not hand-decompose fields into the `CronTrigger(...)` keyword
constructor.

## `ConflictPolicy`

```python
from apscheduler import ConflictPolicy   # do_nothing | replace | exception
```

`ConflictPolicy.replace` is the registration policy for `add_schedule`: re-adding a schedule
with the same `id` replaces it idempotently, the correct behavior when the engine re-reads its
spec set on restart.

## Job events — `subscribe` + `JobReleased`

```python
from apscheduler import JobReleased

scheduler.subscribe(callback, {JobReleased})
```

`subscribe(callback, event_types)` registers the single observability seam for NDJSON ledger
append per fire. The `JobReleased` event carries (attrs fields, verified against 4.0.0a6):
`timestamp`, `job_id`, `scheduler_id`, `task_id`, `schedule_id`, `scheduled_start`,
`started_at`, `outcome: JobOutcome`, and `exception_type` / `exception_message` /
`exception_traceback`. The 4.0.0a6 event does not carry a `return_value` or `scheduled_fire_time`
field; the engine reads the fired `AutomationReceipt` from the task's own ledger write, not from
the event payload, and uses `scheduled_start` as the tick timestamp.

## `JobOutcome`

```python
from apscheduler import JobOutcome
# success | error | missed_start_deadline | deserialization_failed | cancelled | abandoned
```

`JobOutcome.success` is the completed-fire arm. The missed-tick outcome is
`JobOutcome.missed_start_deadline` (there is no `JobOutcome.missed` in 4.0.0a6) — it projects to
a `Status.SKIP` receipt in the NDJSON automation ledger. `JobOutcome.error` /
`JobOutcome.cancelled` / `JobOutcome.abandoned` map to fault receipts via the same projection arm.
