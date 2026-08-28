# CURRENT HANDOFF — Eden Adreno X1 GPU Command Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-gpu-command-attribution`
- predecessor: `exp/x1-frame-build-attribution@f54b732e86e2ef0dd57a402a03b8a76cbbedc0e1`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Closed / retained facts

### Draw / texture / alias

- Draw reason-level barrier owner: `PostCopyBarrier`.
- Draw outside-RP large texture parent: `FillImageViews`.
- repeated alias pair/region traffic is not trivial unchanged-state duplication.
- same source modification tick among tracked alias repeats: 0.
- tracked repeated sources advanced modification tick.
- same-state + same-region candidates: 0.

Do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse.
- gameplay fast selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`.
- classic cached Uniform path is mostly clean.
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint.
- classified same-frame repeats: 99.17% same fingerprint.
- wholesale classic-cache fallback A/B did not break the gameplay ceiling; it moved cost into explicit copy/outside-RP/synchronization work.

Do not blindly reuse prior staging allocations or enable persistent Uniform bindings.

## Uniform cache A/B — completed

Successful build:

- workflow `Build dc95 X1 Uniform Cache AB`
- run `33045572814`
- job `98428654028`
- attempt 1
- build HEAD `8e8351953d966a1c7677940b7a926aae902969d1`
- artifact id `9636118096`
- SHA-256 `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`

Result: gameplay still ~18 FPS; wholesale classic-cache fallback is not the solution.

## Frame cadence attribution — completed

Successful build:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact id `9642483710`
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`

Matched TOTK 1.4.2 runtime:

- stable raw `swap=2`: QueueBuffer median ~33.352 ms, nominal 30-FPS cadence.
- stable raw `swap=3`: QueueBuffer median ~49.985 ms, nominal 20-FPS cadence.
- VI remains ~60 Hz.
- `WaitForComposite` is normally near 0 ms.
- transition observed directly at guest QueueBuffer raw `swap=2 -> 3`.

Raw `swap_interval` originates in guest `QueueBufferInput`; it is not created by Qualcomm Vulkan, Mailbox or Target_60.

## Swap interval 3 -> effective 2 A/B — completed

Successful build:

- workflow `Build dc95 X1 Swap Interval 3 To 2 AB`
- run `33066726140`
- job `98498505964`
- attempt 1
- build HEAD `c196cd1c61e6385009c136b3fb810d5ed9807615`
- artifact id `9644858627`
- SHA-256 `e3b4b71b59812f9c39a9bb8f637cf2b227aa1b9eef623615497f62a65241a7cb`

ON was confirmed: raw main `swap=3` was acquired as `effective=2`.

Result:

- producer cadence remained ~50-ms / ~19-FPS class.
- effective-2 opened some 2-tick acquire opportunities but did not create upstream frames.

Conclusion — CLOSED:

> HardwareComposer interval-3 acquire/release gating is not the primary cause of the <=20-FPS gameplay ceiling.

## Integrated X1 Diagnostic Harness — completed

Successful build:

- workflow `Build dc95 X1 Diagnostic Harness`
- run `33098438607`
- job `98609399031`
- attempt 1
- build HEAD `4d7f8dd972dcf6e0593961aea6992ae385d08608`
- artifact id `9658387549`
- SHA-256 `d726c233ed226571252d0e12e6c284fd6038fc511bf07a83286ac13eab567dd1`

Runtime-selectable controls include prior X1 logs/A-Bs plus Frame Cadence and Dequeue Attribution.

## Dequeue / BufferQueue attribution — completed

Runtime basis:

- exact Eden dc95
- TOTK 1.2.1
- Adreno X1-85
- Qualcomm 512.863.0 / Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223

Fast state around frame 1200-1680:

- Queue -> Queue median ~16.66 ms.
- Dequeue total ~14.40 ms.
- free-slot wait ~14.29 ms.
- Dequeue END -> next Queue ~2.06 ms.

Slow gameplay around frame 2760-3600:

- Queue -> Queue median ~46.90 ms.
- Queue -> next Dequeue entry ~0.16 ms.
- Dequeue total ~0.053 ms.
- free-slot wait ~0.001 ms.
- Dequeue END -> next Queue ~46.63 ms.

Conclusion — CLOSED:

> The ~45-50 ms low-FPS interval is not caused by waiting for a free BufferQueue slot. In the slow state the buffer is available essentially immediately; nearly all missing time appears after DequeueBuffer returns and before the next QueueBuffer submission.

Heavy diagnostic log overhead was also checked and did not explain the ~20-FPS behavior.

## Frame-Build Attribution — built and runtime-tested

Branch predecessor:

`exp/x1-frame-build-attribution`

Successful authorized build:

- workflow `Build dc95 X1 Frame Build Attribution`
- run `33115424368`
- job `98668715842`
- attempt 1
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact `Eden-dc95-X1-frame-build-attribution`
- artifact id `9665216124`
- size 31,315,972 bytes
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`
- no rerun
- one-shot marker removed; cleanup HEAD `f54b732e86e2ef0dd57a402a03b8a76cbbedc0e1`

### DFPS ON runtime

TOTK 1.2.1, stable slow gameplay:

- actual frame class: ~48.8 ms / ~20.5 FPS.
- raw QueueBuffer swap remained `1` in the observed slow state.
- Dequeue wait remained effectively zero.
- Draw count roughly ~3,066/frame.
- measured Vulkan Draw total roughly ~11.1 ms/frame.
- Graphics Configure roughly ~7.2 ms/frame.
- `FillImageViews` roughly ~0.7 ms/frame.
- roughly ~37 ms/frame remained outside the measured RasterizerVulkan Draw/Dispatch/Clear scopes.

### DFPS OFF runtime

Latest comparison log: `eden_log(20260827-234038).txt`.

Same TOTK 1.2.1 class and same FrameBuild/Cadence/Dequeue instrumentation.

Observed slow gameplay:

- raw QueueBuffer swap returned to `3`.
- HWC saw `effective=2` only because the old swap-clamp A/B was still enabled in this run.
- actual performance remained ~19-21 FPS.
- Dequeue free-slot wait remained ~0.001 ms.
- Dequeue END -> next Queue remained ~45.5 ms median.
- Draw count dropped to roughly ~1,962/frame.
- measured Vulkan Draw time dropped to roughly ~8.4 ms/frame.
- total measured rasterizer work remained only roughly ~9 ms/frame.
- roughly ~39 ms/frame remained outside the measured RasterizerVulkan Draw/Dispatch/Clear scopes.

### Interpretation of DFPS comparison

CLOSED / strongly supported:

- DFPS changes workload/cadence behavior, including raw swap behavior and Draw count.
- DFPS is not the root cause of the slow ~45-50 ms frame-production interval.
- raw `swap=3` is not the root renderer-performance cause; DFPS ON could remain around ~20 FPS with raw `swap=1`, and DFPS OFF remained around ~20 FPS with raw `swap=3`.
- simply reducing Draw count is insufficient by itself: DFPS OFF reduced Draw count materially without removing the ~20-FPS class.
- `FillImageViews` alone is not the owner of the missing ~37-39 ms.

The remaining unexplained time is above/outside the currently measured RasterizerVulkan Draw scopes.

## Current experiment — GPU Command Attribution

Branch:

`exp/x1-gpu-command-attribution`

Goal:

Split the remaining ~39 ms/frame between:

1. asynchronous GPU worker idle / waiting for upstream commands, and
2. Eden GPU command scheduling / DmaPusher processing.

New runtime control:

`X1 Log: GPU Command Attribution`

Default OFF.

New aggregate record:

`[X1-GPUCMD]`

120-frame aggregates include:

- GPU worker queue `PopWait` time.
- GPU worker active handling time by command class.
- upstream `PushCommand` total and synchronous block-wait time.
- `Tegra::Control::Scheduler::Push` total / bind / dispatch.
- `DmaPusher::DispatchCalls` total / loop / tail.
- Dma synchronization wait.
- `ProcessCommands` total + command word count.
- no per-method wall-clock timer or per-method atomic counter is used.

Prepared files:

- `src/video_core/x1_gpu_command_profiler.h`
- `tools/adreno_lab/transplant_dc95_gpu_command_attribution.py`
- `tools/adreno_lab/analyze_x1_gpu_command_attribution.py`
- `.github/workflows/build-dc95-x1-gpu-command-attribution.yml`
- `NEXT_ACTION_GPU_COMMAND_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 GPU Command Attribution`

Trigger:

`workflow_dispatch` only.

## Recommended first runtime after a future successful build

Same TOTK 1.2.1 gameplay route, DFPS OFF first.

ON:

- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- swap clamp A/B
- Uniform cache A/B
- Draw/Dispatch skip A/B
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs
- Descriptor Ring

Primary split:

- large `queueWait`, small `active/dma/process` => upstream/guest CPU command supply side.
- large `active/dma/process` => Eden command interpretation / method execution side.
- material `blockWait` => upstream caller synchronously waits for GPU-worker completion.

## What NOT to do

- no ARM64 Actions without fresh explicit permission.
- no automatic rerun.
- no raw guest QueueBuffer modification.
- no VSync / Mailbox / Target_60 / speed-limit changes for attribution.
- no scheduler/fence/barrier/render-pass policy changes.
- no buffer-count modification.
- no simple alias dedupe.
- no blind persistent Uniform binding.
- no blind previous-staging reuse.
- do not treat intentional ForceStop as a crash.

## NEXT ACTION

Read:

`NEXT_ACTION_GPU_COMMAND_ATTRIBUTION.md`

Static preparation only. **Stop before ARM64 Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 GPU Command Attribution`

If it fails, stop. No retry without another fresh explicit authorization.

## Build authorization state

- current branch: `exp/x1-gpu-command-attribution`
- GPU-command ARM64 build attempts: 0
- GPU-command reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
