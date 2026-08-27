# NEXT ACTION — X1 Frame-Build Attribution

Updated: 2026-08-27 KST

## Fixed baseline

- Lab repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- current branch: `exp/x1-frame-build-attribution`
- predecessor: `exp/x1-diagnostic-harness@7fb2f6866cb406f0c502765a57f60789291fa3e4`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Why this is the next experiment

The integrated Diagnostic Harness closed the BufferQueue/backpressure hypothesis for the slow gameplay state.

Matched TOTK 1.2.1 / Adreno X1-85 heavy-logging-OFF run:

- fast state: Queue->Queue ~16.66 ms, Dequeue free-slot wait ~14.29 ms, Dequeue END->Queue ~2.06 ms
- slow state: Queue->Queue ~46.90 ms, Dequeue free-slot wait ~0.001 ms, Dequeue END->Queue ~46.63 ms

The same slow-region shape remained with heavy X1 flow logs ON and OFF.

Therefore:

> The low-FPS frame is not spending ~45-50 ms waiting for a free BufferQueue slot. The missing time appears after DequeueBuffer returns and before the next QueueBuffer submission.

TOTK 1.2.1 also demonstrates the slow ~20-FPS state while raw QueueBuffer remains `swap=1`, so the earlier TOTK 1.4.2 `swap=3` cadence is not the underlying renderer-performance cause.

## New runtime control

`X1 Log: Frame Build Attribution`

Default: OFF.

Observation-only steady-clock timing. It adds no waits, sleeps, submits, flushes, barriers, render-pass changes, queue policy, swap policy, buffer-count policy, or guest-state change.

## What `[X1-FRAMEBUILD]` measures

Every 120 renderer frames it reports aggregate wall time for:

### PrepareDraw

- total Draw preparation wall time
- `FlushWork`
- `gpu_memory->FlushCaching`
- pipeline lookup + cache mutex acquisition + `SetEngine`
- `GraphicsPipeline::Configure`
- post-config dynamic/query/transform-feedback/draw-command work

### GraphicsPipeline::ConfigureImpl

- descriptor synchronization
- shader-stage descriptor/image/sampler scan
- `FillImageViews`
- texture/image-buffer binding
- graphics-buffer update / host geometry binding
- descriptor acquisition + stage binding + PostCopyBarrier + render-target/feedback preparation
- `ConfigureDraw`

The existing Draw/texture reason-level scopes remain intact; the new profiler measures wall time around them rather than replacing them.

### Other top-level work

- `DispatchCompute` total + flush / memory / configure / issue tail
- `DrawTexture`
- `Clear`
- `FlushCommands`
- `TickFrame`

Analyzer:

`tools/adreno_lab/analyze_x1_frame_build_attribution.py`

## Prepared files

- `src/video_core/renderer_vulkan/vk_x1_frame_build_profiler.h`
- `tools/adreno_lab/transplant_dc95_frame_build_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_build_attribution.py`
- `.github/workflows/build-dc95-x1-frame-build-attribution.yml`

Workflow:

`Build dc95 X1 Frame Build Attribution`

Trigger:

`workflow_dispatch` only.

## Recommended first runtime

To match the latest Dequeue result, start with the same TOTK 1.2.1 save/route/settings.

ON:

- `X1 Log: Frame Build Attribution`
- `X1 Log: Frame Cadence`
- `X1 Log: Dequeue Attribution`

OFF:

- `X1 A/B: Clamp Main Swap Interval 3 To 2`
- `X1 A/B: Disable Adaptive Uniform Fast Stream`
- Draw/Dispatch skip A/B controls
- Scheduler Sync Log
- Present/Frame Log
- Pipeline/Shader Log
- Upload/Barrier Log
- QCOM Workaround Log
- Descriptor Ring Log unless separately needed

This minimizes instrumentation noise while retaining the producer-cycle boundary.

## Interpretation

Primary comparison is the slow-state ~45-50 ms `Dequeue END -> Queue` interval versus `[X1-FRAMEBUILD]` ms/frame.

Examples:

- high `cfg` + high `fillViews` => texture/image synchronization path is a primary CPU-side owner
- high `cfg` + high `buffers`/`descPrep` => buffer/Uniform/descriptor/render-target preparation dominates
- high Draw total but low Configure total => outer Draw preparation/dynamic/query/command work needs another split
- high Dispatch total => compute path is material
- measured renderer totals explain only part of 45-50 ms => remaining time is outside these Vulkan rasterizer scopes; next attribution must move one level upward into guest GPU command processing / channel execution

## Instrumentation-overhead check

The profiler performs steady-clock reads at Draw/Configure boundaries. After the first attribution run, compare the same route with Frame Build Attribution OFF in the same binary if the FPS visibly changes. Treat wall-time percentages as attribution evidence first, not as zero-overhead production performance numbers.

## Safety / unchanged paths

The workflow requires the frame-build pass not to change:

- BufferQueue producer / Dequeue instrumentation
- HardwareComposer
- VI conductor
- GPU core
- Vulkan swapchain
- Vulkan scheduler
- nvhost_ctrl
- generic buffer cache
- Vulkan buffer cache

It also rejects newly introduced timing/queue-policy verbs in the frame-build-only diff.

## STOP CONDITION

Static preparation only.

Do **not** run ARM64 Actions without a fresh explicit user authorization.

If authorized later, exactly one attempt of `Build dc95 X1 Frame Build Attribution` may be started. If it fails, stop; no automatic rerun.
