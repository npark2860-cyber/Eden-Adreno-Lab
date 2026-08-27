# Eden Adreno Lab

Repository bootstrap for the Windows ARM64 / Qualcomm Adreno X1-85 Eden optimization lab.

## Fixed experimental baseline

- Upstream source: `eden-emulator/mirror`
- Exact known-good Eden SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control branch: `lab/dc95-arm64-baseline`
- Completed alias-route branch: `exp/x1-alias-copy-reasons`
- Completed alias-redundancy branch: `exp/x1-alias-sync-redundancy`
- Current prepared diagnostic branch: `exp/x1-uniform-stream-reuse`

Do not silently move the experimental source baseline while comparing performance. Later Eden behavior may be studied separately, but dc95 experiments must remain source-comparable.

## Resolved alias performance chain

Runtime diagnostics resolved the dominant Draw outside-render-pass alias path:

`Draw other`
-> `texture-fill-image-views`
-> `SynchronizeAliases / alias-copy`
-> generic direct `CopyImage`
-> Vulkan `TextureCacheRuntime::CopyImage`
-> `RequestOutsideRenderPassOperationContext`
-> `vkCmdCopyImage`

Alias-route runtime attributed **24,806 / 39,017 = 63.58%** of whole-log Draw outside-RP to `other/texture/alias-copy/direct-vk-copy`.

The follow-up alias-redundancy runtime (`eden_log(9).txt`) closed trivial copy dedupe:

- 194,396 alias-sync copies
- `sameSrcTick=0`
- `advancedSrcTick=190,823`
- `sameStateSignature=0`
- `tableOverflow=0`

Repeated pair/region requests therefore represent newer source recency state under exact dc95; do not skip them as unchanged duplicates.

## Current performance axes

- `PostCopyBarrier` owns Draw barriers.
- valid alias `vkCmdCopyImage` synchronization remains a recurring cost but trivial dedupe is rejected.
- tiny graphics Uniform uploads remain the strongest steady normal-ceiling candidate, roughly 10k–12k requests/frame in matched TOTK gameplay.
- severe dips can additionally include bulk staging upload, Vertex/Index copy spikes and texture refresh.

## Current experiment — Uniform stream/reuse

Prepared branch:

`exp/x1-uniform-stream-reuse`

Exact dc95 source facts motivating this measurement:

- Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- graphics Uniform bindings are visited with `dirty = ~0U` rather than a persistent binding dirty mask.
- classic `SynchronizeBuffer()` can produce a zero-upload clean hit or a real upload.
- the adaptive Vulkan fast path is not payload reuse: every visit requests mapped upload staging, inserts a descriptor and copies guest bytes.

New passive marker:

`[X1-UNIFORM-PATH]`

It measures fast mapped-stream vs classic cached path, cached clean vs real upload, alignment-vs-skip fast reason, and bounded repetition of exact `(stage,index,device_addr,size)` fast keys.

A repeated key does not assert identical payload bytes.

See:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY.md`
- `UNIFORM_STREAM_REUSE_MAP.md`
- `NEXT_ACTION_UNIFORM_STREAM_REUSE.md`

## Build safety

No ARM64 GitHub Actions build may be started or re-run without fresh explicit user authorization.

**One authorization = one build attempt.**

Current Uniform experiment ARM64 attempts: **0**.
