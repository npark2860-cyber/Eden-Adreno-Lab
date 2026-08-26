# NEXT ACTION — Alias Synchronization Redundancy Diagnostic

Updated: 2026-08-27 KST

Status: **next experiment specification / no build authorized**

## Starting point

Repository: `npark2860-cyber/Eden-Adreno-Lab`

Exact Eden source must remain:

`dc95cd09eea9749250fe31a3072684d341d19417`

Completed diagnostic branch:

`exp/x1-alias-copy-reasons`

Recommended next branch:

`exp/x1-alias-sync-redundancy`

Create the next branch from the completed alias-copy branch so the proven telemetry chain remains available. Do not change the upstream Eden source SHA.

## Proven fact that motivates this experiment

`eden_log(8).txt` resolved the dominant alias outside-RP path:

`SynchronizeAliases -> CopyImage -> TextureCacheRuntime::CopyImage -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

Whole-log alias child totals:

- `direct-route`: 100,021 scopes
- `direct-resolve-invalidate`: 100,021 scopes / outside 0
- `direct-vk-copy`: 100,021 scopes / outside **24,806**
- `reinterpret-route`: 0
- `convert-route`: 0
- `direct-bpb-reinterpret`: 0

Whole-log attributed Draw outside-RP: **39,017**.

`direct-vk-copy` share: **63.58%**.

Do not spend another experiment splitting the Vulkan `CopyImage` implementation. The implementation path is already known.

## Diagnostic question

Determine **why `SynchronizeAliases()` requests so many direct image copies** and whether a significant fraction are redundant.

The first pass is telemetry-only. It must not skip, merge, delay, suppress or reorder any copy.

## Source-first work

Before modifying code, inspect exact dc95 definitions and semantics for:

- `TextureCache<P>::SynchronizeAliases()`
- `TextureCache<P>::CopyImage()`
- `AliasedImage`
- `Image::modification_tick`
- any existing alias up-to-date / dirty / overlap state
- frame tick / Draw work serials already available to the profiler

Do not assume `modification_tick` means “contents identical” until its write/update semantics are verified from source.

## Required passive measurements

Instrument only the alias-copy requests issued from `SynchronizeAliases()`; do not count unrelated `CopyImage()` users.

At minimum collect bounded aggregate telemetry for each reporting interval:

1. **total alias copy requests**
2. **unique `(dst ImageId, src ImageId)` pairs**
3. **same pair repeated within one frame**
4. **same pair repeated within one Draw work scope**, if a stable Draw serial can be obtained without changing behavior
5. **same pair repeated across consecutive frames**
6. **source `modification_tick` relation**
   - current source tick
   - last source tick seen when that same pair was copied
   - count same-tick repeats vs advanced-tick repeats
7. **copy-region signature**
   - number of regions
   - stable hash/signature from src/dst offsets, subresources and extents
   - count identical-signature repeats for the same pair
8. **copy volume**, only if exact dc95 exposes a safe existing helper to calculate it correctly
   - do not invent a byte formula for compressed/block formats

## Logging design

Prefer one bounded summary line per existing 120-frame report interval, for example:

`[X1-ALIAS-SYNC] frame=... copies=... uniquePairs=... sameFrame=... sameDraw=... consecutiveFrame=... sameSrcTick=... advancedSrcTick=... sameSignature=...`

Optional: emit a small fixed top-N list of the most repeated pairs at report time.

Do **not** log every alias copy. Per-copy logging would perturb the hot path and contaminate timing.

Any pair-tracking table must be bounded and cleared/rotated at a defined interval. Do not create unbounded runtime memory growth.

## Preserve existing telemetry

The next build must retain the currently proven categories so the new diagnostic can be cross-checked against the previous runtime:

- `other/texture/alias-copy`
- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/direct-vk-copy`
- `other/post-copy-barrier`
- existing Uniform / Vertex / Index / refresh counters

A successful run should still show approximately the same order of magnitude for direct alias-copy scopes and outside-RP events on a comparable gameplay route.

## Safety constraints

First diagnostic build is **instrumentation-only**.

Do not:

- skip a repeated copy
- cache a copy result
- alter `modification_tick`
- mark aliases up to date artificially
- suppress `RequestOutsideRenderPassOperationContext()`
- suppress barriers
- batch `vkCmdCopyImage`
- move copies across Draw boundaries
- change render-pass policy
- change Draw/Dispatch A/B defaults

Draw/Dispatch skip must remain OFF.

## Build/workflow preparation

Prepare a new transplant script and a manual-only ARM64 workflow, following the exact dc95 build chain used by the successful alias-copy diagnostic.

Recommended names:

- `tools/adreno_lab/transplant_dc95_alias_sync_redundancy.py`
- `.github/workflows/build-dc95-x1-alias-sync-redundancy.yml`
- artifact: `Eden-dc95-X1-alias-sync-redundancy`

Add preflight checks for:

- exact profiler marker strings
- bounded tracking state
- `git diff --check`
- no scheduler behavior leakage
- no skip/suppress optimization code
- exact dc95 source SHA

## BUILD AUTHORIZATION BOUNDARY

**Do not start or re-run an ARM64 GitHub Actions build while preparing this experiment.**

A build requires a fresh explicit user authorization.

**One authorization = one build attempt only.**

If a future authorized build fails, diagnose and fix the source/workflow but do not run again without another fresh permission.

## Runtime contract after a future successful build

Use the same matched setup:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- driver 512.863.0
- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- comparable field route containing both normal ~20 FPS and slower sections when possible

## Decision rules after runtime

### Strong redundancy evidence

If the same pair is copied repeatedly with:

- unchanged verified source modification state, and
- identical copy-region signature,

especially multiple times in one frame or one Draw, then prepare a **separate one-variable A/B experiment** that skips only the proven redundant subset. Do not implement that optimization in the diagnostic build itself.

### Copies mostly justified by source changes

If source state advances before most repeated copies, deduplication is not supported. Then investigate whether required copies can be coalesced/batched or scheduled with fewer render-pass transitions, but only in a later experiment.

### Many unique pairs, little repetition

If most copies are unique pairs, the issue is alias-set churn rather than duplicate requests. Move the next diagnostic toward why so many aliases become synchronization candidates.

## Completion criteria for this next task

Before asking for build authorization, the next task should leave the repository with:

- a new experiment branch
- source-verified passive instrumentation
- static/preflight validation
- manual-only workflow
- updated `CURRENT_HANDOFF.md`
- **zero new ARM64 runs**
