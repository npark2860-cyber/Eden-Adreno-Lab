# NEXT ACTION — X1 GPU Submit Gap Attribution

Updated: 2026-08-28 KST

## Goal

Explain why the asynchronous Eden GPU worker is idle for roughly ~32-37 ms/frame in slow TOTK gameplay even though actual GPU-command processing is only roughly ~15-20 ms/frame.

The current strongest result is:

> GPU worker queue `PopWait` dominates the missing time; `PushCommand` itself is tiny and synchronous caller `blockWait` is zero.

Therefore the next split is upstream of `GPUThread::PushCommand`.

## Fixed baseline

- Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- branch: `exp/x1-gpu-submit-gap-attribution`
- predecessor cleanup HEAD: `exp/x1-gpu-command-attribution@368752c0cd9f98b1a94b7599e9a9a687eb1cc8a0`

Do not change the baseline.

## Exact source path

`NVDRV::Ioctl1/Ioctl2`
-> `Module::Ioctl1/Ioctl2`
-> `nvhost_gpu::Ioctl1/Ioctl2`
-> `SubmitGPFIFOBase1/SubmitGPFIFOBase2`
-> `SubmitGPFIFOImpl`
-> `GPU::PushGPUEntries`
-> `GPUThread::SubmitList`
-> `PushCommand`
-> GPU worker queue

## New runtime control

`X1 Log: GPU Submit Gap Attribution`

Default OFF.

## New aggregate record

`[X1-GPUSUBMIT]`

120-frame aggregates include:

### NVDRV service boundary

- candidate GPU-submit `Ioctl1/Ioctl2` entry count
- inter-entry gap count / sum / max
- IPC input-buffer read and output-buffer preparation time
- module/device dispatch time
- output write-back time
- total service-side time

The service-level command filter uses group `H`, command `0x8` or `0x1b` for Ioctl1 and `0x1b` for Ioctl2. The analyzer compares service-candidate count with confirmed `nvhost_gpu` device-submit count; if counts differ, prefer device/push gap attribution.

### Confirmed nvhost_gpu boundary

- submit-device entry count
- inter-entry gap count / sum / max
- Base1/Base2 count
- `Tegra::CommandList` allocation time
- `ApplicationMemory().ReadBlock()` / `memcpy()` command-header transfer time
- total Base1/Base2 wall time
- submitted entry count

### SubmitGPFIFOImpl

- total time
- `channel_mutex` acquisition wait
- lazy channel initialization time
- fence-signalled check time
- syncpoint update time
- wait/main/fence PushGPUEntries call time
- actual PushGPUEntries entry count by type
- inter-PushGPUEntries gap count / sum / max

## Interpretation

### Case A — large submit gaps, tiny service work

If service/device/push gaps are large but service/impl/lock/copy time is tiny:

> the GPU worker starvation originates above NVDRV; the guest/upstream CPU side simply does not issue GPU submissions for long intervals.

Next step: instrument guest CPU/HLE scheduling around the NVDRV IPC caller boundary rather than GPU internals.

### Case B — NVDRV service work is large

If service total, input read or device dispatch is material:

> Eden HLE/NVDRV service processing owns the gap.

Then split the measured service owner only.

### Case C — nvhost_gpu GPFIFO preparation is large

If Base1/Base2 copy/read, channel lock or SubmitGPFIFOImpl dominates:

> the nvhost GPU submission path owns the gap.

Then optimize only that measured subpath.

## Recommended runtime

Use the same TOTK 1.2.1 gameplay route.

DFPS OFF first.

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
- Draw skip A/B
- Dispatch skip A/B
- Scheduler Sync heavy log
- Present log
- Pipeline log
- Upload/Barrier log
- QCOM workaround log

The previous GPU-command runtime accidentally still had swap clamp and Descriptor Ring ON. Do not repeat that for the clean submit-gap run.

## Safety / scope

Observation only.

Do not modify:

- guest command order
- queue block/non-block semantics
- channel mutex semantics
- fence/syncpoint behavior
- scheduler policy
- BufferQueue / HWC / VI cadence
- Vulkan submit/fence/barrier/render-pass policy
- speed limiter / VSync / Mailbox / Target_60

The workflow checks call-count preservation for:

- `ctx.ReadBuffer(0)`
- `nvdrv->Ioctl1/Ioctl2`
- `gpu.PushGPUEntries`
- `ApplicationMemory().ReadBlock`
- `std::memcpy`
- `std::scoped_lock lock(channel_mutex)`
- fence-signalled checks
- syncpoint increment calls

It also hashes critical files that the new pass must not change, including GPU worker/command-processing, BufferQueue, HWC, VI, Vulkan scheduler/swapchain and buffer-cache paths.

## Workflow

`Build dc95 X1 GPU Submit Gap Attribution`

File:

`.github/workflows/build-dc95-x1-gpu-submit-gap-attribution.yml`

Normal trigger:

`workflow_dispatch` only.

## Build rule

**No ARM64 build/re-run without a fresh explicit user authorization. One authorization = exactly one attempt.**

Current GPU-submit-gap ARM64 attempts: 0.
