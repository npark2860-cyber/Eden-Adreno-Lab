# X1 Texture Fill / Render-Target Reason Map

Updated: 2026-08-27 KST

Status: **runtime attribution complete / superseded by alias-copy analysis**

Branch used for this stage: `exp/x1-texture-fill-reasons`

Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`

## Starting evidence

The preceding Draw-other experiment established:

- Draw barrier owner: `other/post-copy-barrier`
- dominant Draw outside-RP parent: `other/texture-fill-image-views`
- secondary outside-RP parent: `other/update-render-targets`

The texture-fill experiment therefore split the common texture-cache work beneath `FillImageViews()` / `UpdateRenderTargets()`.

## Exact source map

`FillImageViews -> VisitImageView -> PrepareImageView -> PrepareImage`

`PrepareImage()` can reach:

- `RefreshContents(image, image_id)`
- `SynchronizeAliases(image_id)`

`RefreshContents()` performs the synchronous upload path.

`SynchronizeAliases()` can perform scale operations and `CopyImage`.

`UpdateRenderTargets(false)` shares `PrepareImageView()` and can additionally perform render-target find/rescale work.

## Instrumented subreasons

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

## `eden_log(7).txt` result — CONFIRMED

Across the complete 1920-frame sample, attributed Draw outside-RP totaled **54,175**.

Major rows:

- `other/texture/alias-copy`: **35,017 = 64.64%**
- `other/post-copy-barrier`: 7,383
- `vertex`: 4,842
- `other/texture/refresh-standard`: 2,819
- `uniform`: 1,521
- `index`: 1,369
- `storage`: 1,048

Across report windows 1080–1920, alias-copy remained **30,062 / 46,356 = 64.85%** of attributed Draw outside-RP.

Representative windows:

- frame 1200: alias-copy outside 4,149; refresh-standard outside 11 / 4.115 MiB upload
- frame 1560: alias-copy outside 3,747; refresh-standard outside 344 / 106.767 MiB upload
- frame 1920: alias-copy outside 3,756; refresh-standard outside 131 / 31.883 MiB upload

## What this stage proved

1. **`SynchronizeAliases -> CopyImage` is the dominant texture-side outside-RP path.**
2. `refresh-standard` is important for staging/upload volume but is not the dominant render-pass-break owner.
3. RT find/color/depth/scale paths can have very high scope counts while producing zero outside-RP in the sampled runtime.
4. create-view / converted refresh / accelerated refresh / alias-scale / blacklist-scale were not the main outside-RP explanation.

This closed the question of which texture-cache operation owns most of the `FillImageViews` churn and led directly to `ALIAS_COPY_REASON_MAP.md`.

## Follow-up result

The next alias-copy experiment (`eden_log(8).txt`) further proved that the alias copies in this runtime all take the direct Vulkan copy route, and that `other/texture/alias-copy/direct-vk-copy` owns **24,806 / 39,017 = 63.58%** of whole-log attributed Draw outside-RP.

Thus the current chain is:

`FillImageViews / PrepareImage -> SynchronizeAliases -> CopyImage -> direct Vulkan vkCmdCopyImage`

## Current interpretation

Keep three performance axes separate:

- tiny Uniform uploads: persistent normal-ceiling candidate
- alias direct `vkCmdCopyImage` render-pass churn: persistent steady burden
- bulk texture refresh + Vertex/Index copies: severe-dip contributors

`PostCopyBarrier` remains the Draw barrier owner but is not the dominant alias outside-RP source.

## Next action

Do not perturb render-pass requirements yet. The next passive experiment should test whether `SynchronizeAliases()` repeatedly copies unchanged/repeated src-dst alias pairs.

See `NEXT_ACTION_ALIAS_SYNC_REDUNDANCY.md`.

No ARM64 build may be started without fresh explicit user authorization. One permission = one attempt.
