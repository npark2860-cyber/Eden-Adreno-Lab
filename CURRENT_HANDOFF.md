# CURRENT HANDOFF — Eden Adreno X1 alias CopyImage reasons

Updated: 2026-08-27 KST

## Fixed baseline

- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Previous experiment: `exp/x1-texture-fill-reasons`
- Current experiment: `exp/x1-alias-copy-reasons`
- No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.

## Previous build — SUCCESS

Texture Fill/RT diagnostic:

- workflow: `Build dc95 X1 Texture Fill Reasons`
- run: `33013428678`
- job: `98325342539`
- build head: `ce92e665baa277cc6a99c52dee35504832a1cf1b`
- result: success
- exact source: dc95

The user ran this build with TOTK 1.4.2 on Qualcomm Adreno X1-85, driver 512.863.0 and uploaded `eden_log(7).txt`. Draw/Dispatch skip were both false.

## What `eden_log(7).txt` proved

Across the complete 1920-frame sample, attributed Draw outside-RP totaled 54,175:

- `other/texture/alias-copy`: **35,017 = 64.64%**
- `other/post-copy-barrier`: 7,383
- `vertex`: 4,842
- `other/texture/refresh-standard`: 2,819
- `uniform`: 1,521
- `index`: 1,369
- `storage`: 1,048

This is persistent in steady gameplay. Across report windows 1080–1920:

- alias-copy: **30,062 / 46,356 = 64.85%**
- post-copy-barrier: 6,586
- vertex: 4,597
- refresh-standard: 1,843

Representative rows:

- frame 1200: alias-copy outside 4,149; refresh-standard outside 11 / 4.115 MiB upload
- frame 1560: alias-copy outside 3,747; refresh-standard outside 344 / 106.767 MiB upload
- frame 1920: alias-copy outside 3,756; refresh-standard outside 131 / 31.883 MiB upload

RT find/color/depth/scale scopes were large but had zero outside-RP, so they are not the current render-pass-break target.

Separate axes remain:

- persistent tiny Uniform uploads remain a normal ~20 FPS ceiling candidate
- PostCopyBarrier remains the Draw barrier owner
- severe dips can combine alias-copy, texture refresh, and Vertex/Index bursts

Do not collapse these into one cause.

## Exact source map

### Generic route

`TextureCache<P>::CopyImage` in `src/video_core/texture_cache/texture_cache.h` routes:

1. same SurfaceType -> `runtime.CopyImage`
2. different type + `ShouldReinterpret` -> `runtime.ReinterpretImage`
3. otherwise -> `runtime.ConvertImage`

### Attribution hazard — CONFIRMED

Generic `CopyImage()` is not exclusive to `SynchronizeAliases()`. Exact dc95 also calls it from image joining/overlap maintenance.

Therefore new route instrumentation is **parent-gated**: it activates only when the current BufferCategory is the existing `OtherTextureAliasCopy` parent. Calls from JoinImages or unrelated texture maintenance remain outside the new alias child buckets.

Profiler API added:

`PushBufferCategoryOverrideIf(expected, category)`

### Vulkan direct route

Exact `TextureCacheRuntime::CopyImage` additionally does:

1. `InvalidateResolveShadow`
2. if BytesPerBlock differs -> Windows linear guard or `ReinterpretImage` fallback
3. otherwise -> `RequestOutsideRenderPassOperationContext` + barriers + `vkCmdCopyImage`

`ReinterpretImage` uses a temporary buffer and explicitly requests outside-RP context.

## Prepared alias child buckets

Generic routes:

- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/reinterpret-route`
- `other/texture/alias-copy/convert-route`

Direct-route internals:

- `other/texture/alias-copy/direct-resolve-invalidate`
- `other/texture/alias-copy/direct-bpb-reinterpret`
- `other/texture/alias-copy/direct-vk-copy`

The existing `other/texture/alias-copy` parent remains residual accounting.

## Prepared files

Branch:

`exp/x1-alias-copy-reasons`

Files:

- `tools/adreno_lab/transplant_dc95_alias_copy_reasons.py`
- `.github/workflows/build-dc95-x1-alias-copy-reasons.yml`
- `ALIAS_COPY_REASON_MAP.md`
- `CURRENT_HANDOFF.md`

Important commits in preparation sequence:

- `68c8dfe228ee3b7be7e00fc768210009d92b6e0e` — initial alias route split
- `4cf02e6d1fc119c889396db5507aa165f78f3ff3` — gate child routes to alias parent
- `b29f504aff6570803400af637b3ac190af0fccd0` — keep shared generic TextureCache backend-safe with OpenGL no-op bridge
- `d6af758e664b2fe67562633db9006a7b7c79b3fb` — update workflow preflight for parent-gated hooks
- `b14ff40d25b072d6c5ee2eff8dd281484b23fb3d` — document parent-gated attribution

## Backend safety

Shared generic TextureCache is instantiated for Vulkan and OpenGL.

- Vulkan TextureCacheParams exposes real conditional profiler hooks.
- OpenGL TextureCacheParams gets no-op conditional hooks returning false.

This keeps generic template code compile-safe while ensuring only Vulkan X1 diagnostics produce new category data.

## Workflow

`.github/workflows/build-dc95-x1-alias-copy-reasons.yml`

Expected artifact:

`Eden-dc95-X1-alias-copy-reasons`

The workflow is intended to stay `workflow_dispatch` only until an explicit build authorization.

Pre-configure verification checks:

- Python transplant syntax
- `git diff --check`
- all six alias bucket names
- conditional profiler API
- Vulkan + OpenGL conditional bridges
- exact generic parent-gated route markers `29 -> 35/36/37`
- Vulkan direct child enum uses
- existing exact-dc95 scheduler leak guards

## Runtime contract after successful build

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- same TOTK 1.4.2 field route / comparable gameplay window

Interpretation priority:

1. direct-vk-copy
2. direct-bpb-reinterpret
3. reinterpret-route
4. convert-route
5. direct-resolve-invalidate
6. parent alias-copy residual

## NEXT ACTION

Do not start GitHub Actions until the user gives a fresh explicit build permission.

On the next explicit build permission, start exactly one ARM64 build attempt of:

`.github/workflows/build-dc95-x1-alias-copy-reasons.yml`

on:

`exp/x1-alias-copy-reasons`

If direct workflow dispatch is unavailable, use a one-shot push trigger restricted to a unique marker file path, create exactly one marker commit, then immediately restore the workflow to manual-only without modifying that marker path.

If the build fails, diagnose/fix but do not re-run until another fresh explicit permission.

## Current safety state

- Gameplay behavior changes: none
- Copies skipped: none
- Barriers suppressed: none
- Render-pass requests suppressed: none
- Optimization A/B selected: none
- Alias workflow build attempts: 0
