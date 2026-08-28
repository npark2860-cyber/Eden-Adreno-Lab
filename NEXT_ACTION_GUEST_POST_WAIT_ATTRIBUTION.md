# NEXT ACTION — X1 Guest Post Wait Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Current lab branch: `exp/x1-guest-post-wait-attribution`
- Predecessor completed IPC-dispatch branch HEAD: `exp/x1-nvdrv-ipc-dispatch-gap@491f911a6e7e13a9d43902edcc99a129ca08f893`

Do not change the Eden baseline.

**ARM64 Actions rule: no build or rerun without fresh explicit user authorization. One authorization = exactly one attempt.**

## Why this experiment exists

The completed NVDRV IPC Dispatch Gap runtime (`eden_log(20260828-061910).txt`) decisively selected guest-side Case A.

Representative 120-frame reports:

- frame 840: `guestPostAvg=16.840 ms`, `ipcDispatchAvg=0.021 ms`, `serviceReplyAvg=0.014 ms`;
- frame 1320: `guestPostAvg=26.743 ms`, `ipcDispatchAvg=0.017 ms`, `serviceReplyAvg=0.039 ms`;
- frame 1440: `guestPostAvg=29.091 ms`, `ipcDispatchAvg=0.027 ms`, `serviceReplyAvg=0.033 ms`.

`missingA=0` and `missingB=0` in the representative slow reports.

The dominant GPU submitter remains guest `tid=0x53`, essentially 100% of candidate submits, while its observed CPU share is only ~1-2% in slow gameplay.

Therefore the live question is now:

> Between previous candidate NVDRV completion/reply-adjacent C and the next candidate submit request, is `tid=0x53` mostly in an explicit guest wait, or is it Runnable but not scheduled / otherwise outside the measured wait states?

Host `nvservices` request-dispatch latency is closed as the missing 20-30 ms owner for this runtime.

## Exact dc95 source basis

`ThreadWaitReasonForDebugging` values in exact dc95:

- `None`
- `Sleep`
- `IPC`
- `Synchronization`
- `ConditionVar`
- `Arbitration`
- `Suspended`

`KThread::BeginWait()` moves the thread to `Waiting`.

`KThreadQueue::EndWait()` / `CancelWait()` move it back to `Runnable`.

`KThread::SetState()` is the common transition point and clears the debugging wait reason before applying the new base state. Therefore the observation hook must snapshot the old wait reason before the existing clear, while preserving the exact existing state mutation and scheduler callback.

## Prepared runtime control

`X1 Log: Guest Post Wait Attribution`

Setting:

`x1_guest_post_wait_attribution_log`

Default OFF.

New report:

`[X1-GUESTWAIT]`

## Measurement boundaries

### Window start

Candidate NVDRV handler completion C for the dynamically observed submitter thread opens the post-submit window.

The immediate reply wake belonging to that just-completed candidate request is explicitly ignored.

### Wait tracking

Observation-only hook in the existing `KThread::SetState()` transition:

- non-Waiting -> Waiting: record steady-clock start and current SVC ID;
- Waiting -> non-Waiting: record duration and classify using the old wait reason captured before dc95 clears it.

No per-event line logging is emitted.

### Window end

The next candidate NVDRV handler entry closes the window.

This is a practical proxy for the exact next sync-request A boundary. The completed IPC-dispatch runtime measured A -> handler entry at only ~0.02 ms/request, so this approximation is negligible relative to the ~27-29 ms guest-post interval.

The current candidate request's own IPC wait is excluded from the post-submit window accounting.

## 120-frame fields

`[X1-GUESTWAIT]` reports:

- dynamic target guest thread ID;
- candidate-window count;
- total / average / max window time;
- total completed KThread wait time;
- `waitShare` = tracked wait / window;
- `residual` = window time not explained by completed KThread waits;
- count/time by reason: `None`, `Sleep`, `IPC`, `Synchronization`, `ConditionVar`, `Arbitration`, `Suspended`;
- top 3 SVC IDs by tracked wait duration;
- pairing/transition sanity counters.

Analyzer:

`tools/adreno_lab/analyze_x1_guest_post_wait_attribution.py`

## Interpretation

### Case A — tracked wait dominates

If `waitShare` is high, the dominant reason directly chooses the next source target.

Examples:

- IPC dominates -> identify which non-candidate sync IPC/service the submitter waits on;
- Synchronization dominates -> inspect handles/events and producer/waker thread;
- ConditionVar dominates -> inspect process-wide-key producer;
- Arbitration dominates -> inspect address-arbiter owner/waker;
- Sleep dominates -> inspect sleep SVC cadence/timing.

### Case B — residual dominates while CPU share remains ~1-2%

If explicit waits explain little of the window but the submitter still has very low CPU share:

> the thread is likely Runnable but not scheduled for much of the interval, or the remaining time belongs to a scheduler/preemption boundary not represented by KThread wait state.

Next target then becomes targeted Runnable residency / scheduler competitor attribution for the dynamic submitter thread only.

### Case C — mixed

If both tracked wait and residual are material, preserve both and instrument only the dominant remaining component; do not jump to optimization.

## Prepared files

- `src/core/x1_guest_post_wait_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_post_wait_attribution.py`
- `tools/adreno_lab/analyze_x1_guest_post_wait_attribution.py`
- `.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml`
- `DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`

## Static safety design

The new pass may modify generated:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h/.cpp`
- `src/core/hle/kernel/k_thread.cpp`
- `src/core/hle/service/nvdrv/nvdrv_interface.cpp`
- `src/video_core/renderer_vulkan/vk_rasterizer.cpp`
- plus the new profiler header.

The workflow requires unchanged:

- `k_thread.h` and `k_thread_queue.cpp`;
- KClient/KServer session implementation;
- KScheduler / GlobalSchedulerContext;
- `svc_ipc.cpp` including the prior IPC-dispatch A hook;
- `server_manager.cpp`, `multi_wait.cpp`;
- nvhost GPU/ctrl;
- BufferQueue/HWC/VI;
- GPU worker / control scheduler / DmaPusher;
- Vulkan swapchain/scheduler/graphics pipeline;
- all prior GPU-command/GPU-submit/guest-submit/IPC-dispatch profiler headers.

Token-count guards preserve existing `BeginWait`, `EndWait`, `SetWaitReasonForDebugging`, `m_thread_state.store`, `OnThreadStateChanged`, NVDRV Ioctl and prior IPC-dispatch calls.

The pass must not add sleep/wait behavior, `WaitHost`, `StallApplication`, scheduling/priority/core changes, GPU submission changes, swap/buffer-count/frame-target/speed changes.

## Recommended first runtime after a future successful build

Use the same TOTK 1.2.1 gameplay route, DFPS OFF first.

ON:

- Guest Post Wait Attribution
- NVDRV IPC Dispatch Gap
- Guest Submit Thread Attribution
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- Descriptor Ring
- swap 3 -> 2 clamp A/B
- all behavioral A/B controls
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

## Build state

Static preparation only.

Workflow:

`Build dc95 X1 Guest Post Wait Attribution`

Normal trigger must remain:

`workflow_dispatch` only.

- Guest Post Wait ARM64 build attempts: **0**
- Guest Post Wait reruns: **0**
- current ARM64 build authorization: **none**

**Stop before ARM64 Actions. A fresh explicit user authorization is required for exactly one build attempt.**
