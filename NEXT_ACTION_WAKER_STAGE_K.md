# NEXT ACTION — Waker Stage K Runtime Work-Object Semantic Mapping

Updated: 2026-09-01 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_WORK_TARGET_RUNTIME.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_PAIR_PARTIAL_MAPPING.md`

Use GitHub documents as source of truth. Do not reconstruct state from chat guesses.

## Fixed baseline / branch

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent ARM workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

Current ARM64 authorization:

**NONE**

Do not build/rebuild/rerun Windows ARM64 without a fresh explicit authorization. No ARM build is needed for the immediate next action.

## Exact runtime / NSO identity

Current x26 runtime log:

`eden_log.txt`

Confirmed:

- Eden exact baseline: `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- renderer: Vulkan
- GPU: Qualcomm Adreno X1-85
- resolution: `Res1X`
- exact main build ID: `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- x26 Stage K work-object fields are populated.

Use ASLR-normalized `main+offset` only for durable analysis.

## x26 pair interpretation

The resolver records the selected work object's vtable members:

`workTopN=<vtable+0x10 offset>/<vtable+0x60 offset>/<ticks>/<count>/<percent>`

For the known ModuleSystem family only:

- `vtable+0x10 = main+0x2af1230` is the common ModuleSystem shim;
- that shim tail-dispatches to the component's `vtable+0x60` target.

For a non-common-shim object, `vtable+0x60` is a stable secondary vtable fingerprint/member pointer until static control flow proves a stronger execution meaning.

Do not call every second pair member a concrete executed work target.

## One dominant non-common owner — CLOSED

Runtime pair:

`main+0x86bc04 -> main+0x2ada93c`

Exact prior NSO analysis already proved `main+0x86bc04` belongs to the concrete:

**EventModuleSubWorker**

Therefore this x26 work-object pair owner is now closed as **EventModuleSubWorker**.

The individual semantic method name of `main+0x2ada93c` remains unassigned; do not invent one.

## Immediate next action — OFFLINE ONLY

Two dominant non-common owners remain unresolved:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x244fc20 -> main+0x2ad6b20`

Use the exact dumped TOTK 1.2.1 main image:

`main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`

For each remaining pair, trace:

- `vtable+0x10` function code shape;
- the owning vtable and adjacent slots;
- callers / xrefs;
- constructors/destructors;
- registration tables;
- nearby names/strings/RTTI-like data;
- relation to already-resolved Stage K anchors.

The exact NSO bytes are not currently visible in the active uploaded-file set. Re-obtain/re-upload the same exact dump before assigning either semantic name. Do not substitute another TOTK build or infer names from offset proximity.

Priority order:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x244fc20 -> main+0x2ad6b20`
3. map the individual `main+0x2ada93c` EventModuleSubWorker vtable member only if useful after owner attribution is complete.

## Current x26 cadence correlation

Current uploaded x26 log provides:

- fast / swap2: frames `960`, `1080`
- slow / swap3 available in this file: frames `1320`, `1440`, `1560`

A current-x26 `frame=1680` record with `workResolvedN` was not found. Do not mix the older 2026-08-30 Stage K frame `1680` record, which predates the x26 fields, into this comparison.

Partial current-file slow3/fast pair-tick ratios:

| Pair / owner | Producer 0 | Producer 1 |
|---|---:|---:|
| `0x96e2a8 -> 0x26936d0` | `1.242x` | `1.517x` |
| `EventModuleSubWorker` (`0x86bc04 -> 0x2ada93c`) | `1.673x` | `1.234x` |
| `0x244fc20 -> 0x2ad6b20` | `0.895x` | top-4 censored; exact ratio unavailable |

Across the three available slow windows, the first two rows together average approximately `33.24%` of producer-0 CPU ticks and `28.87%` of producer-1 CPU ticks.

These are current-file partial correlations, not a sole-cause claim and not a substitute for a future fourth slow x26 window if one becomes available.

## Stop condition

Stop after the two remaining semantic owners are mapped and their existing runtime correlation is interpreted.

Do not create Stage L or implement behavior-changing scheduler/GPU/QueueBuffer/wait/signal/priority/affinity/yield changes from this evidence alone.
