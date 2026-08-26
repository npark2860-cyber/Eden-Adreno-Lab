# X1 alias synchronization redundancy map

Updated: 2026-08-27 KST

Status: **instrumentation prepared / runtime not yet executed**

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

- `direct-route`: 100,021 scopes
- `direct-resolve-invalidate`: 100,021 scopes / outside 0
- `direct-vk-copy`: 100,021 scopes / outside 24,806
- `reinterpret-route`: 0
- `convert-route`: 0
- `direct-bpb-reinterpret`: 0
- whole-log attributed Draw outside-RP: 39,017
- direct-vk-copy share: 24,806 / 39,017 = **63.58%**

This experiment does not reopen route attribution.

## Exact dc95 alias semantics — source verified

### `AliasedImage`

Exact dc95 defines an alias record as:

- `ImageId id`
- `std::vector<ImageCopy> copies`

There is no per-alias dirty/up-to-date flag in `AliasedImage`.

`ImageFlagBits::Alias` indicates that the image has aliases and affects cache/GC state. `CheckAliasState()` clears that flag only when `aliased_images` becomes empty; it is not the synchronization freshness test.

### `modification_tick`

`TextureCache<P>::MarkModification(ImageBase&)`:

- sets `GpuModified`
- sets `image.modification_tick = ++modification_tick`

Other exact-dc95 maintenance paths can propagate an existing image tick to a newly joined/copied image, and `SynchronizeAliases()` propagates the most recent selected alias tick to the destination.

Therefore `modification_tick` is used here as an Eden recency/version ordering signal. It is **not** treated as a content hash or proof that two byte streams are equal.

### `SynchronizeAliases()` selection and copy order

For destination `image_id`, exact dc95:

1. reads the destination image's current `modification_tick`
2. examines each `AliasedImage`
3. selects an alias only when:
   `destination.modification_tick < source.modification_tick`
4. records the maximum selected source tick
5. updates the destination tick to that maximum
6. sorts selected aliases by source `modification_tick`
7. calls `CopyImage(image_id, aliased->id, aliased->copies)` for each selected alias, with scale handling around the same copy request where required

Thus the new telemetry is attached to the alias-copy request issued from this exact `SynchronizeAliases()` path, immediately before the existing copy call.

## Copy-region semantics

`AliasedImage::copies` is produced by `AddImageAlias()` and contains `ImageCopy` records with:

- source subresource: base level, base layer, layer count
- destination subresource: base level, base layer, layer count
- source x/y/z offset
- destination x/y/z offset
- width/height/depth extent

The diagnostic hashes exactly these fields, plus region count, in copy order. It does not invent a byte-volume formula for compressed/block formats.

## Prepared passive telemetry

Transplant:

`tools/adreno_lab/transplant_dc95_alias_sync_redundancy.py`

New report marker:

`[X1-ALIAS-SYNC]`

One aggregate line is emitted at the existing profiler report interval, default 120 frames. No per-copy log is emitted.

Fields:

- `copies`: total SynchronizeAliases alias-copy requests
- `uniquePairs`: unique `(dst ImageId, src ImageId)` pairs tracked in the interval
- `sameFrame`: repeated pair in the same texture-cache frame
- `sameDraw`: repeated pair in the same Draw work scope
- `consecutiveFrame`: repeated pair on consecutive texture-cache frames
- `sameSrcTick`: repeated pair with unchanged source `modification_tick`
- `advancedSrcTick`: repeated pair whose source tick advanced
- `regressedSrcTick`: diagnostic guard for a lower subsequently observed source tick
- `sameSignature`: repeated pair with identical copy-region signature
- `sameStateSignature`: repeated pair with both unchanged source tick and identical region signature
- `regions`: total ImageCopy regions represented by requests
- `maxRegions`: largest region count in one request
- `tableOverflow`: requests whose pair history could not be retained by the bounded tracker

## Bounded-state design

Pair history is fixed-size:

- capacity: 4,096 entries
- probe cap: 32
- no dynamic growth
- state rotated/cleared at each report boundary

This bounds diagnostic memory regardless of runtime duration.

`uniquePairs` and repeat classifications should be interpreted together with `tableOverflow`; a non-zero overflow means some pair-history classification was missed.

## Existing telemetry retained

The workflow retains the established instrumentation chain, including:

- `other/texture/alias-copy`
- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/direct-vk-copy`
- `other/post-copy-barrier`
- Uniform / Vertex / Index / refresh counters

A future matched runtime can therefore cross-check the new copy-request count against the known alias-route scope magnitude and outside-RP attribution.

## Instrumentation-only boundary

This experiment does not:

- skip or deduplicate copies
- cache copy results
- batch `vkCmdCopyImage`
- suppress barriers
- suppress `RequestOutsideRenderPassOperationContext()`
- modify `modification_tick`
- force alias state up to date
- move copies across Draw boundaries
- change Draw/Dispatch A/B defaults

The purpose is measurement only.

## Prepared workflow

Workflow:

`.github/workflows/build-dc95-x1-alias-sync-redundancy.yml`

Artifact name:

`Eden-dc95-X1-alias-sync-redundancy`

The workflow is manual-only (`workflow_dispatch`) and checks out the exact fixed Eden SHA.

Preflight includes:

- exact dc95 HEAD verification
- Python transplant syntax checks
- `git diff --check` on transplanted Eden source
- exact source-semantic markers
- required `[X1-ALIAS-SYNC]` and bounded-state markers
- retained alias direct-route/direct-vk-copy markers
- an alias-sync-only diff checked for forbidden state/optimization changes
- explicit no-scheduler-touch guard for the new transplant
- existing exact-dc95 scheduler leak guards

## Runtime decision rules

No runtime conclusion exists yet.

After one future authorized build and matched run:

- high `sameStateSignature`, especially with high `sameFrame` or `sameDraw`, is evidence supporting a separate one-variable redundant-copy A/B experiment
- mostly `advancedSrcTick` means source state normally changes before repeated copies, so dedupe is not supported by this measurement
- mostly unique pairs with little repeat means alias-set churn is the more likely next diagnostic target

Even a high `sameSrcTick` result remains a version-state result, not byte-for-byte content proof.

## Build authorization state

**No ARM64 build has been started for this experiment.**

Fresh explicit user authorization is required before exactly one build attempt. One authorization = one attempt.
