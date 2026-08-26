# CURRENT HANDOFF — Eden Adreno X1 texture Fill/RT reasons

Updated: 2026-08-27 KST

## Fixed baseline

- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Previous experiment: `exp/x1-draw-other-reasons`
- Current experiment: `exp/x1-texture-fill-reasons`
- Current prepared HEAD before any ARM64 run: `5bd533bf32cd84501c8729d7d450db2c62baafce`
- No ARM64 build may be started or re-run without a fresh explicit user permission. One permission = one attempt.

## What the previous experiment proved

The `exp/x1-draw-other-reasons` ARM64 diagnostic build completed successfully in GitHub Actions:

- run: `33006509619`
- job: `98301532029`
- build head: `1625580c5ebecb782593b144f9d52c32a0fc8bb8`
- artifact: `Eden-dc95-X1-draw-other-reasons`
- artifact id: `9621708904`

The user then captured `eden_log(6).txt` with TOTK 1.4.2 on Qualcomm Adreno X1-85, driver 512.863.0. Draw/Dispatch skip A/B were both disabled.

Passive Draw reason telemetry split the old residual `other` bucket enough to establish two different owners:

### Barrier owner — CONFIRMED

`other/post-copy-barrier` owned all attributed Draw barriers in the sampled windows.

This matches exact dc95 source: `GraphicsPipeline::ConfigureImpl()` calls `buffer_cache.runtime.PostCopyBarrier()` after named BufferCache scopes, and `BufferCacheRuntime::PostCopyBarrier()` requests outside-render-pass context and records the transfer -> graphics/compute barrier.

### Outside-RP owner — CONFIRMED

The dominant Draw outside-render-pass reason was **not** PostCopyBarrier. Across the analyzed frames around 960–1680:

- `other/texture-fill-image-views`: 16,570 outside-RP (~62.35% of the reason-family outside count)
- `other/update-render-targets`: 6,693 (~25.19%)
- `other/post-copy-barrier`: 3,311 (~12.46%)

A heavy reporting window around frame 1680 reached 9,376 Draw outside-RP events, of which `other/texture-fill-image-views` alone contributed 6,590 (~70.3%).

A heavy frame-1200 window also showed approximately:

- staging upload: 976.193 MiB
- Draw upload: 853.165 MiB
- Draw copy: 250.113 MiB
- Draw outside-RP: 5,099
- Draw barriers: 3,843
- Vertex copy: 219.840 MiB
- `texture-fill-image-views`: 288.109 MiB upload / 1,926 outside
- `update-render-targets`: 24.397 MiB upload / 1,109 outside
- `post-copy-barrier`: 3,843 barriers / 293 outside

Therefore PostCopyBarrier is the Draw barrier owner, while FillImageViews / UpdateRenderTargets are the stronger texture-side outside-RP targets.

## Separate normal-ceiling axis remains open

Uniform uploads still dominate steady Draw upload volume. In the sampled 960–1680 range they were roughly 3,182 MiB (~80.7% of Draw upload), while texture-fill-image-views was roughly 590 MiB (~15%).

Current interpretation:

- normal ~20 FPS ceiling candidate: persistent tiny Uniform uploads
- severe dips: texture FillImageViews / UpdateRenderTargets outside-RP work plus Vertex-copy spikes
- Draw barrier attribution: PostCopyBarrier

Do not collapse these into a single cause.

## Why the current experiment exists

Exact dc95 source shows `FillImageViews()` itself is a thin loop. The real work is underneath it:

`FillImageViews -> VisitImageView -> PrepareImageView -> PrepareImage`

`VisitImageView()` can create a new cached image view:

`VisitImageView -> CreateImageView -> FindOrInsertImage -> InsertImage/JoinImages`

`PrepareImage()` can execute:

- `RefreshContents()`
- `SynchronizeAliases()`

`RefreshContents()` synchronous path performs:

`UploadStagingBuffer -> UploadImageContents -> Image::UploadMemory / AccelerateImageUpload`

`SynchronizeAliases()` may execute:

- `ScaleUp` / `ScaleDown`
- `CopyImage`
- runtime copy / reinterpret / conversion beneath `CopyImage`

`FillImageViews()` blacklist handling can also call `ScaleDown()`.

`UpdateRenderTargets(false)` shares the same `PrepareImageView()` path. When render targets are dirty it first calls `RescaleRenderTargets()`, which can execute:

- `FindColorBuffer(index)`
- `FindDepthBuffer()`
- `ScaleUp()` / `ScaleDown()`

