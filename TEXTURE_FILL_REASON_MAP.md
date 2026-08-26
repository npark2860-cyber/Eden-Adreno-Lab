# X1 Texture Fill / Render-Target Reason Map

## Status

Branch: `exp/x1-texture-fill-reasons`

Exact Eden source under test: `dc95cd09eea9749250fe31a3072684d341d19417`

This experiment is instrumentation-only. It does not skip Draw/Dispatch work, reorder guest work, or alter Vulkan synchronization semantics.

## Evidence from `eden_log(6).txt`

The previous `exp/x1-draw-other-reasons` runtime run split the old Draw `other` bucket enough to establish two separate facts:

1. Draw barriers are attributed to `other/post-copy-barrier`.
2. Draw outside-render-pass events are dominated by texture work, especially `other/texture-fill-image-views`, with `other/update-render-targets` second.

Across the sampled steady/heavy reporting windows used in the analysis, `other/texture-fill-image-views` contributed the largest share of texture-side outside-RP events. In the heaviest observed reporting window around frame 1680 it reached 6,590 outside-RP events while `other/post-copy-barrier` remained the barrier owner rather than the dominant outside-RP owner.

Therefore the next passive question is not whether `FillImageViews()` is involved; it is which internal texture-cache operation performed during `FillImageViews()` / `UpdateRenderTargets()` causes the RP breaks and staging traffic.

## Exact dc95 call map

### FillImageViews

`TextureCache<P>::FillImageViews()` is a thin loop around:

`FillImageViews -> VisitImageView -> PrepareImageView -> PrepareImage`

`VisitImageView()` can also create a new cached image view:

`VisitImageView -> CreateImageView -> FindOrInsertImage -> InsertImage/JoinImages`

`PrepareImage()` then performs the main existing-content work:

- `RefreshContents(image, image_id)` when the image is CPU-modified.
- `SynchronizeAliases(image_id)` when aliases exist.

`RefreshContents()` performs the synchronous upload path as:

`UploadStagingBuffer -> UploadImageContents -> Image::UploadMemory / AccelerateImageUpload`

`SynchronizeAliases()` may perform:

- `ScaleUp` / `ScaleDown`
- `CopyImage`
- runtime copy / reinterpret / conversion paths beneath `CopyImage`

The `FillImageViews()` blacklist path can also call `ScaleDown()` directly.

### UpdateRenderTargets

`TextureCache<P>::UpdateRenderTargets(false)` calls `PrepareImageView()` on active color/depth render targets. When render targets are dirty it first calls `RescaleRenderTargets()`.

`RescaleRenderTargets()` can perform:

- `FindColorBuffer(index)`
- `FindDepthBuffer()`
- `ScaleUp()` / `ScaleDown()`

After that, `UpdateRenderTargets()` again reaches the same `PrepareImageView -> PrepareImage -> RefreshContents / SynchronizeAliases` path used by FillImageViews.

This shared path is why the new experiment instruments common texture-cache operations rather than treating FillImageViews and UpdateRenderTargets as unrelated problems.

## New passive subreason buckets

The existing parent buckets remain active:

- `other/texture-fill-image-views`
- `other/update-render-targets`

The new experiment temporarily overrides the current category only while concrete internal work is executing, then restores the parent category. New rows are:

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

Parent rows therefore become residual accounting: events remaining on `texture-fill-image-views` or `update-render-targets` were not captured by one of the concrete internal scopes above.

## Interpretation order

1. **refresh-standard / converted / accelerated**
   - If these own most outside-RP and staging upload, the dominant problem is image refresh/upload rather than descriptor lookup itself.
2. **alias-copy**
   - Large outside/copy traffic points to alias synchronization and image copy/reinterpret paths.
3. **alias-scale / blacklist-scale / rt-scale**
   - Large outside counts here point to resolution-scale blits and rescale churn.
4. **create-view / rt-find-color / rt-find-depth**
   - Large counts here point to image creation/find/join work triggered by new descriptors or dirty RT discovery.
5. **parent residual**
   - If substantial outside-RP remains on the parent bucket, add one more scope only around the unclassified portion; do not perturb behavior yet.

## Build workflow

Manual-only workflow:

`.github/workflows/build-dc95-x1-texture-fill-reasons.yml`

Expected artifact:

`Eden-dc95-X1-texture-fill-reasons`

Runtime settings remain passive/default-safe:

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF

No ARM64 run should be started without a fresh explicit authorization.
