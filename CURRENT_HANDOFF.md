# CURRENT HANDOFF — Eden Adreno X1 Frame-Build Attribution

Updated: 2026-08-27 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-frame-build-attribution`
- predecessor: `exp/x1-diagnostic-harness@7fb2f6866cb406f0c502765a57f60789291fa3e4`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Retained closed facts

### Alias

Repeated alias pair/region traffic is not trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse
- gameplay fast selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached Uniform path is mostly clean
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint
- classified same-frame repeats: 99.17% same fingerprint
- wholesale classic-cache fallback A/B did not break the gameplay ceiling; it moved cost into explicit copy/outside-RP/synchronization work

Do not blindly reuse prior staging allocations or enable persistent Uniform bindings.

## Uniform cache A/B — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Uniform Cache AB`
- run `33045572814`
- job `98428654028`
- attempt 1
- build HEAD `8e8351953d966a1c7677940b7a926aae902969d1`
- artifact id `9636118096`
- SHA-256 `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`

ON result:

- adaptive fast / fastSkip = 0
- redirected classic-cache visits ~94.33% clean
- gameplay still ~18 FPS
- cost migrated into explicit copy / outside-RP / synchronization

Conclusion: wholesale classic-cache fallback is not an optimization.

## Frame cadence attribution — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact id `9642483710`
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`

Matched TOTK 1.4.2 runtime:

- stable raw `swap=2`: QueueBuffer median ~33.352 ms, nominal 30-FPS cadence
- stable raw `swap=3`: QueueBuffer median ~49.985 ms, nominal 20-FPS cadence
- main acquire follows ~33.5 ms vs ~50.0 ms
- VI remains ~60 Hz
- `WaitForComposite` is normally near 0 ms
- transition observed directly at QueueBuffer raw `swap=2 -> 3`

Meaning:

> The discrete 30 -> <=20 shape in that 1.4.2 run is encoded in guest/main BufferQueue cadence. Raw 2 gives nominal 60/2=30 opportunities; raw 3 gives nominal 60/3=20 opportunities.

Raw `swap_interval` originates in guest `QueueBufferInput`; it is not created by Qualcomm Vulkan, Mailbox, or Target_60.

## Swap interval 3 -> effective 2 A/B — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Swap Interval 3 To 2 AB`
- run `33066726140`
- job `98498505964`
- attempt 1
- build HEAD `c196cd1c61e6385009c136b3fb810d5ed9807615`
- artifact id `9644858627`
- SHA-256 `e3b4b71b59812f9c39a9bb8f637cf2b227aa1b9eef623615497f62a65241a7cb`
- no rerun

ON was confirmed: raw main `swap=3` was acquired as `effective=2`.

Result:

- raw producer cadence remained ~50-ms / ~19-FPS class
- effective-2 opened some 2-tick acquire opportunities but did not create upstream frames

Conclusion — CLOSED:

> HardwareComposer interval-3 acquire/release gating is not the primary cause of the <=20-FPS gameplay ceiling.

Do not repeat a simple producer/compositor `3 -> 2` clamp as the next optimization.

## Integrated X1 Diagnostic Harness — built successfully

Branch predecessor:

`exp/x1-diagnostic-harness`

Authorized build — SUCCESS:

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
- one-shot trigger removed; predecessor cleanup HEAD `7fb2f6866cb406f0c502765a57f60789291fa3e4`

Runtime-selectable controls include the earlier X1 flow logs and A/Bs plus:

- `X1 Log: Frame Cadence`
- `X1 Log: Dequeue Attribution`

## Dequeue / BufferQueue attribution — completed

Runtime basis:

- exact Eden dc95
- TOTK 1.2.1
- Adreno X1-85
- Qualcomm 512.863.0 / Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223

### Fast state

Representative stable region around frame 1200-1680:

- Queue -> Queue median ~16.66 ms
- Queue -> next Dequeue entry ~0.13 ms
- Dequeue total ~14.40 ms
- free-slot wait ~14.29 ms
- Dequeue END -> next Queue ~2.06 ms

Interpretation: when the producer is fast, it really does wait for the 2-buffer queue.

### Slow gameplay state

Representative stable region around frame 2760-3600:

- Queue -> Queue median ~46.90 ms
- Queue -> next Dequeue entry ~0.16 ms
- Dequeue total ~0.053 ms
- free-slot wait ~0.001 ms
- Dequeue END -> next Queue ~46.63 ms

Interpretation — CLOSED:

