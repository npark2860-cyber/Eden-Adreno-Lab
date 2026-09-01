# DEBUG HISTORY — Waker Stage K Non-Common Pair Partial Mapping

Date: 2026-09-01 KST

## Scope

Offline continuation of Stage K x26 work-object semantic attribution.

Fixed Eden baseline remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Branch HEAD observed before this documentation update:

`1826bbeb399d78e1a591021b789e7417bcbe7972`

No Windows ARM64 build/rebuild/rerun was performed. Current ARM64 authorization remains **NONE**. No source, workflow, baseline, scheduler, GPU, wait/signal, priority, affinity, QueueBuffer, or cadence behavior was changed.

Exact TOTK 1.2.1 main build ID remains:

`9B4E43650501A4D4489B4BBFDB740F26AF3CF85`

## x26 pair semantics — precision correction

The Stage K x26 resolver follows the scheduler node stored in x26 to the selected work object, then reads that object's vtable.

It records:

- vtable `+0x10` as the first normalized pair member (`shim_offset`);
- vtable `+0x60` as the second normalized pair member (`work_target_offset`).

For the known ModuleSystem class family, `vtable+0x10 = main+0x2af1230` is the common shim and that shim tail-dispatches to `vtable+0x60`. Therefore the second member is a proven concrete ModuleSystem execution target for that family.

For a **non-common-shim** class, the same `+0x60` value is a durable vtable fingerprint/member-method pointer, but it must not automatically be described as the method executed by the `+0x10` call unless static control flow proves that relation.

The existing analyzer already preserves this distinction by labeling only `main+0x2af1230` as the common ModuleSystem shim and reporting other first members as non-ModuleSystem shims.

## Pair owner closed: EventModuleSubWorker

Runtime recurring pair:

`main+0x86bc04 -> main+0x2ada93c`

The exact-NSO static record `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md` already proved through vtable/constructor/registration tracing that `main+0x86bc04` belongs to the concrete `EventModuleSubWorker` worker path:

`EventModuleSubWorker -> main+0x86bc04 -> main+0x86bd40 -> selected-object virtual operation -> nn::os::WaitLightEvent`

Because the x26 resolver's first pair member is the selected work object's vtable `+0x10` method, the object/pair owner is now durably classified as:

**EventModuleSubWorker**

The individual semantic method name of the same vtable's `+0x60` member `main+0x2ada93c` is **not** established by the current evidence and is not invented here.

This closes owner attribution for one of the three dominant non-common pairs without another runtime experiment.

## Remaining unresolved non-common owners

Exact offline NSO mapping is still required for:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x244fc20 -> main+0x2ad6b20`

Do not infer names from offset proximity or from runtime frequency.

The exact dumped `main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso` bytes are not currently visible in the active uploaded-file set. Re-obtain/re-upload the same exact dump before assigning these two semantic names. Do not substitute another TOTK revision.

## Current x26 log cadence availability

The current uploaded x26 runtime log contains populated `workResolvedN` / `workTopN` records through frame `1560`.

A search for an x26 `frame=1680` record containing `workResolvedN` and the dominant x26 pair did not find such a record in this current log. Older 2026-08-30 Stage K logs do contain frame `1680`, but they predate the x26 work-target fields and must **not** be mixed into this x26 correlation.

Therefore current-file correlation uses:

- fast / swap2: frames `960`, `1080`;
- slow / swap3 currently available: frames `1320`, `1440`, `1560`.

The nominal fourth slow window `1680` remains unavailable in the current x26 log file.

## Partial current-file slow/fast correlation

These ratios use the arithmetic mean of pair ticks across the two available fast windows versus the three available slow windows. They are a partial current-file correlation, not a replacement for a future four-slow-window aggregate if an x26 frame `1680` record becomes available.

### `main+0x96e2a8 -> main+0x26936d0`

- producer 0: fast mean `6,471,428` ticks; slow3 mean `8,037,320`; slow3/fast = **1.242x**
- producer 1: fast mean `5,765,174.5`; slow3 mean `8,743,099.3`; slow3/fast = **1.517x**

### `EventModuleSubWorker` pair `main+0x86bc04 -> main+0x2ada93c`

- producer 0: fast mean `3,522,753` ticks; slow3 mean `5,893,140`; slow3/fast = **1.673x**
- producer 1: fast mean `1,954,985.5`; slow3 mean `2,411,603.7`; slow3/fast = **1.234x**

### `main+0x244fc20 -> main+0x2ad6b20`

- producer 0: fast mean `1,451,371` ticks; slow3 mean `1,299,235.7`; slow3/fast = **0.895x**
- producer 1 cannot be given an exact slow3 ratio from the current top-4 record because this pair is censored from at least some required slow producer-1 windows.

Across the three available slow windows, the two dominant pairs `0x96e2a8/...` plus `EventModuleSubWorker` together account for an average of approximately:

- producer 0: **33.24%** of total producer CPU ticks;
- producer 1: **28.87%**.

This makes those two non-common object families the immediate semantic priority ahead of interpreting smaller common-ModuleSystem targets. It does **not** establish a sole causal owner.

## Decision

1. Runtime x26 identity is valid and the analyzer's common-vs-non-common distinction is correct.
2. `main+0x86bc04 -> main+0x2ada93c` owner is **EventModuleSubWorker**.
3. `main+0x96e2a8 -> main+0x26936d0` remains the dominant unresolved owner and is first priority for exact-NSO tracing.
4. `main+0x244fc20 -> main+0x2ad6b20` remains the second unresolved owner.
5. No ARM build and no behavior-changing experiment is justified before those two semantic owners are closed.
