# CURRENT HANDOFF — Eden Adreno X1 GPU Submit Gap Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-gpu-submit-gap-attribution`
- predecessor cleanup HEAD: `exp/x1-gpu-command-attribution@368752c0cd9f98b1a94b7599e9a9a687eb1cc8a0`

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
- do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse.
- gameplay fast selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`.
- classic cached Uniform path is mostly clean.
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint.
- classified same-frame repeats: 99.17% same fingerprint.
- wholesale classic-cache fallback A/B did not break the gameplay ceiling.
- do not blindly reuse prior staging allocations or enable persistent Uniform bindings.

### Frame cadence / swap

- TOTK 1.4.2 raw main QueueBuffer `swap=2` maps to nominal ~30-FPS opportunities.
- raw `swap=3` maps to nominal ~20-FPS opportunities.
- VI remains ~60 Hz.
- raw swap interval originates in guest QueueBuffer input, not Qualcomm Vulkan Present/Mailbox/Target_60.
- raw-3 -> effective-2 HardwareComposer A/B executed correctly but did not create upstream frames.
- HardwareComposer interval gating is not the root <=20-FPS renderer-performance cause.
- DFPS ON could remain ~20-FPS class with raw swap=1.
- DFPS OFF could remain ~20-FPS class with raw swap=3.
- therefore DFPS and raw swap=3 are not the root cause of the ~45-50 ms frame-production interval.

### BufferQueue / Dequeue

Fast state:

- Queue -> Queue ~16.66 ms.
- free-slot wait ~14 ms class because producer is fast.

Slow gameplay:

- Queue -> Queue ~45-50 ms class.
- Queue -> next Dequeue entry ~0.16 ms.
- Dequeue total ~0.05 ms.
- free-slot wait ~0.001 ms.
- Dequeue END -> next Queue ~45-47 ms.

Conclusion — CLOSED:

> Slow gameplay is not waiting for a free BufferQueue slot. The buffer is immediately available; the missing time is after Dequeue returns and before the next QueueBuffer.

Heavy X1 diagnostic logging was also A/B checked and did not create the ~20-FPS behavior.

### Frame-Build Attribution

Successful build:

- workflow `Build dc95 X1 Frame Build Attribution`
- run `33115424368`
- job `98668715842`
- attempt 1
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact id `9665216124`
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`
- no rerun

Runtime conclusions:

- DFPS ON slow gameplay: ~48.8 ms/frame; measured Vulkan Draw ~11.1 ms/frame; Graphics Configure ~7.2 ms/frame; `FillImageViews` ~0.7 ms/frame; ~37 ms/frame outside measured RasterizerVulkan scopes.
- DFPS OFF slow gameplay: ~19-21 FPS; Draw count materially lower, measured Vulkan Draw ~8.4 ms/frame, yet ~39 ms/frame remained outside measured Draw/Dispatch/Clear scopes.
- `FillImageViews` alone is not the missing-time owner.
- high Draw count alone is not sufficient to explain the ceiling.

## GPU Command Attribution — completed

Branch predecessor:

`exp/x1-gpu-command-attribution`

Successful authorized build:

- workflow `Build dc95 X1 GPU Command Attribution`
- run `33129866149`
- job `98716608240`
- attempt 1
- build HEAD `dafee3f7f08832dbd39aedf7f2c2607bf1b6112b`
- artifact `Eden-dc95-X1-gpu-command-attribution`
- artifact id `9670361329`
- size 31,323,601 bytes
- SHA-256 `5c0d99f3539dd46e79b8b3002ef48216acbcb7de1282c5078b5fb411dd389758`
- success, no rerun
- one-shot marker removed; cleanup HEAD `368752c0cd9f98b1a94b7599e9a9a687eb1cc8a0`

Runtime log:

`eden_log(20260828-011332).txt`

Runtime basis:

- exact Eden dc95
- TOTK 1.2.1
- Adreno X1-85
- Qualcomm 512.863.0 / Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- GPU Command Attribution ON
- Frame Build Attribution ON
- Frame Cadence ON
- Dequeue Attribution ON
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- note: old swap 3 -> 2 clamp and Descriptor Ring were still ON in this runtime; both must be OFF in the next clean run

Representative slow windows:

### frame 1200 / 120-frame window

- wall: 6322.530 ms => ~52.69 ms/frame
- GPU worker queue `PopWait`: 3887.384 ms => ~32.39 ms/frame
- GPU worker active: 2435.021 ms => ~20.29 ms/frame
- worker SubmitList handling: 2132.020 ms
- `ProcessCommands`: 2061.420 ms => ~17.18 ms/frame
- `PushCommand`: 3.903 ms total / 395 calls
- synchronous caller blockWait: 0.000 ms

### frame 1320 / 120-frame window

- wall: 6311.908 ms => ~52.60 ms/frame
- GPU worker queue `PopWait`: 4389.924 ms => ~36.58 ms/frame
- GPU worker active: 1921.739 ms => ~16.01 ms/frame
- `ProcessCommands`: 1856.880 ms => ~15.47 ms/frame
- `PushCommand`: 3.578 ms total / 366 calls
- synchronous caller blockWait: 0.000 ms