Therefore the next passive experiment instruments these common internal texture-cache operations instead of treating FillImageViews and UpdateRenderTargets as unrelated problems.

## Prepared subreason instrumentation

New branch:

`exp/x1-texture-fill-reasons`

Prepared files:

- `tools/adreno_lab/transplant_dc95_texture_fill_reasons.py`
- `.github/workflows/build-dc95-x1-texture-fill-reasons.yml`
- `TEXTURE_FILL_REASON_MAP.md`

Commits:

- `102c37654e4a1586cedd09ea30b76f144922271e` — `profiler: split texture fill and RT reasons`
- `359f2be017572382589bc6d151d2565983ed7e52` — `ci: add manual texture fill reason workflow`
- `5bd533bf32cd84501c8729d7d450db2c62baafce` — `docs: map texture fill and RT subreasons`

The existing parent categories remain:

- `other/texture-fill-image-views`
- `other/update-render-targets`

New child categories temporarily override the current category only during concrete internal work, then restore the parent:

- `other/texture/create-view`
- `other/texture/refresh-standard`
- `other/texture/refresh-converted`
- `other/texture/refresh-accelerated`
- `other/texture/alias-copy`
- `other/texture/alias-scale`
- `other/texture/blacklist-scale`
- `other/texture/rt-find-color`
- `other/texture/rt-find-depth`
- `other/texture/rt-scale`

The parent row therefore becomes residual accounting for work not captured by a concrete child scope.

## Instrumentation mechanics

`transplant_dc95_texture_fill_reasons.py` adds a small override stack to the existing profiler:

- `PushBufferCategoryOverride(BufferCategory)`
- `PopBufferCategoryOverride()`

It bridges generic TextureCache through optional `TextureCacheParams` hooks:

- `BeginX1TextureSubcategory(u32)`
- `EndX1TextureSubcategory()`

Generic TextureCache calls them only through compile-time `if constexpr (requires {...})`, keeping non-Vulkan backends independent.

No Draw/Dispatch work is skipped, synchronization is not suppressed, and guest work is not reordered.

## Manual-only build workflow

Workflow:

`.github/workflows/build-dc95-x1-texture-fill-reasons.yml`

Expected artifact:

`Eden-dc95-X1-texture-fill-reasons`

The workflow is currently `workflow_dispatch` only. It contains pre-configure Python syntax checks, `git diff --check`, subreason grep checks, and the existing exact-dc95 scheduler leak guards.

No ARM64 run for this workflow has been started yet.

## Runtime contract after a successful build

Use the same passive settings:

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF

Use the same TOTK 1.4.2 field route / comparable gameplay window and upload the newest Eden log.

Existing `analyze_x1_draw_other_reasons.py` already accepts arbitrary `other/*` rows, so it can aggregate the new child categories without a separate analyzer.

## Interpretation order for the next runtime log

1. `refresh-standard / refresh-converted / refresh-accelerated`
   - dominant outside-RP + staging upload => image refresh/upload path is the FillImageViews cost center.
2. `alias-copy`
   - dominant outside/copy => alias synchronization and image copy/reinterpret path.
3. `alias-scale / blacklist-scale / rt-scale`
   - dominant outside => rescale/blit churn.
4. `create-view / rt-find-color / rt-find-depth`
   - dominant work => descriptor-driven image creation/find/join or dirty RT discovery.
5. Parent residual
   - if `texture-fill-image-views` / `update-render-targets` still retain large outside-RP counts, isolate only that residual portion next. Do not guess or optimize generically.

## NEXT ACTION

### Until fresh explicit build permission

Do not start GitHub Actions and do not build locally/remotely.

### On the next explicit build permission

Start exactly **one** ARM64 build attempt of:

`.github/workflows/build-dc95-x1-texture-fill-reasons.yml`

on:

`exp/x1-texture-fill-reasons`

If the connector still lacks direct workflow dispatch, use a one-shot push trigger restricted to a unique marker-file path, create exactly one marker commit, then restore the workflow to manual-only without touching that marker path. This avoids the previous workflow-file/concurrency cancellation problem.

If the build fails, diagnose/fix but do not re-run until another explicit permission is given.

## Current safety state

- Current experiment HEAD before build: `5bd533bf32cd84501c8729d7d450db2c62baafce`
- New workflow: manual-only
- New ARM64 run: not started
- Gameplay behavior change: none
- Optimization A/B selected: none
