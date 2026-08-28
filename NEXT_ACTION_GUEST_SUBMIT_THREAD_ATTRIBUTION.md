# NEXT ACTION — X1 Guest Submit Thread Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Lab branch: `exp/x1-guest-submit-thread-attribution`
- predecessor cleanup: `exp/x1-gpu-submit-gap-attribution@d17eb7314b2809c95e53874dbc7f64808df67006`

Do not change the Eden baseline.

**ARM64 Actions rule: no build or rerun without fresh explicit user authorization. One authorization = exactly one attempt.**

## Why this experiment exists

GPU-command attribution showed that slow gameplay spends roughly 30-35 ms/frame with the asynchronous GPU worker idle in queue `PopWait`, while actual command processing is roughly 15-20 ms/frame.

GPU-submit-gap attribution then moved the boundary above NVDRV:

- slow gameplay is ~50-55 ms/frame class,
- candidate NVDRV submit-service gap, confirmed nvhost_gpu device-submit gap and actual `PushGPUEntries` gap are effectively identical,
- stable slow windows are roughly ~26 ms per submit interval with ~2 main submits/frame,
- NVDRV service work is only roughly ~0.05-0.06 ms/frame,
- `SubmitGPFIFOImpl` is roughly ~0.01-0.02 ms/frame,
- channel lock / copy / fence / syncpoint overhead is tiny.

Therefore the missing interval already exists **before the submit ioctl reaches NVDRV**.

The next question is no longer whether NVDRV is slow. It is:

> Which guest thread issues the GPU submit ioctls, and between consecutive submits is that thread actually consuming guest CPU time or mostly waiting/preempted?

## Exact-source basis

`HLERequestContext` retains the originator `Kernel::KThread` for the synchronous IPC request and exposes it through `ctx.GetThread()`.

Exact dc95 `KThread` exposes:

- `GetThreadId()`
- `GetCpuTime()`
- `GetCurrentCore()`
- `GetActiveCore()`
- `GetPriority()`
- `GetContext().pc`

Exact dc95 scheduler updates `KThread::GetCpuTime()` from the same `CoreTiming().GetClockTicks()` time base at context switches. Because a synchronous NVDRV request blocks/deschedules the originator before the HLE service handles it, the CPU-time snapshot at NVDRV entry is suitable for comparing consecutive submit requests from the same thread.

## New runtime control

`X1 Log: Guest Submit Thread Attribution`

Setting:

`x1_guest_submit_thread_attribution_log`

Default OFF.

New record:

`[X1-GUESTSUBMIT]`

## What it measures

For candidate GPU submit ioctls only (`'H'/0x8` and `'H'/0x1b`, aligned with the existing GPU-submit profiler):

- originator guest thread ID,
- submit count by originator thread,
- dominant submitter share,
- same-thread wall-clock gap between consecutive submit requests,
- guest `CoreTiming` tick delta between those requests,
- originator `KThread::GetCpuTime()` tick delta between those requests,
- `cpuShare = thread CPU tick delta / elapsed guest tick delta`,
- saved guest PC at submit request,
- same-PC vs PC-change count,
- current core / active core / priority.

Up to 8 submitter thread IDs are tracked. This is deliberately small because the expected GPU producer set is tiny and the goal is attribution, not a general thread profiler.

## Why CPU-share is the decisive first split

### Case A — one dominant thread, high CPU share

If one thread owns most submits and its `cpuShare` is high across the slow windows:

> The guest GPU producer is CPU-bound between submit requests.

The next step should then identify which guest code / emulator CPU path consumes that execution time. A targeted PC/block sampler or Dynarmic-side attribution becomes justified.

### Case B — one dominant thread, low CPU share

If one thread owns most submits but its `cpuShare` is low while wall gaps remain ~25-30 ms:

> The submitter spends most of the interval not executing guest CPU instructions.

Then instrument only that thread's kernel wait/synchronization/SVC transitions to determine whether it is waiting on IPC, synchronization, condition variables, arbitration, sleep, or scheduler preemption.

### Case C — multiple submitter threads

If dominant share is low or thread IDs alternate materially:

> GPU production is distributed across guest threads.

Then attribute each thread separately before adding deeper scheduler instrumentation.

## Caller PC caveat

The saved PC is useful as submit-callsite identity evidence. It does **not** by itself prove that the intervening 25-30 ms executes at that PC. Do not infer a hot function solely from repeated submit-entry PC values.

## Prepared files

- `src/video_core/x1_guest_submit_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_submit_thread_attribution.py`
- `tools/adreno_lab/analyze_x1_guest_submit_thread_attribution.py`
- `.github/workflows/build-dc95-x1-guest-submit-thread-attribution.yml`

## Safety design

The new pass modifies only generated:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h/.cpp`
- `src/core/hle/service/nvdrv/nvdrv_interface.cpp`
- `src/video_core/renderer_vulkan/vk_rasterizer.cpp`
- plus the new profiler header.

It must not change:

- kernel scheduler behavior,
- service framework / HLE IPC behavior,
- nvhost_gpu submission behavior,
- GPU worker / DmaPusher behavior,
- Vulkan scheduler/present/render behavior,
- BufferQueue/HWC/VI behavior.

Workflow hashes those critical files before and after the pass. It also verifies existing `ReadBuffer`, `nvdrv->Ioctl1/2` and GPU-submit service-record call counts remain unchanged.

No sleep, wait, reschedule, state, priority, core-mask, swap, buffer-count, speed-limit or `PushGPUEntries` behavior may be added by this pass.

## Recommended runtime after a future successful build

Use the same TOTK 1.2.1 gameplay route, DFPS OFF first.

ON:

- Guest Submit Thread Attribution
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- `X1 A/B: Clamp Main Swap Interval 3 To 2`
- Descriptor Ring
- Uniform cache A/B
- Draw/Dispatch skip A/B
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

The previous GPU-submit runtime accidentally still had swap-clamp and Descriptor Ring ON. They are not needed for this experiment and should be OFF for the clean run.

## Build state

Static preparation only.

**Stop before ARM64 Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Guest Submit Thread Attribution`

If it fails, stop. No retry without another fresh authorization.
