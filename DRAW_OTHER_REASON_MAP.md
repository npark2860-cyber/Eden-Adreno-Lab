# Draw `other` reason map — exact dc95

Status: pre-build source analysis / instrumentation prepared

Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch: `exp/x1-draw-other-reasons`

## 1. Scope

The existing BufferCategory profiler classifies Draw preparation as index / vertex / uniform / storage / texture-buffer / transform-feedback / indirect, with all work outside those scopes falling into `other`.

The latest runtime showed that `other` owns about 86% of Draw-side outside-render-pass endings and all currently attributed Draw barriers. The purpose of this experiment is to split that residual bucket without changing guest-visible behavior.

## 2. Exact Draw path

`RasterizerVulkan::PrepareDraw()` performs, in order:

1. `FlushWork()`
2. `gpu_memory->FlushCaching()`
3. graphics-pipeline lookup
4. `GraphicsPipeline::Configure(is_indexed)`
5. dynamic-state update
6. query segment notification
7. transform-feedback handling
8. query-counter enable/update
9. final Draw command recording

Inside `GraphicsPipeline::ConfigureImpl()` the important non-BufferCategory regions include:

- `texture_cache.SynchronizeDescriptors(false)`
- `texture_cache.FillImageViews(...)`
- direct transform-feedback outside-render-pass request
- `guest_descriptor_queue.Acquire(...)`
- `buffer_cache.runtime.PostCopyBarrier()` after BufferCache category scopes
- `texture_cache.UpdateRenderTargets(false)`
- `texture_cache.CheckFeedbackLoop(...)`
- final `ConfigureDraw(...)`

## 3. Strongest source-level candidate

### `other/post-copy-barrier`

When `buffer_cache.any_buffer_uploaded` is true, `GraphicsPipeline::ConfigureImpl()` calls `buffer_cache.runtime.PostCopyBarrier()` after the named BufferCache category scopes have ended.

Exact dc95 `BufferCacheRuntime::PostCopyBarrier()`:

- calls `scheduler.RequestOutsideRenderPassOperationContext()`
- records a transfer-write -> graphics/compute memory barrier

Therefore this one call is structurally capable of producing both symptoms that currently collapse into `other`:

- outside-RP endings
- barriers

This is the first reason bucket to test against runtime totals. It is a source-level candidate, not yet a proven performance cause.

## 4. Other reason buckets

The new passive instrumentation extends the existing BufferCategory enum after the original numeric categories, so existing category numbers remain unchanged.

Reason buckets:

- `other/texture-sync-descriptors`
- `other/texture-fill-image-views`
- `other/transform-feedback-break`
- `other/descriptor-acquire`
- `other/post-copy-barrier`
- `other/update-render-targets`
- `other/feedback-loop`
- `other/configure-draw`
- `other/flush-work`
- `other/flush-caching`
- `other/dynamic-states`
- `other/query-segment`
- `other/transform-feedback`
- `other/query-counter`
- `other/draw-command`

Residual `cat=other` remains intentionally available. Any significant residual after the next runtime means another caller still needs isolation.

## 5. Why TextureCache is split at top-level call boundaries

Exact dc95 TextureCache runtime contains multiple operations that can request an outside-render-pass context for image copies, reinterpretation, resolve/shadow work, feedback handling, and buffer-to-image uploads. Texture upload staging also uses `StagingBufferPool::Request(..., MemoryUsage::Upload, ...)`.

Rather than instrument every hot internal event, the experiment scopes the top-level Draw preparation calls. Existing upload/copy/outside/barrier telemetry will therefore aggregate under the top-level reason that caused the internal work.

## 6. Query/cache reason

The Vulkan query cache has conditional paths that request outside-render-pass operation contexts for query-pool reset/copy/resolve work. The ordinary Draw path usually only records query begin/end work, so query buckets are expected to be smaller, but they are separated to avoid leaving them mixed into residual `other`.

## 7. Instrumentation rule

This experiment is instrumentation-only.

It does not:

- skip Draws
- suppress uploads
- remove barriers
- alter render-pass policy
- change descriptor behavior
- change BufferCache dirty tracking

The new manual workflow applies, in order:

`dc95 -> full-flow -> Draw/Dispatch correlation -> A/B controls -> BufferCategory correlation -> Draw other reasons`

This explicitly fixes the reproducibility problem in the inherited manual workflow, which did not currently call the BufferCategory transplant.

## 8. Decision after runtime

Use the next matched gameplay log to rank reason buckets by:

1. outside-RP count
2. barrier count
3. staging upload
4. copy bytes
5. scheduler wait
6. correlation with the heavy 15-6 FPS windows versus normal ~20 FPS windows

Only after one reason dominates should a one-variable semantic A/B be prepared.

No ARM64 build has been started for this branch.
