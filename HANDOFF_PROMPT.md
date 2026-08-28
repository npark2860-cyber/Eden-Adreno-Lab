# Handoff Prompt — Eden Adreno X1 GPU Submit Gap Attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-gpu-submit-gap-attribution`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260827_CONTINUED.md`
4. `DEBUG_HISTORY_20260828_CONTINUED.md`
5. `DEBUG_HISTORY_20260828_GPU_SUBMIT.md`
6. `LAB_BOOTSTRAP.md`
7. `NEXT_ACTION_GPU_SUBMIT_GAP_ATTRIBUTION.md`
8. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain all closed facts in `CURRENT_HANDOFF.md`, especially:

- alias trivial dedupe is closed
- wholesale classic-cache Uniform fallback did not break the gameplay ceiling
- raw swap interval originates in guest QueueBuffer input, but raw swap / HWC interval gating is not the root renderer-performance cause
- DFPS changes cadence/workload shape but is not the root ~45-50 ms frame-production cause
- slow gameplay Dequeue free-slot wait is ~0.001 ms; BufferQueue backpressure is closed as root cause
- Frame-Build attribution found only ~9-12 ms/frame in measured Vulkan Draw/Dispatch/Clear scopes
- GPU Command Attribution then found the missing time is dominated by GPU worker queue `PopWait`, not by DmaPusher processing

GPU Command Attribution completed successfully:

- workflow `Build dc95 X1 GPU Command Attribution`
- run `33129866149`
- job `98716608240`
- attempt 1
- build HEAD `dafee3f7f08832dbd39aedf7f2c2607bf1b6112b`
- artifact id `9670361329`
- SHA-256 `5c0d99f3539dd46e79b8b3002ef48216acbcb7de1282c5078b5fb411dd389758`
- cleanup HEAD `368752c0cd9f98b1a94b7599e9a9a687eb1cc8a0`

Runtime log:

`eden_log(20260828-011332).txt`

Representative slow 120-frame windows:

- frame 1200: wall ~52.69 ms/frame, GPU worker queueWait ~32.39 ms/frame, active ~20.29 ms/frame, ProcessCommands ~17.18 ms/frame, PushCommand total 3.903 ms / 395 calls, blockWait 0
- frame 1320: wall ~52.60 ms/frame, GPU worker queueWait ~36.58 ms/frame, active ~16.01 ms/frame, ProcessCommands ~15.47 ms/frame, PushCommand total 3.578 ms / 366 calls, blockWait 0

Conclusion:

> the GPU worker is starved for upstream submissions for roughly ~30-35 ms/frame; the next target is upstream of `GPUThread::PushCommand`.

Exact source path:

`NVDRV::Ioctl1/Ioctl2`
-> `Module::Ioctl1/Ioctl2`
-> `nvhost_gpu::Ioctl1/Ioctl2`
-> `SubmitGPFIFOBase1/SubmitGPFIFOBase2`
-> `SubmitGPFIFOImpl`
-> `GPU::PushGPUEntries`
-> `GPUThread::SubmitList`
-> `PushCommand`

Current work is the runtime-selectable GPU submit-gap attribution layer.

New control:

`X1 Log: GPU Submit Gap Attribution`

It emits `[X1-GPUSUBMIT]` 120-frame aggregates for:

- gaps between candidate NVDRV submit service entries
- gaps between confirmed nvhost_gpu submit-device entries
- NVDRV IPC buffer read / device dispatch / output write time
- GPFIFO CommandList allocation and command-header read/copy time
- SubmitGPFIFOImpl channel-lock / init / fence / syncpoint time
- wait/main/fence PushGPUEntries call time
- gaps between actual PushGPUEntries calls

Primary next split:

- large submit gaps + tiny service/impl work => guest/upstream CPU is not issuing GPU submissions promptly
- large NVDRV service time => HLE/NVDRV service path
- large Base/lock/impl time => nvhost GPU submission path

Prepared files:

- `src/video_core/x1_gpu_submit_profiler.h`
- `tools/adreno_lab/transplant_dc95_gpu_submit_gap_attribution.py`
- `tools/adreno_lab/analyze_x1_gpu_submit_gap_attribution.py`
- `.github/workflows/build-dc95-x1-gpu-submit-gap-attribution.yml`
- `NEXT_ACTION_GPU_SUBMIT_GAP_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 GPU Submit Gap Attribution`

It must remain `workflow_dispatch` only.

Recommended future runtime after a successful build:

ON:
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:
- swap 3 -> 2 clamp A/B
- Descriptor Ring
- all behavioral A/B controls
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

NEXT ACTION:

Read `NEXT_ACTION_GPU_SUBMIT_GAP_ATTRIBUTION.md`, verify branch/HEAD/workflow state, and finish static/pre-Actions validation. Stop before ARM64 Actions.

No current ARM64 build authorization exists. A fresh explicit user authorization is required for exactly one GPU-submit-gap build attempt.