GPU-command conclusion — STRONGLY SUPPORTED:

> In slow gameplay the asynchronous GPU worker spends the majority of wall time idle in its queue `PopWait`, waiting for upstream command supply. Eden command interpretation / DmaPusher processing is material (~15-20 ms/frame class) but does not own the missing ~30-35 ms. `PushCommand` itself is tiny and caller `blockWait` is zero.

Therefore the current primary causal target moves **upstream of `GPUThread::PushCommand`**.

Do not spend the next experiment splitting per-method DmaPusher work unless upstream submission attribution disproves this result.

## Exact upstream source chain

Exact dc95 source path is:

`NVDRV::Ioctl1/Ioctl2`
-> `Module::Ioctl1/Ioctl2`
-> `nvhost_gpu::Ioctl1/Ioctl2`
-> `SubmitGPFIFOBase1/SubmitGPFIFOBase2`
-> `SubmitGPFIFOImpl`
-> `GPU::PushGPUEntries`
-> `GPUThread::SubmitList`
-> `PushCommand`
-> GPU worker queue

Important exact-source details:

- `NVDRV::Ioctl1/2` reads IPC buffers before module/device dispatch.
- `SubmitGPFIFOBase1` may use `ApplicationMemory().ReadBlock()` for kickoff or `memcpy` for inline command headers.
- `SubmitGPFIFOBase2` copies command headers with `memcpy`.
- `SubmitGPFIFOImpl` takes `channel_mutex`, handles fence checks/syncpoint update, then calls `gpu.PushGPUEntries(...)` for the main list and optional wait/fence lists.
- `GPUThread::PushCommand` merely enqueues the command and only waits if `block=true`; measured runtime had blockWait=0.

## Current experiment — GPU Submit Gap Attribution

Branch:

`exp/x1-gpu-submit-gap-attribution`

Goal:

Resolve the GPU worker starvation by separating:

1. guest/upstream time before a GPU submit ioctl reaches NVDRV,
2. NVDRV IPC buffer/read/dispatch/write overhead,
3. `nvhost_gpu` GPFIFO allocation/read/copy work,
4. `SubmitGPFIFOImpl` channel-lock/fence/syncpoint overhead,
5. gaps between actual `PushGPUEntries` calls.

New runtime control:

`X1 Log: GPU Submit Gap Attribution`

Default OFF.

New aggregate record:

`[X1-GPUSUBMIT]`

120-frame aggregates include:

- candidate NVDRV submit-service entry count and inter-entry gap sum/max,
- confirmed `nvhost_gpu` submit-device entry count and inter-entry gap sum/max,
- NVDRV service total / input-read / device-dispatch / output-write wall time,
- SubmitGPFIFOBase1/Base2 total, CommandList allocation and command-header copy/read time,
- SubmitGPFIFOImpl total and channel-lock wait,
- lazy channel init, fence check and syncpoint update time,
- all wait/main/fence `PushGPUEntries` counts/time,
- gaps between actual `PushGPUEntries` calls,
- submitted GPFIFO entry count.

No queue semantics, command order, synchronization policy, fence behavior, guest state or Vulkan behavior is intentionally changed.

Prepared files:

- `src/video_core/x1_gpu_submit_profiler.h`
- `tools/adreno_lab/transplant_dc95_gpu_submit_gap_attribution.py`
- `tools/adreno_lab/analyze_x1_gpu_submit_gap_attribution.py`
- `.github/workflows/build-dc95-x1-gpu-submit-gap-attribution.yml`
- `NEXT_ACTION_GPU_SUBMIT_GAP_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 GPU Submit Gap Attribution`

Trigger must remain:

`workflow_dispatch` only.

## Interpretation for next runtime

### Case A — submit gaps are large, service work is tiny

If service/device/PushGPUEntries gaps are large while service/impl/lock/copy time is tiny:

> the GPU worker is starved because the guest/upstream CPU side simply does not submit GPU work for long intervals.

Then move next attribution above NVDRV into guest CPU execution / HLE scheduling around the caller.

### Case B — service entry is prompt but service work is large

If NVDRV service time or IPC read/dispatch dominates:

> Eden HLE/NVDRV service processing owns the gap.

Split IPC buffer transfer vs device dispatch further.

### Case C — nvhost GPFIFO work is large

If Base1/Base2 copy/read, channel-lock wait or SubmitGPFIFOImpl dominates:

> the nvhost GPU submission path owns the gap.

Optimize only the measured owner.

## Recommended first runtime after a successful future build

Use same TOTK 1.2.1 route, DFPS OFF first.

ON:

- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- swap 3 -> 2 clamp A/B
- Descriptor Ring
- Uniform cache A/B
- Draw/Dispatch skip A/B
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

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

`NEXT_ACTION_GPU_SUBMIT_GAP_ATTRIBUTION.md`

Static/pre-Actions verification only. **Stop before ARM64 Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 GPU Submit Gap Attribution`

If it fails, stop. No retry without another fresh explicit authorization.

## Build authorization state

- current branch: `exp/x1-gpu-submit-gap-attribution`
- GPU-command ARM64 build attempts: 1 successful, 0 reruns
- GPU-submit-gap ARM64 build attempts: 0
- GPU-submit-gap reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
