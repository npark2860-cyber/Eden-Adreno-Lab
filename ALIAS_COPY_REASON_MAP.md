# X1 alias-copy reason map

Updated: 2026-08-27 KST

## Runtime evidence

The successful texture-fill diagnostic used exact Eden `dc95cd09eea9749250fe31a3072684d341d19417`, TOTK 1.4.2, Adreno X1-85, driver 512.863.0, with Draw/Dispatch skip disabled.

Across the complete 1920-frame `eden_log(7).txt` sample, attributed Draw outside-RP totaled 54,175:

- `other/texture/alias-copy`: **35,017 (64.64%)**
- `other/post-copy-barrier`: 7,383
- `vertex`: 4,842
- `other/texture/refresh-standard`: 2,819
- `uniform`: 1,521
- `index`: 1,369
- `storage`: 1,048

The signal persists in steady gameplay. Across report windows 1080–1920:

- `other/texture/alias-copy`: **30,062 / 46,356 = 64.85%**
- `other/post-copy-barrier`: 6,586
- `vertex`: 4,597
- `other/texture/refresh-standard`: 1,843

Representative windows:

- frame 1200: alias-copy outside 4,149; refresh-standard outside 11 / 4.115 MiB upload
- frame 1560: alias-copy outside 3,747; refresh-standard outside 344 / 106.767 MiB upload
- frame 1920: alias-copy outside 3,756; refresh-standard outside 131 / 31.883 MiB upload

RT find/scale buckets had large scope counts but zero outside-RP, so they are not the current render-pass-break target.

## Exact dc95 routing

### Generic `TextureCache<P>::CopyImage`

`src/video_core/texture_cache/texture_cache.h`

1. same `SurfaceType` -> normally `runtime.CopyImage(dst, src, copies)`
2. different type + `runtime.ShouldReinterpret(dst, src)` -> `runtime.ReinterpretImage(...)`
3. otherwise -> image/view setup + `runtime.ConvertImage(...)`

### Important attribution hazard

Generic `TextureCache<P>::CopyImage` is **not alias-exclusive**. Exact dc95 also calls it while joining/rebuilding overlapping images, outside `SynchronizeAliases()`.

Therefore simply instrumenting the whole generic function would mix unrelated image-maintenance copies into the alias result.

The prepared profiler solves this by activating the new generic route buckets only when the current parent category is exactly the existing:

`OtherTextureAliasCopy` / `other/texture/alias-copy`

The conditional API is:

`PushBufferCategoryOverrideIf(expected, category)`

If the current category does not equal the expected alias parent, it returns false and changes nothing.

### Vulkan `TextureCacheRuntime::CopyImage`

`src/video_core/renderer_vulkan/vk_texture_cache.cpp`

The Vulkan direct route has a second decision layer:

1. optional `InvalidateResolveShadow(dst.Handle())`
2. if source/destination `BytesPerBlock` differ:
   - Windows linear-image guard may return
   - otherwise a full-image copy is sent through `ReinterpretImage(...)`
3. otherwise:
   - `scheduler.RequestOutsideRenderPassOperationContext()`
   - barriers + `vkCmdCopyImage`

The Vulkan child buckets are also gated on the generic `OtherTextureAliasDirectRoute` parent, preventing ordinary runtime image copies elsewhere from contaminating alias telemetry.

### Vulkan `ReinterpretImage`

Exact dc95 `ReinterpretImage`:

- can invalidate resolve shadow
- gets a temporary buffer
- calls `scheduler.RequestOutsideRenderPassOperationContext()`
- performs image-to-buffer / buffer-to-image transfer work with barriers

Thus reinterpretation is structurally capable of producing the persistent outside-RP signal, but `eden_log(7)` cannot yet distinguish it from normal direct `vkCmdCopyImage` work.

## Prepared buckets

Existing parent:

- `other/texture/alias-copy`

Generic routes:

- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/reinterpret-route`
- `other/texture/alias-copy/convert-route`

Vulkan direct-route internals:

- `other/texture/alias-copy/direct-resolve-invalidate`
- `other/texture/alias-copy/direct-bpb-reinterpret`
- `other/texture/alias-copy/direct-vk-copy`

Interpretation order:

1. `direct-vk-copy` dominant outside-RP -> ordinary Vulkan image copy is the churn center.
2. `direct-bpb-reinterpret` dominant -> same-type copies repeatedly fall back to temporary-buffer reinterpret due block-size mismatch.
3. `reinterpret-route` dominant -> generic cross-type reinterpret path is the center.
4. `convert-route` dominant -> format conversion/render-target conversion path is the center.
5. `direct-resolve-invalidate` non-trivial -> resolve-shadow invalidation itself contributes render-pass breaks.
6. parent `alias-copy` residual still large -> isolate remaining setup/prework instead of optimizing generically.

## Backend safety

The generic texture cache is instantiated for Vulkan and OpenGL. Vulkan receives the real conditional profiler bridge. OpenGL receives a no-op `BeginX1TextureSubcategoryIf` / `EndX1TextureSubcategory` bridge so the shared template remains compile-safe without changing OpenGL behavior.

## Instrumentation contract

- passive attribution only
- no copy skipped
- no barrier suppressed
- no render-pass request suppressed
- no guest work reordered
- Draw/Dispatch skip A/B remains OFF

## Runtime contract after successful build

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- same TOTK 1.4.2 field route / comparable window

Existing `analyze_x1_draw_other_reasons.py` accepts arbitrary `other/*` rows, so no new parser is required.
