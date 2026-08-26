# X1 alias-copy reason map

Updated: 2026-08-27 KST

## Why this experiment exists

The previous passive texture-fill build (`exp/x1-texture-fill-reasons`) was run successfully on exact Eden `dc95cd09eea9749250fe31a3072684d341d19417` with TOTK 1.4.2 on Adreno X1-85 / driver 512.863.0.

Across the complete 1920-frame `eden_log(7).txt` sample, Draw outside-render-pass attribution was:

- `other/texture/alias-copy`: **35,017** outside-RP events (**64.64%** of all attributed Draw outside-RP events)
- `other/post-copy-barrier`: 7,383
- `vertex`: 4,842
- `other/texture/refresh-standard`: 2,819
- `uniform`: 1,521
- `index`: 1,369
- `storage`: 1,048

The total attributed Draw outside-RP count in that sample was 54,175.

The alias-copy signal is persistent, not a one-time loading effect. Restricting the same log to report windows 1080 through 1920 gives:

- `other/texture/alias-copy`: **30,062 / 46,356 = 64.85%** of attributed Draw outside-RP
- `other/post-copy-barrier`: 6,586
- `vertex`: 4,597
- `other/texture/refresh-standard`: 1,843

Representative windows:

- frame 1200: alias-copy outside 4,149; refresh-standard outside 11 / 4.115 MiB upload
- frame 1560: alias-copy outside 3,747; refresh-standard outside 344 / 106.767 MiB upload
- frame 1920: alias-copy outside 3,756; refresh-standard outside 131 / 31.883 MiB upload

The RT discovery/scale buckets had very high scope counts but zero outside-RP in these windows, so they are not the current render-pass-break target.

## Exact dc95 source routing

### Generic TextureCache::CopyImage

`src/video_core/texture_cache/texture_cache.h`

The alias synchronization path ultimately calls `TextureCache<P>::CopyImage(dst_id, src_id, copies)`. Exact dc95 then routes by format type:

1. **same SurfaceType**
   - normally `runtime.CopyImage(dst, src, copies)`
   - Vulkan has `HAS_EMULATED_COPIES == false`, so this is the normal Vulkan direct route
2. **different SurfaceType + runtime.ShouldReinterpret(dst, src)**
   - `runtime.ReinterpretImage(dst, src, copies)`
3. **otherwise**
   - creates render-target/image views and calls `runtime.ConvertImage(...)` for each copy

### Vulkan TextureCacheRuntime::CopyImage

`src/video_core/renderer_vulkan/vk_texture_cache.cpp`

The Vulkan direct route has a second decision layer:

1. `InvalidateResolveShadow(dst.Handle())` when `ENABLE_MSAA_RESOLVE_CONSUME`
2. if source/destination `BytesPerBlock` differ:
   - Windows linear-image guard can return early
   - otherwise construct a full-image copy and call `ReinterpretImage(...)`
3. otherwise:
   - `scheduler.RequestOutsideRenderPassOperationContext()`
   - record barriers and `vkCmdCopyImage`

This means the generic `direct` route can still become a reinterpret operation inside the Vulkan runtime.

### Vulkan TextureCacheRuntime::ReinterpretImage

Exact dc95 `ReinterpretImage`:

- optionally invalidates the resolve shadow
- allocates/uses a temporary buffer
- calls `scheduler.RequestOutsideRenderPassOperationContext()`
- records image-to-buffer and buffer-to-image transfer work with barriers

Therefore reinterpretation is structurally capable of explaining the persistent alias-copy outside-RP signal, but the current log cannot distinguish it from ordinary direct image copies.

## Prepared child buckets

This experiment keeps the existing parent:

- `other/texture/alias-copy`

and adds the following nested overrides:

### Generic route

- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/reinterpret-route`
- `other/texture/alias-copy/convert-route`

### Vulkan direct-route internals

- `other/texture/alias-copy/direct-resolve-invalidate`
- `other/texture/alias-copy/direct-bpb-reinterpret`
- `other/texture/alias-copy/direct-vk-copy`

Interpretation:

- `direct-vk-copy` dominant outside-RP -> ordinary Vulkan image copies are the render-pass churn center
- `direct-bpb-reinterpret` dominant -> same-SurfaceType copies are repeatedly falling back to temporary-buffer reinterpret because block sizes differ
- `reinterpret-route` dominant -> generic cross-SurfaceType reinterpret path is the main source
- `convert-route` dominant -> format conversion/render-target conversion path is the main source
- `direct-resolve-invalidate` non-trivial -> resolve-shadow invalidation itself is breaking render passes
- parent `alias-copy` residual still large -> isolate uncaptured setup/prework rather than optimizing blindly

## Instrumentation rules

- passive attribution only
- no copies skipped
- no barriers suppressed
- no render-pass requests suppressed
- no guest work reordered
- existing parent scopes remain active and child scopes only temporarily override BufferCategory
- Draw/Dispatch skip A/B remains OFF for runtime collection

## Runtime contract after a successful build

Use the same settings and route as the previous log:

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- TOTK 1.4.2 comparable field route

Existing `analyze_x1_draw_other_reasons.py` accepts arbitrary `other/*` category rows, so no new parser is required.
