# Eden Adreno Lab

Repository bootstrap for the Windows ARM64 / Qualcomm Adreno X1-85 Eden optimization lab.

## Fixed experimental baseline

- Upstream source: `eden-emulator/mirror`
- Exact known-good Eden SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control branch: `lab/dc95-arm64-baseline`
- Current completed diagnostic branch: `exp/x1-alias-copy-reasons`

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

## Next experiment

The next passive question is whether `SynchronizeAliases()` requests redundant direct image copies.

See:

- `CURRENT_HANDOFF.md`
- `ALIAS_COPY_REASON_MAP.md`
- `NEXT_ACTION_ALIAS_SYNC_REDUNDANCY.md`

## Build safety

No ARM64 GitHub Actions build may be started or re-run without fresh explicit user authorization.

**One authorization = one build attempt.**