> The ~45-50 ms low-FPS interval is not caused by waiting for a free BufferQueue slot. In the slow state the buffer is available essentially immediately; nearly all missing time appears after DequeueBuffer returns and before the next QueueBuffer submission.

### Heavy diagnostic log overhead check

Same slow region with broad X1 flow logs ON vs OFF remained essentially unchanged:

- heavy ON, frame 2760-3120: Queue->Queue ~44.895 ms; Dequeue END->Queue ~44.616 ms
- heavy OFF, same frame range: Queue->Queue ~45.368 ms; Dequeue END->Queue ~45.036 ms

Therefore broad X1 logging is not the source of the ~20-FPS behavior.

### Important swap interpretation update

In these TOTK 1.2.1 slow-state runs, QueueBuffer remained raw `swap=1` while gameplay was still around ~20 FPS.

Therefore:

> `swap=3` explains/quantizes the 30->20 cadence shape seen in the earlier TOTK 1.4.2 run, but it is not the underlying renderer-performance cause. A slow ~45-50 ms frame-production path exists independently of raw swap=3.

## Current experiment — Frame-Build Attribution

Branch:

`exp/x1-frame-build-attribution`

Goal:

Split the confirmed slow-state `Dequeue END -> next Queue` ~45-50 ms inside the Vulkan rasterizer/frame-build path.

New runtime control:

`X1 Log: Frame Build Attribution`

Default OFF.

New aggregate record:

`[X1-FRAMEBUILD]`

It reports 120-frame steady-clock wall-time totals for:

### PrepareDraw

- total
- `FlushWork`
- `gpu_memory->FlushCaching`
- pipeline lookup / cache lock / SetEngine
- `GraphicsPipeline::Configure`
- post-config dynamic/query/transform-feedback/draw-command work

### GraphicsPipeline::ConfigureImpl

- descriptor synchronization
- stage descriptor/image/sampler scan
- `FillImageViews`
- texture/image-buffer binding
- graphics-buffer update / geometry binding
- descriptor acquire + stage binding + PostCopyBarrier + render-target/feedback preparation
- `ConfigureDraw`

Existing Draw/texture reason-level scopes remain intact; this new pass wraps them with wall-time measurement.

### Other paths

- DispatchCompute total + flush / memory / configure / issue tail
- DrawTexture
- Clear
- FlushCommands
- TickFrame

Prepared files:

- `src/video_core/renderer_vulkan/vk_x1_frame_build_profiler.h`
- `tools/adreno_lab/transplant_dc95_frame_build_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_build_attribution.py`
- `.github/workflows/build-dc95-x1-frame-build-attribution.yml`
- `NEXT_ACTION_FRAME_BUILD_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 Frame Build Attribution`

Trigger:

`workflow_dispatch` only.

The workflow reconstructs the complete existing diagnostic chain, applies the integrated Harness, then applies only the new frame-build wall-time pass.

The frame-build pass is not allowed to alter and the workflow hashes:

- BufferQueue producer
- HardwareComposer
- VI conductor
- GPU core
- Vulkan swapchain
- Vulkan scheduler
- nvhost_ctrl
- generic buffer cache
- Vulkan buffer cache

## Recommended first runtime after a future successful build

Match the latest TOTK 1.2.1 route first.

ON:

- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- swap clamp A/B
- Uniform cache A/B
- Draw/Dispatch skip A/B
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs
- Descriptor Ring unless separately needed

Primary question:

> Which measured renderer sub-stage owns the ~45-50 ms between Dequeue return and the next QueueBuffer?

If the measured Vulkan scopes explain only a small fraction of the interval, move attribution one level upward into guest GPU command/channel execution rather than returning to BufferQueue/present pacing.

## What NOT to do

- no ARM64 Actions without fresh explicit permission
- no automatic rerun
- no raw guest QueueBuffer modification
- no VSync / Mailbox / Target_60 / speed-limit changes for this attribution
- no scheduler/fence/barrier/render-pass policy changes
- no buffer-count modification
- no simple alias dedupe
- no blind persistent Uniform binding
- no blind previous-staging reuse
- do not treat intentional ForceStop as a crash

## NEXT ACTION

Read:

`NEXT_ACTION_FRAME_BUILD_ATTRIBUTION.md`

Static preparation is in progress / pre-Actions validation only. **Stop before ARM64 Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Frame Build Attribution`

If it fails, stop. No retry without another fresh explicit authorization.

## Build authorization state

- current branch: `exp/x1-frame-build-attribution`
- frame-build ARM64 build attempts: 0
- frame-build reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
