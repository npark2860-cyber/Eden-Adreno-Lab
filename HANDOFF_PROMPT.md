# Handoff Prompt — Eden Adreno X1 Frame-Build Attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-frame-build-attribution`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260827_CONTINUED.md`
4. `LAB_BOOTSTRAP.md`
5. `NEXT_ACTION_FRAME_BUILD_ATTRIBUTION.md`
6. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain the closed facts in `CURRENT_HANDOFF.md`, especially:

- alias trivial dedupe is closed
- adaptive Uniform fast stream is mapped staging re-stream; wholesale classic-cache fallback did not fix gameplay
- TOTK 1.4.2 raw main BufferQueue `swap=2 -> 3` explains the discrete 30 -> <=20 cadence shape in that run
- raw swap originates in guest QueueBuffer input, not Qualcomm Vulkan Present
- raw-3/effective-2 HardwareComposer A/B executed correctly but did not break the gameplay ceiling
- integrated Diagnostic Harness build succeeded: run `33098438607`, artifact id `9658387549`
- Dequeue attribution closed 2-buffer backpressure as the slow-state cause
- fast state waits ~14 ms for a free slot; slow gameplay state waits ~0.001 ms and instead spends ~46.6 ms after Dequeue END before next Queue
- heavy X1 flow logs ON/OFF do not materially change that slow-state interval
- TOTK 1.2.1 reaches ~20-FPS class while raw swap stays 1, proving raw swap=3 is not the underlying renderer-performance cause

Current work is the runtime-selectable frame-build wall-time extension to the integrated Harness.

New control:

`X1 Log: Frame Build Attribution`

It emits `[X1-FRAMEBUILD]` 120-frame aggregates for:

- PrepareDraw total / FlushWork / GPU-memory FlushCaching / pre-config / GraphicsPipeline::Configure / post-config
- GraphicsPipeline Configure descriptor sync / stage scan / FillImageViews / image-buffer bind / graphics-buffer update / descriptor+render-target preparation / ConfigureDraw
- DispatchCompute total / flush / memory / configure / issue
- DrawTexture / Clear / FlushCommands / TickFrame

The existing Draw/texture reason-level scopes must remain intact. The new pass only measures wall time around them.

Prepared files:

- `src/video_core/renderer_vulkan/vk_x1_frame_build_profiler.h`
- `tools/adreno_lab/transplant_dc95_frame_build_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_build_attribution.py`
- `.github/workflows/build-dc95-x1-frame-build-attribution.yml`
- `NEXT_ACTION_FRAME_BUILD_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 Frame Build Attribution`

It must remain `workflow_dispatch` only.

Recommended first runtime after a successful future build:

- Frame Build Attribution ON
- Frame Cadence ON
- Dequeue Attribution ON
- all behavioral A/B controls OFF
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- Descriptor Ring OFF unless separately needed

NEXT ACTION:

Read `NEXT_ACTION_FRAME_BUILD_ATTRIBUTION.md` and finish static/pre-Actions validation. Stop before ARM64 Actions.

No current ARM64 build authorization exists. A fresh explicit user authorization is required for exactly one build attempt.
