# Draw `other` reason map — exact dc95

Updated: 2026-08-27 KST

Status: **runtime attribution complete / downstream chain resolved**

Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`

Original experiment branch: `exp/x1-draw-other-reasons`

## Scope

The original Draw profiler left non-buffer preparation work in a broad `other` bucket. This experiment split that residual without changing guest-visible behavior.

Reason buckets included texture descriptor/fill work, PostCopyBarrier, UpdateRenderTargets, feedback-loop handling, dynamic states, queries, descriptor acquire/push, flush paths and final draw command work.

## Exact Draw path

`RasterizerVulkan::PrepareDraw()` includes:

1. `FlushWork()`
2. `gpu_memory->FlushCaching()`
3. graphics pipeline lookup/configure
4. dynamic-state update
5. query segment notification
6. transform-feedback handling
7. query-counter handling
8. final Draw command

Important `GraphicsPipeline::ConfigureImpl()` work includes:

- `texture_cache.SynchronizeDescriptors(false)`
- `texture_cache.FillImageViews(...)`
- descriptor acquire/push
- `buffer_cache.runtime.PostCopyBarrier()` when a buffer upload occurred
- `texture_cache.UpdateRenderTargets(false)`
- `texture_cache.CheckFeedbackLoop(...)`
- final `ConfigureDraw(...)`

## Runtime result — first split

The Draw-other runtime established:

- **all reason-level Draw barriers -> `other/post-copy-barrier`**
- dominant outside-RP source -> `other/texture-fill-image-views`
- second outside-RP source -> `other/update-render-targets`

Across the analyzed 960–1680 windows:

- `other/texture-fill-image-views`: 16,570 outside-RP (~62.35% of reason outside)
- `other/update-render-targets`: 6,693 (~25.19%)
- `other/post-copy-barrier`: 3,311 (~12.46%)

`other/post-copy-barrier` owned **100% of reason-level Draw barriers**, but it was not the dominant outside-RP owner.

This invalidated the earlier source-only idea that PostCopyBarrier might explain both major symptoms by itself.

## Downstream texture result

The follow-up texture-fill experiment (`eden_log(7).txt`) moved the dominant texture parent one level deeper:

- `other/texture/alias-copy`: **35,017 / 54,175 = 64.64%** of whole-log attributed Draw outside-RP
- `other/texture/refresh-standard`: staging/upload-heavy but much smaller outside-RP owner
- RT find/scale paths: high scope counts but zero outside-RP in the sampled runtime

## Downstream alias result

The alias-copy experiment (`eden_log(8).txt`) then resolved the implementation route:

- `direct-route`: 100,021 scopes
- `direct-resolve-invalidate`: 100,021 scopes / outside 0
- **`direct-vk-copy`: 100,021 scopes / outside 24,806**
- `reinterpret-route`: 0
- `convert-route`: 0
- `direct-bpb-reinterpret`: 0

Whole-log attributed Draw outside-RP was 39,017, so `direct-vk-copy` alone owned **63.58%**.

The current resolved outside-RP chain is therefore:

`Draw Configure -> FillImageViews -> PrepareImage -> SynchronizeAliases -> CopyImage -> TextureCacheRuntime::CopyImage -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

## Separate barrier chain

Keep the barrier result separate:

`Draw Configure -> buffer upload occurred -> PostCopyBarrier -> transfer-write memory barrier`

PostCopyBarrier remains the confirmed Draw barrier owner. It is not the dominant alias outside-RP path.

## Current bottleneck model

Do not force one root cause:

- persistent tiny Uniform upload traffic -> normal ~20 FPS ceiling candidate
- persistent alias direct `vkCmdCopyImage` render-pass churn -> second steady burden
- severe dips -> those burdens plus bulk staging upload, Vertex/Index copy spikes and texture refresh

## What not to do next

- do not suppress `RequestOutsideRenderPassOperationContext()` blindly
- do not remove `vkCmdCopyImage` synchronization semantics
- do not re-test already eliminated reinterpret/convert/BPB fallback hypotheses
- do not treat PostCopyBarrier as the sole outside-RP cause

## Next diagnostic

Move upward from the now-known Vulkan copy implementation to the **copy-request decision in `SynchronizeAliases()`**.

Determine whether the same src/dst pair, same source modification state, or same copy regions are being synchronized repeatedly without new source content.

See `NEXT_ACTION_ALIAS_SYNC_REDUNDANCY.md`.

No ARM64 build may be started without fresh explicit user authorization. One permission = one attempt.
