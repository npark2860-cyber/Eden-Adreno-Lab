# X1 alias synchronization redundancy map

Updated: 2026-08-27 KST

Status: **ARM64 diagnostic build succeeded / runtime not yet captured**

Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch: `exp/x1-alias-sync-redundancy`

## Starting proven path

The preceding alias-route experiment established the dominant Draw outside-render-pass path:

`Draw Configure`
-> `FillImageViews`
-> `PrepareImage`
-> `SynchronizeAliases`
-> `CopyImage`
-> generic direct route
-> `TextureCacheRuntime::CopyImage`
-> `RequestOutsideRenderPassOperationContext`
-> `vkCmdCopyImage`

Matched runtime (`eden_log(8).txt`):

- direct-route: 100,021 scopes
- direct-resolve-invalidate: 100,021 scopes / outside 0
- direct-vk-copy: 100,021 scopes / outside 24,806
- reinterpret-route: 0
- convert-route: 0
- direct-bpb-reinterpret: 0
- whole-log attributed Draw outside-RP: 39,017
- direct-vk-copy share: **63.58%**

This experiment does not reopen route attribution.

## Exact dc95 alias semantics — source verified

- `AliasedImage` stores alias `ImageId` plus `std::vector<ImageCopy>`; no per-alias dirty/up-to-date flag exists.
- `ImageFlagBits::Alias` is not the synchronization freshness test.
- `MarkModification()` sets `GpuModified` and advances `image.modification_tick` from the cache-global counter.
- `modification_tick` is an Eden recency/version signal, not a content hash.
- `SynchronizeAliases()` selects a source only when `destination.modification_tick < source.modification_tick`.
- destination tick is advanced to the maximum selected source tick before copies execute.
- selected aliases are sorted by source tick.
- actual request: `CopyImage(image_id, aliased->id, aliased->copies)`.
- `AddImageAlias()` builds regions from source/destination subresources, offsets and extents.

## Diagnostic instrumentation

Transplant:

`tools/adreno_lab/transplant_dc95_alias_sync_redundancy.py`

Aggregate marker:

`[X1-ALIAS-SYNC]`

One aggregate line is emitted at the existing profiler report interval, default 120 frames. No per-copy log is emitted.

Fields:

- `copies`: total SynchronizeAliases alias-copy requests
- `uniquePairs`: unique `(dst ImageId, src ImageId)` pairs tracked in interval
- `sameFrame`: repeated pair in same texture-cache frame
- `sameDraw`: repeated pair in same Draw work scope
- `consecutiveFrame`: repeated pair on consecutive frames
- `sameSrcTick`: repeated pair with unchanged source `modification_tick`
- `advancedSrcTick`: repeated pair whose source tick advanced
- `regressedSrcTick`: lower subsequently observed source tick guard
- `sameSignature`: repeated pair with identical copy-region signature
- `sameStateSignature`: same pair + same source tick + identical region signature
- `regions`: total `ImageCopy` regions represented
- `maxRegions`: largest region count in one request
- `tableOverflow`: requests whose pair history could not be retained

Region signature covers copy count and exact source/destination subresource, offset and extent fields in copy order.

## Bounded-state design

- fixed capacity: 4,096 entries
- probe cap: 32
- fixed array; no dynamic growth
- state cleared/rotated at each report boundary

Non-zero `tableOverflow` means some repeat history could not be classified.

## Successful build

Exactly one authorized ARM64 attempt was executed:

- run: `33024690895`
- job: `98363162523`
- attempt: `1`
- build head: `804f394c5db280f842a01113e6ca92f7ad57d219`
- result: **success**
- exact dc95 preflight: **success**
- instrumentation verification: **success**
- configure/build/package/upload: **success**
- artifact: `Eden-dc95-X1-alias-sync-redundancy`
- artifact id: `9628554127`
- size: `31,300,012` bytes
- SHA-256: `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

The temporary one-shot push trigger was removed after launch. Workflow is back to `workflow_dispatch` only and no second run was created.

## Existing telemetry retained

- `other/texture/alias-copy`
- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/direct-vk-copy`
- `other/post-copy-barrier`
- Uniform / Vertex / Index / refresh counters

## Instrumentation-only boundary

This build does not:

- skip/deduplicate/cache copies
- batch `vkCmdCopyImage`
- suppress barriers
- suppress `RequestOutsideRenderPassOperationContext()`
- modify `modification_tick`
- force alias state up to date
- move copies across Draw boundaries
- change Draw/Dispatch A/B defaults

## Runtime decision rules

Runtime conclusion is still pending.

After a matched run:

- high `sameStateSignature`, especially high `sameFrame` or `sameDraw`, supports a separate one-variable redundant-copy A/B experiment
- mostly `advancedSrcTick` means source version changes normally justify repeated copies; dedupe is not supported
- mostly unique pairs with little repetition points toward alias-set churn as the next diagnostic target
- non-zero `tableOverflow` limits repeat-ratio interpretation

Unchanged `modification_tick` remains version-state evidence, not byte-for-byte equality proof.

## Next action

Run the successful artifact on the matched TOTK 1.4.2 route and provide the log containing `[X1-ALIAS-SYNC]` plus retained telemetry.

No additional build is authorized. Any further ARM64 attempt requires fresh explicit user permission.
