# dc95 QCOM / Windows ARM64 provenance

This file records upstream work already present in the known-good `dc95cd09ee` baseline. These are not new Lab optimization proposals.

## 1. QCOM stock-driver capability and synchronization path — #3334

Commit: `1fbace438c375ca1e33f3cb09d7d85249cb51293`

Relevant source changes:

- `vk_buffer_cache.cpp`: UINT8 index conversion is enabled only when the required 8/16-bit storage features are actually supported; QCOM gets a null-buffer fallback instead of issuing an unsupported compute path.
- `vulkan_device.cpp`: storage 8/16-bit capabilities are moved away from unconditional mandatory assumptions and are feature-gated.
- `vulkan_device.cpp`: stock QCOM is no longer blanket-disabled from timeline semaphores; the blanket disable remains for Turnip.
- removes old QCOM forced BGR565 emulation and old QCOM parallel-compilation version special case.

The upstream commit explicitly reports improved GPU/CPU synchronization, more stable shader compilation and about 15% performance versus the previous builds. Treat the percentage as upstream test reporting, not as a guaranteed X1-85 result.

Windows ARM64 relevance: **high**. The capability path is keyed by `VK_DRIVER_ID_QUALCOMM_PROPRIETARY`, not Android-only code.

## 2. ARM Windows / stock-QCOM query and barrier regression repair — #3953

Commit: `3d19743d95f973ec0c322a0e8703387513ee0c66`

The upstream commit explicitly identifies an ARM Windows + QCOM stock-driver blitter/query race.

Relevant source changes include:

- multiple Vulkan barriers changed from `VK_PIPELINE_STAGE_ALL_COMMANDS_BIT` to narrower graphics/compute/transfer stage masks;
- renderer and presentation `WaitIdle` paths no longer wrap `WaitIdle` in `scheduler.submit_mutex`;
- query/reset/presync behavior adjusted to eliminate the ARM Windows / QCOM race described by the commit;
- several copy/download/compute paths stop synchronizing against all commands when a narrower dependency is sufficient.

Windows ARM64 relevance: **very high**. This is directly named by upstream as an ARM Windows stock-QCOM fix and it targets synchronization pressure.

## 3. QCOM narrow-feature safety + vertex binding reduction — #4189

Commit: `8225151a4469a13ac602215dbeb2ce9a3702f38b`

Relevant source changes:

- SPIR-V U8/U16 constant-buffer paths now require the actual corresponding uniform/storage feature bits before emitting the narrow access path;
- fixes bad compute-pipeline generation on QCOM when those features are missing;
- upstream reports reducing redundant `BindVertexBuffers2EXT` binding on new ticks/frames, specifically noting vertex-heavy BOTW/TOTK grass as a performance case;
- begins a safer Synchronization2 path.

Windows ARM64 relevance: **high** for stock-QCOM capability handling and vertex-heavy titles.

## 4. Render-pass / MSAA / tiler bandwidth work — #4212

Commit: `eb9280dedfb5e49e17a0bb586c2be87c4b769625`

Relevant source changes:

- removes repeated MSAA image-copy work from the common path;
- restructures render-pass/framebuffer attachment load/store handling and uses `DONT_CARE` where data does not need preservation;
- reduces unnecessary loads/clears and pressure on SYSMEM/GMEM-style paths;
- refines QCOM descriptor-indexing and narrow-feature handling;
- makes SPIR-V non-uniform descriptor capabilities more precisely conditional on actual use/support.

Windows ARM64 relevance: **high** for a tile-based Adreno GPU even though parts of the original motivation also cover Android and other bandwidth-limited GPUs.

## 5. Descriptor-buffer path targeting QCOM descriptor overhead — #4251

Commit: `49a0ca6d5d9929391e0633163ebbfec564d27cc1`

Relevant source changes:

- introduces `VK_EXT_descriptor_buffer` + device-buffer-address path alongside push descriptors/descriptor sets;
- descriptor ring is chunked using device limits; the commit explicitly calls out QCOM's small reported sampler range;
- descriptor-buffer chunk binding is re-emitted only when the chunk changes;
- repeated descriptor payload can reuse its previous allocation instead of rewriting it;
- upstream explicitly describes this as improving the slow push-descriptor implementation on QCOM A7xx and older and reducing pipeline compilation latency.

Windows ARM64 relevance: **high if the X1-85 stock driver exposes the required descriptor-buffer/device-address capabilities**. Runtime capability logs must confirm that before assigning benefit.

## What the current profiler measures

The dc95 profiler currently records:

- Finish wait time
- worker wait time
- render-pass begin/end/reuse
- post-render-pass image-barrier count
- deferred clears
- descriptor-buffer binds
- queue submissions
- graphics/compute pipeline compilation instrumentation already present in the P0 profiler

## Important gaps for the next instrumentation pass

Do not add these until the clean/profiler dc95 baseline is proven equivalent.

After baseline validation, add counters for:

1. selected synchronization mode: timeline semaphore vs fallback;
2. pipeline barriers grouped by source/destination stage class;
3. `BindVertexBuffers2EXT` calls per frame;
4. descriptor path selected per pipeline: descriptor buffer / push descriptor / descriptor set;
5. descriptor payload reuse vs new allocation;
6. MSAA resolve/copy fallback counts;
7. query reset/presync path counts.

These counters map directly to the upstream changes above and will tell us which existing Eden optimization is actually active on Snapdragon X1 Windows ARM64.

## Working hypothesis order

Until measured, use this order only as an investigation priority, not as a conclusion:

1. build/codegen difference: official MSYS2 CLANGARM64 and PGO;
2. QCOM synchronization path: timeline semaphore + #3953 barrier/query fixes;
3. descriptor-buffer path from #4251;
4. render-pass/load-store/MSAA reductions from #4212;
5. vertex-binding and feature-gating changes from #4189.

Do not attribute a large FPS delta to post-dc95 #4301 by default; its own commit description characterizes it primarily as graphical-accuracy/caching work with almost no performance impact.
