# `watchfiles`

Rust-backed filesystem watcher. Owns the Watch-trigger lane of the automation engine: a
single `awatch` async generator yields debounced change batches that the engine maps to
trigger fires. New capability — nothing in `admin/` currently watches the filesystem, so
there is no surface to replace.

## `awatch` — the watch generator

```python
from watchfiles import awatch

async for changes in awatch(
    *paths,
    watch_filter=...,      # BaseFilter instance or None
    debounce=1600,         # ms; coalesce a burst into one batch
    step=50,               # ms poll granularity
    stop_event=...,        # anyio.Event; set -> generator exits cleanly
    recursive=True,
):
    ...
```

`awatch(*paths)` accepts one or more `str | os.PathLike` roots. Each yielded value is a
`set[tuple[Change, str]]` — a debounced batch, never a single event. The generator is the
sole watch primitive; do not poll, stat-loop, or shell out to a file watcher.

`stop_event` is an `anyio.Event` owned by the engine's cancel scope. When the scope tears
down it sets the event and the generator exits cleanly on its next `step` boundary — no
`CancelledError` swallow, no thread to join. This is the lane-shutdown seam.

`debounce`/`step` are milliseconds; the engine owns the values (no blocking poll elsewhere,
since the debounce already coalesces bursts). `recursive=True` watches subtrees.

## Filters — `watch_filter=` correspondence table

One `watch_filter=` kwarg selects from a correspondence table in the engine's `[TABLES]`;
there is no per-event consumer-side filtering:

```python
from watchfiles import BaseFilter, DefaultFilter, PythonFilter

#   "default" -> DefaultFilter()    # skips .git, __pycache__, editor swap/temp files
#   "python"  -> PythonFilter()     # DefaultFilter + only *.py / *.pyx / *.pyi
#   "none"    -> None               # every raw change
```

`DefaultFilter` and `PythonFilter` subclass `BaseFilter`; a custom filter subclasses
`BaseFilter` and overrides `__call__(self, change: Change, path: str) -> bool`. The filter is
constructed once and passed by instance, not re-evaluated per consumer.

## `Change` — event kind

```python
from watchfiles import Change   # IntEnum: Change.added, Change.modified, Change.deleted
```

`Change.raw_str()` returns the lowercase event name (`"added"`/`"modified"`/`"deleted"`) for
structlog context alongside the path. It feeds diagnostics, not a receipt field — the receipt
carries the static `TriggerTag` literal, not the per-event change kind.
