# DEBUG HISTORY CONTINUED — 2026-08-27

This file continues `DEBUG_HISTORY.md` without rewriting the older cumulative history.

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

## Integrated X1 Diagnostic Harness build — SUCCESS

Branch at build time:

`exp/x1-diagnostic-harness`

Authorized build:

- workflow `Build dc95 X1 Diagnostic Harness`
- run `33098438607`
- job `98609399031`
- attempt 1
- build HEAD `4d7f8dd972dcf6e0593961aea6992ae385d08608`
- artifact `Eden-dc95-X1-diagnostic-harness`
- artifact id `9658387549`
- size 31,309,147 bytes
- SHA-256 `d726c233ed226571252d0e12e6c284fd6038fc511bf07a83286ac13eab567dd1`
- no rerun

The one-shot trigger was removed after the run. Cleanup HEAD:

`7fb2f6866cb406f0c502765a57f60789291fa3e4`

The integrated binary made Frame Cadence and Dequeue Attribution runtime-selectable so subsequent attribution did not require a new build.

## Dequeue attribution — slow-state BufferQueue backpressure CLOSED

Runtime:

- TOTK 1.2.1
- exact Eden dc95
- Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223

### Fast state

Representative stable region around frame 1200-1680:

- Queue -> Queue median ~16.66 ms
- Queue -> next Dequeue entry ~0.13 ms
- Dequeue total ~14.40 ms
- free-slot wait ~14.29 ms
- Dequeue END -> next Queue ~2.06 ms

Interpretation:

When the producer is fast, the 2-buffer path does create real free-slot backpressure. The producer reaches Dequeue quickly and waits for the consumer.

### Slow gameplay state

Representative stable region around frame 2760-3600:

- Queue -> Queue median ~46.90 ms
- Queue -> next Dequeue entry ~0.16 ms
- Dequeue total ~0.053 ms
- free-slot wait ~0.001 ms
- Dequeue END -> next Queue ~46.63 ms

Conclusion — CONFIRMED:

> The slow ~45-50 ms frame is not waiting for a free BufferQueue slot. The producer obtains a buffer essentially immediately, then spends nearly the whole frame interval after DequeueBuffer returns and before the next QueueBuffer.

Do not pursue buffer-count changes or Dequeue wait removal as the next optimization.

## Heavy X1 logging overhead check — CLOSED

The same slow frame range was compared with broad flow logs ON and OFF.

Frame 2760-3120:

- heavy ON: Queue->Queue ~44.895 ms; Dequeue END->Queue ~44.616 ms
- heavy OFF: Queue->Queue ~45.368 ms; Dequeue END->Queue ~45.036 ms

Conclusion — CONFIRMED:

> The broad Scheduler/Present/Pipeline/Upload/QCOM diagnostic logs are not creating the ~20-FPS state.

## Swap interpretation refined by TOTK 1.2.1

The slow TOTK 1.2.1 run remained around the ~20-FPS class while every observed QueueBuffer used raw `swap=1`.

This does not invalidate the prior TOTK 1.4.2 cadence result. It refines the meaning:

- 1.4.2 raw `swap=2 -> 3` genuinely explains the discrete 30 -> 20 cadence quantization in that run
- but raw `swap=3` is not the underlying renderer-performance cause
- an independent ~45-50 ms frame-production cost exists before QueueBuffer

This is consistent with the earlier raw-3/effective-2 A/B: changing the consumer-side interval could not create frames that had not yet been produced.

## Frame-Build Attribution static preparation

Current branch:

`exp/x1-frame-build-attribution`

Goal:

Split the confirmed `Dequeue END -> next Queue` ~45-50 ms inside the Vulkan rasterizer/frame-build path.

New runtime control:

`X1 Log: Frame Build Attribution`

Default OFF.

Prepared observation-only aggregate:

`[X1-FRAMEBUILD]`

It measures:

- PrepareDraw total and major sub-stages
- GraphicsPipeline::Configure descriptor/image/buffer/descriptor-draw sub-stages
- DispatchCompute total and sub-stages
- DrawTexture / Clear / FlushCommands / TickFrame

Existing Draw/texture reason-level scopes are preserved; frame-build timing wraps them.

Prepared files:

- `src/video_core/renderer_vulkan/vk_x1_frame_build_profiler.h`
- `tools/adreno_lab/transplant_dc95_frame_build_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_build_attribution.py`
- `.github/workflows/build-dc95-x1-frame-build-attribution.yml`
- `NEXT_ACTION_FRAME_BUILD_ATTRIBUTION.md`

No frame-build ARM64 Actions have been run. No build authorization exists.
