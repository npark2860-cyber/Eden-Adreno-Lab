# Eden Adreno Lab

Repository bootstrap for the Windows ARM64 / Qualcomm Adreno X1-85 Eden optimization lab.

## Fixed experimental baseline

- Upstream source: `eden-emulator/mirror`
- Exact known-good Eden SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control branch: `lab/dc95-arm64-baseline`
- Completed diagnostic branch: `exp/x1-alias-copy-reasons`
- Current prepared diagnostic branch: `exp/x1-alias-sync-redundancy`

Do not silently move the experimental source baseline while comparing performance. Later Eden behavior may be studied separately, but dc95 experiments must remain source-comparable.

## Current resolved performance chain

Runtime diagnostics have progressively resolved the dominant Draw outside-render-pass path:

`Draw other`
-> `texture-fill-image-views`
-> `SynchronizeAliases / alias-copy`
-> generic direct `CopyImage`
-> Vulkan `TextureCacheRuntime::CopyImage`
-> `RequestOutsideRenderPassOperationContext`
-> `vkCmdCopyImage`

Latest matched runtime (`eden_log(8).txt`) attributed **24,806 / 39,017 = 63.58%** of whole-log Draw outside-RP to `other/texture/alias-copy/direct-vk-copy`.

Separate confirmed/active axes:

- `PostCopyBarrier` owns Draw barriers.
- tiny Uniform uploads remain a persistent normal-ceiling candidate.
- severe dips can add bulk staging upload, Vertex/Index copy spikes and texture refresh.

## Current experiment

The passive alias synchronization redundancy diagnostic is prepared on:

`exp/x1-alias-sync-redundancy`

Exact dc95 source inspection established that `SynchronizeAliases()` uses relative `modification_tick` ordering to choose newer alias sources; `AliasedImage` itself has no per-alias dirty/up-to-date flag.

Prepared telemetry measures repeated src/dst alias pairs, same-frame/same-Draw/consecutive-frame repetition, source tick relation and copy-region signatures using bounded state only.

See:

- `CURRENT_HANDOFF.md`
- `ALIAS_COPY_REASON_MAP.md`
- `ALIAS_SYNC_REDUNDANCY_MAP.md`
- `NEXT_ACTION_ALIAS_SYNC_REDUNDANCY.md`

## Build safety

No ARM64 GitHub Actions build may be started or re-run without fresh explicit user authorization.

**One authorization = one build attempt.**

Current alias-sync ARM64 attempts: **0**.
