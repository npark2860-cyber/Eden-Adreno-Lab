# CURRENT HANDOFF — Eden Adreno X1 alias synchronization redundancy

Updated: 2026-08-27 KST

## Fixed baseline

- Repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Completed texture experiment: `exp/x1-texture-fill-reasons`
- Completed alias-route experiment: `exp/x1-alias-copy-reasons`
- Current experiment: `exp/x1-alias-sync-redundancy`

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Current branch lineage

Completed alias-route branch HEAD used as the parent:

`26728e59c31c36a20ba1dc9d11e8a84e8d67cb74`

message:

`docs: hand off alias synchronization redundancy work`

`exp/x1-alias-sync-redundancy` was created directly from that HEAD.

## Latest successful diagnostic build — Alias Sync Redundancy

Authorized attempt count: **1**

- workflow: `Build dc95 X1 Alias Sync Redundancy`
- workflow file: `.github/workflows/build-dc95-x1-alias-sync-redundancy.yml`
- run: `33024690895`
- job: `98363162523`
- run attempt: `1`
- trigger event: `push`
- build head: `804f394c5db280f842a01113e6ca92f7ad57d219`
- result: **success**
- exact dc95 verification: **success**
- all prior transplants: **success**
- alias-sync redundancy transplant: **success**
- instrumentation preflight: **success**
- ARM64 configure: **success**
- ARM64 build/link: **success**
- package: **success**
- upload: **success**
- artifact: `Eden-dc95-X1-alias-sync-redundancy`
- artifact id: `9628554127`
- artifact size: `31,300,012` bytes
- artifact SHA-256: `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

The one-shot branch `push` trigger was removed immediately after launch. The restore commit was:

`abad21031730d0f97eaef79b50a79308c4b50534`

message:

`ci: restore alias sync workflow to manual only`

After completion, the branch had exactly **1** Actions run for this experiment. No rerun occurred.

Current workflow trigger is again:

`workflow_dispatch` only.

## Previous proven alias-route runtime

Matched setup:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF

Runtime log: `eden_log(8).txt`.

Whole-log alias child totals:

| Bucket | Scopes | Outside-RP |
| --- | ---: | ---: |
| `other/texture/alias-copy/direct-route` | **100,021** | 0 |
| `other/texture/alias-copy/direct-resolve-invalidate` | **100,021** | 0 |
| `other/texture/alias-copy/direct-vk-copy` | **100,021** | **24,806** |
| `other/texture/alias-copy/reinterpret-route` | 0 | 0 |
| `other/texture/alias-copy/convert-route` | 0 | 0 |
| `other/texture/alias-copy/direct-bpb-reinterpret` | 0 | 0 |

Whole-log attributed Draw outside-RP: **39,017**.

`direct-vk-copy`: **24,806 / 39,017 = 63.58%**.

Resolved dominant path:

`Draw Configure`
-> `FillImageViews`
-> `PrepareImage`
-> `SynchronizeAliases`
-> `CopyImage`
-> generic direct route
-> `TextureCacheRuntime::CopyImage`
-> `scheduler.RequestOutsideRenderPassOperationContext()`
-> `vkCmdCopyImage`

Do not reopen generic reinterpret, generic convert, direct BytesPerBlock reinterpret fallback, or resolve-shadow invalidation as current dominant causes without materially new evidence.

Do not suppress `RequestOutsideRenderPassOperationContext()`; `vkCmdCopyImage` must execute outside the render pass.

## Exact dc95 alias semantics used by the new diagnostic

- `AliasedImage` contains alias `ImageId` plus `std::vector<ImageCopy>`; no per-alias dirty/up-to-date boolean exists.
- `ImageFlagBits::Alias` is not the synchronization freshness gate.
- `MarkModification(ImageBase&)` sets `GpuModified` and assigns `image.modification_tick = ++modification_tick`.
- `modification_tick` is an Eden recency/version ordering signal, **not** a byte-content hash.
- `SynchronizeAliases()` selects an alias only when `destination.modification_tick < source.modification_tick`.
- destination tick is advanced to the maximum selected source tick before the copy loop.
- selected aliases are sorted by source tick.
- actual request is `CopyImage(image_id, aliased->id, aliased->copies)`.
- `AddImageAlias()` constructs copy regions from source/destination subresources, offsets and extents.

See `ALIAS_SYNC_REDUNDANCY_MAP.md`.

## Alias synchronization redundancy telemetry — BUILD VALIDATED

Transplant:

`tools/adreno_lab/transplant_dc95_alias_sync_redundancy.py`

New aggregate report marker:

`[X1-ALIAS-SYNC]`

The diagnostic measures only alias-copy requests emitted by the existing `SynchronizeAliases()` path. It does not add per-copy logging.

At the existing report interval, default 120 frames, it records:

- `copies`
- `uniquePairs`
- `sameFrame`
- `sameDraw`
- `consecutiveFrame`
- `sameSrcTick`
- `advancedSrcTick`
- `regressedSrcTick`
- `sameSignature`
- `sameStateSignature`
- `regions`
- `maxRegions`
- `tableOverflow`

The stable region signature hashes, in copy order:

- copy count
- source/destination base level
- source/destination base layer
- layer count
- source/destination x/y/z offsets
- width/height/depth extent

The source `modification_tick` is read immediately before the existing alias `CopyImage` request.

### Bounded tracker

- capacity: 4,096 entries
- probe limit: 32
- fixed `std::array`
- no unbounded growth
- state cleared/rotated at each report boundary

A non-zero `tableOverflow` means some pair-history classification was missed and must be considered when interpreting ratios.

## Instrumentation-only safety contract

The successful build does **not**:

- skip or deduplicate alias copies
- cache copy results
- batch `vkCmdCopyImage`
- suppress barriers
- suppress render-pass exit requests
- alter `modification_tick`
- force alias state up to date
- reorder Draw work
- change Draw/Dispatch A/B defaults

Gameplay optimization applied: **none**.

Copies skipped: **none**.

Barriers suppressed: **none**.

Render-pass requests suppressed: **none**.

## Existing telemetry retained for runtime cross-check

The build also retains:

- `other/texture/alias-copy`
- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/direct-vk-copy`
- `other/post-copy-barrier`
- Uniform / Vertex / Index / refresh counters

