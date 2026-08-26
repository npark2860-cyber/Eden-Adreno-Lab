# NEXT ACTION — Alias Synchronization Redundancy Diagnostic

Updated: 2026-08-27 KST

Status: **source/instrumentation/workflow prepared / no build authorized / no runtime yet**

## Fixed starting point

Repository: `npark2860-cyber/Eden-Adreno-Lab`

Exact Eden source remains:

`dc95cd09eea9749250fe31a3072684d341d19417`

Completed diagnostic branch:

`exp/x1-alias-copy-reasons`

Current prepared branch:

`exp/x1-alias-sync-redundancy`

The current branch was created from completed alias-route HEAD:

`26728e59c31c36a20ba1dc9d11e8a84e8d67cb74`

## Proven motivation

Matched alias-route runtime (`eden_log(8).txt`) established:

- `direct-route`: 100,021 scopes
- `direct-resolve-invalidate`: 100,021 scopes / outside 0
- `direct-vk-copy`: 100,021 scopes / outside 24,806
- `reinterpret-route`: 0
- `convert-route`: 0
- `direct-bpb-reinterpret`: 0
- whole-log attributed Draw outside-RP: 39,017
- direct-vk-copy share: **63.58%**

Resolved chain:

`SynchronizeAliases -> CopyImage -> TextureCacheRuntime::CopyImage -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

Do not reopen Vulkan route attribution in this experiment.

## Source-first work — COMPLETE

Exact dc95 was inspected before instrumentation.

Confirmed:

1. `AliasedImage` contains an alias `ImageId` plus `ImageCopy` regions; no per-alias dirty/up-to-date bit exists.
2. `ImageFlagBits::Alias` is not the synchronization freshness gate.
3. `MarkModification()` sets `GpuModified` and advances the image's `modification_tick` from the cache-global counter.
4. Exact dc95 can propagate existing modification ticks through image maintenance/copy paths.
5. `SynchronizeAliases()` selects a source only when its tick is newer than the destination tick at selection time.
6. The destination tick is advanced to the maximum selected source tick before the copy loop.
7. Selected sources are sorted by source tick.
8. The actual alias request is `CopyImage(dst=image_id, src=aliased->id, copies=aliased->copies)`.
9. `AddImageAlias()` builds the copy regions from source/destination subresources, offsets and extents.

Therefore `modification_tick` is used only as Eden's recency/version state. It is not interpreted as a byte-content hash.

See `ALIAS_SYNC_REDUNDANCY_MAP.md`.

## Passive instrumentation — PREPARED

Transplant:

`tools/adreno_lab/transplant_dc95_alias_sync_redundancy.py`

The hook is attached only to alias-copy requests issued by the existing `SynchronizeAliases()` alias-copy wrapper.

New aggregate marker:

`[X1-ALIAS-SYNC]`

Measured at the existing report interval, default 120 frames:

- total alias-copy requests
- unique `(dst ImageId, src ImageId)` pairs
- same-frame pair repeats
- same-Draw pair repeats
- consecutive-frame pair repeats
- same / advanced / regressed source `modification_tick`
- total and max copy-region count
- stable region signature from src/dst subresources, offsets and extents
- same pair + same signature repeats
- same pair + same source tick + same signature repeats (`sameStateSignature`)
- bounded tracker overflow

No copy-volume formula was added.

No per-copy logging was added.

## Bounded-state contract

- fixed capacity: 4,096 pair entries
- probe limit: 32
- no unbounded map/table growth
- state cleared/rotated at each report boundary
- overflow is counted explicitly

## Existing telemetry retained

The prepared diagnostic preserves:

- `other/texture/alias-copy`
- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/direct-vk-copy`
- `other/post-copy-barrier`
- Uniform / Vertex / Index / refresh counters

## Instrumentation-only safety contract

The current branch does not:

- skip or deduplicate a copy
- cache a copy result
- alter `modification_tick`
- force alias state up to date
- suppress `RequestOutsideRenderPassOperationContext()`
- suppress barriers
- batch `vkCmdCopyImage`
- move copies across Draw boundaries
- change Draw/Dispatch A/B defaults

## Workflow — PREPARED, NOT RUN

Workflow:

`.github/workflows/build-dc95-x1-alias-sync-redundancy.yml`

Artifact:

`Eden-dc95-X1-alias-sync-redundancy`

Trigger:

`workflow_dispatch` only.

The workflow checks out exact dc95 and has pre-configure checks for:

- exact source SHA
- Python syntax
- `git diff --check`
- exact alias semantic markers
- bounded table markers
- required report marker and region-signature markers
- retained direct-route/direct-vk-copy instrumentation
- alias-sync-only forbidden optimization/state-mutation diff scan
- no new scheduler-source touch
- existing exact-dc95 scheduler leak guards

## BUILD AUTHORIZATION BOUNDARY

**Do not start or re-run an ARM64 GitHub Actions build without fresh explicit user authorization.**

One authorization = one build attempt.

Current ARM64 attempts for `exp/x1-alias-sync-redundancy`: **0**.

Current authorization: **not granted**.

If a future authorized attempt fails, diagnose and fix the source/workflow but do not run again until another fresh authorization.

## Runtime contract after a future successful build

Use the matched setup:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- driver 512.863.0
- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- comparable field route containing normal ~20 FPS and slower sections when possible

Cross-check `[X1-ALIAS-SYNC]` against the retained direct alias-copy scopes/outside-RP counts before drawing a redundancy conclusion.

## Decision rules after runtime

### Strong redundancy evidence

High repeated-pair counts with unchanged source tick and identical copy-region signature, especially in the same frame or Draw, support a **separate** one-variable A/B experiment for only the proven redundant subset.

Do not implement that optimization in this diagnostic branch.

### Copies mostly justified by source changes

If source tick advances before most repeated pair copies, deduplication is not supported by this diagnostic.

### Many unique pairs, little repetition

If most copies are unique pairs, move the next diagnostic toward alias-set churn / why many aliases become synchronization candidates.

### Interpretation limit

Unchanged `modification_tick` means unchanged Eden version state for that source between observations. It does not independently prove byte-for-byte content identity.

## NEXT ACTION

Source preparation is complete.

**Stop here until fresh explicit build authorization.**

After authorization, start exactly one attempt of `Build dc95 X1 Alias Sync Redundancy` on `exp/x1-alias-sync-redundancy`.
