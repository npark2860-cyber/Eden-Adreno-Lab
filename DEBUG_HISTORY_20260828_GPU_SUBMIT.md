# DEBUG HISTORY — 2026-08-28 GPU command closure / submit-gap follow-up

## Fixed source

Exact Eden baseline remained:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

## GPU Command Attribution build

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
- cleanup HEAD `368752c0cd9f98b1a94b7599e9a9a687eb1cc8a0`

## Runtime

Log:

`eden_log(20260828-011332).txt`

Environment:

- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Adreno X1-85
- Qualcomm 512.863.0
- Vulkan 1.3.295
- GPU Command Attribution ON
- Frame Build Attribution ON
- Frame Cadence ON
- Dequeue Attribution ON
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- old swap clamp and Descriptor Ring were still ON; next clean run must turn them OFF

### Representative slow window — frame 1200

120-frame aggregate:

- wall 6322.530 ms => ~52.69 ms/frame
- GPU worker queueWait 3887.384 ms => ~32.39 ms/frame
- active 2435.021 ms => ~20.29 ms/frame
- worker SubmitList time 2132.020 ms
- ProcessCommands 2061.420 ms => ~17.18 ms/frame
- PushCommand 3.903 ms total over 395 calls
- blockWait 0.000 ms

### Representative slow window — frame 1320

120-frame aggregate:

- wall 6311.908 ms => ~52.60 ms/frame
- GPU worker queueWait 4389.924 ms => ~36.58 ms/frame
- active 1921.739 ms => ~16.01 ms/frame
- worker SubmitList time 1917.736 ms
- ProcessCommands 1856.880 ms => ~15.47 ms/frame
- PushCommand 3.578 ms total over 366 calls
- blockWait 0.000 ms

## Conclusion

Strongly supported:

1. The asynchronous GPU worker is not saturated for the whole ~50 ms frame.
2. It spends the majority of the missing time blocked in queue `PopWait`, waiting for upstream commands.
3. DmaPusher / ProcessCommands is material but only ~15-20 ms/frame class in these slow windows.
4. `PushCommand` itself is tiny.
5. Caller synchronous `blockWait` is zero.
6. Therefore the next causal target is upstream of `GPUThread::PushCommand`, not deeper per-method GPU command interpretation.

## Exact source path traced

`NVDRV::Ioctl1/Ioctl2`
-> `Module::Ioctl1/Ioctl2`
-> `nvhost_gpu::Ioctl1/Ioctl2`
-> `SubmitGPFIFOBase1/SubmitGPFIFOBase2`
-> `SubmitGPFIFOImpl`
-> `GPU::PushGPUEntries`
-> `GPUThread::SubmitList`
-> `PushCommand`
-> GPU worker queue

Exact dc95 facts:

- `NVDRV::Ioctl1/2` reads guest IPC buffers before module/device dispatch.
- `Module::Ioctl1/2` is a file-descriptor lookup followed by device virtual dispatch.
- `SubmitGPFIFOBase1` allocates a `Tegra::CommandList`, then either reads guest memory via `ApplicationMemory().ReadBlock()` or copies inline command headers via `memcpy()`.
- `SubmitGPFIFOBase2` allocates the list and uses `memcpy()`.
- `SubmitGPFIFOImpl` takes `channel_mutex`, handles lazy channel init/fence/syncpoint bookkeeping, calls main `PushGPUEntries`, and may add wait/fence command lists.

## New experiment prepared

Branch:

`exp/x1-gpu-submit-gap-attribution`

New control:

`X1 Log: GPU Submit Gap Attribution`

New record:

`[X1-GPUSUBMIT]`

Purpose:

- measure gaps between NVDRV submit service entries,
- measure gaps between confirmed nvhost_gpu submit-device entries,
- measure gaps between actual `PushGPUEntries` calls,
- split NVDRV IPC read/dispatch/write work,
- split Base1/Base2 allocation + command-header transfer,
- split SubmitGPFIFOImpl lock/init/fence/syncpoint/push time.

Prepared files:

- `src/video_core/x1_gpu_submit_profiler.h`
- `tools/adreno_lab/transplant_dc95_gpu_submit_gap_attribution.py`
- `tools/adreno_lab/analyze_x1_gpu_submit_gap_attribution.py`
- `.github/workflows/build-dc95-x1-gpu-submit-gap-attribution.yml`
- `NEXT_ACTION_GPU_SUBMIT_GAP_ATTRIBUTION.md`

No GPU-submit-gap ARM64 build has been authorized or run at the time of this entry.