The new `[X1-ALIAS-SYNC] copies` count must be compared with the established direct-route scope order of magnitude on a matched gameplay route.

## Other confirmed/active performance axes

### Draw barriers — confirmed

`other/post-copy-barrier` owns the reason-level Draw barriers. It is not the dominant alias outside-RP owner.

### Persistent Uniform pressure — strong separate candidate

Previous matched windows showed roughly:

- 8,666,347 Uniform upload requests
- 3,516.7 MiB
- ~425 bytes/request
- ~12,037 requests/frame

Tiny Uniform traffic remains a separate normal ~20 FPS ceiling candidate.

### Severe dips — composite

The slowest windows add bulk staging upload, Vertex/Index copy spikes and texture refresh activity on top of persistent Uniform + alias-copy burdens.

Do not force these into one root cause.

## NEXT ACTION — runtime only

The alias-sync diagnostic has built successfully. The next step is **not another build**.

Run the artifact `Eden-dc95-X1-alias-sync-redundancy` with the same matched TOTK 1.4.2 setup and collect a gameplay log containing `[X1-ALIAS-SYNC]` plus the retained telemetry.

Use:

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- a comparable field route including normal ~20 FPS and slower sections when practical

Interpretation rules:

1. High `sameStateSignature`, especially with high `sameFrame` or `sameDraw`, supports a **separate future one-variable A/B** targeting only the proven redundant subset.
2. Mostly `advancedSrcTick` means repeated copies normally follow source-state changes; deduplication is not supported.
3. Mostly unique pairs with little repetition points toward alias-set churn / why many aliases become synchronization candidates.
4. Non-zero `tableOverflow` limits repeat-ratio interpretation.
5. Unchanged `modification_tick` is only unchanged Eden version state; it does not independently prove byte-for-byte identity.

Do not implement an alias-copy skip/dedupe optimization before this runtime evidence.

## Build authorization state

- current experiment: `exp/x1-alias-sync-redundancy`
- ARM64 attempts for this experiment: **1**
- attempt 1: **success**
- additional build authorization: **not granted**
- workflow: manual-only
- next required input: matched runtime log with `[X1-ALIAS-SYNC]`
