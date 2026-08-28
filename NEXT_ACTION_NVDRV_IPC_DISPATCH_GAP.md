# NEXT ACTION — X1 NVDRV IPC Dispatch Gap Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Current lab branch: `exp/x1-nvdrv-ipc-dispatch-gap`
- predecessor source-review HEAD: `exp/x1-guest-submit-thread-attribution@5dfb93b831d59526083ab8616a61dda179ce9b4f`

Do not change the Eden baseline.

**ARM64 Actions rule: no build or rerun without fresh explicit user authorization. One authorization = exactly one attempt.**

## Why this experiment exists

Completed runtime attribution established:

- GPU worker spends roughly 30-35 ms/frame idle waiting for command supply;
- lower NVDRV GPFIFO preparation is tiny once the candidate handler starts;
- one guest thread `tid=0x53` owns essentially all candidate GPU-submit requests;
- its observed CPU share between candidate handler entries is only about 1-2%.

Exact dc95 source then refined the boundary:

- synchronous IPC sleeps the originator KThread in `IPC` wait;
- Nvidia services run through a detached host `nvservices` process;
- one `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`;
- there are no additional Nvidia host service workers in this path.

Therefore the missing interval may be either:

1. guest-side post-reply work/wait before the next NVDRV sync request is issued, or
2. request-to-handler dispatch delay after the guest has already issued the sync IPC and gone to sleep.

## Prepared runtime control

`X1 Log: NVDRV IPC Dispatch Gap`

Setting:

`x1_nvdrv_ipc_dispatch_gap_log`

Default OFF.

New report:

`[X1-IPCDISPATCH]`

## Exact measurement

### A — generic sync-request send boundary

In `SendSyncRequestImpl()`, immediately before the existing:

`session->SendSyncRequest(...)`

record current guest KThread ID + `steady_clock` timestamp.

The generic path uses only a fixed-size lock-free atomic table when the profiler is enabled. No general IPC line logging or mutex is added at A.

### B — candidate NVDRV handler entry

For candidate GPU-submit `Ioctl1/Ioctl2` requests:

- pair `ctx.GetThread()` with its latest A timestamp;
- compute `ipcDispatch = B - A`;
- compute `guestPostReply = A - previous candidate C` for that thread.

### C — candidate handler completion / reply-adjacent proxy

A `SCOPE_EXIT` records handler completion after response construction.

Exact `ServerManager::CompleteSyncRequest()` directly follows service completion with `SendReplyHLE()` on the same host loop, so C is a conservative reply-adjacent boundary.

## 120-frame fields

The dominant candidate submitter report includes:

- request count and dominant share;
- ioctl1 / ioctl2 counts;
- `guestPostAvg`, total and max;
- `ipcDispatchAvg`, total and max;
- `serviceReplyAvg`, total and max;
- missing A/B pairing counters;
- generic sync-entry count.

Analyzer:

`tools/adreno_lab/analyze_x1_nvdrv_ipc_dispatch_gap.py`

## Interpretation

### Case A — `guestPostAvg` dominates

> The prior NVDRV request completed, but the guest waits/works elsewhere before issuing the next candidate submit request.

Next target:

- targeted non-NVDRV SVC/wait transitions for `tid=0x53`;
- producer threads/events that wake or feed the submitter.

### Case B — `ipcDispatchAvg` dominates

> The guest issues the request promptly and sleeps in IPC, but the host `nvservices` loop enters the candidate handler late.

Next target:

1. Windows host scheduling/wakeup latency of `nvservices`;
2. single-thread `ServerManager` head-of-line delay;
3. blocking Nvidia ioctl occupancy.

### Case C — `serviceReplyAvg` dominates

This would contradict the existing lower-NVDRV timing and requires reopening the handler/reply path.

## Prepared files

- `src/core/x1_nvdrv_ipc_dispatch_profiler.h`
- `tools/adreno_lab/transplant_dc95_nvdrv_ipc_dispatch_gap.py`
- `tools/adreno_lab/analyze_x1_nvdrv_ipc_dispatch_gap.py`
- `.github/workflows/build-dc95-x1-nvdrv-ipc-dispatch-gap.yml`
- `DEBUG_HISTORY_20260828_IPC_DISPATCH.md`

## Static safety design

The pass may modify generated:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h/.cpp`
- `src/core/hle/kernel/svc/svc_ipc.cpp`
- `src/core/hle/service/nvdrv/nvdrv_interface.cpp`
- `src/video_core/renderer_vulkan/vk_rasterizer.cpp`
- plus the new profiler header.

The workflow hashes and requires unchanged:

- KClient/KServer session implementation;
- KThread / KScheduler / GlobalSchedulerContext;
- `services.cpp`, `server_manager.cpp`, `multi_wait.cpp`;
- nvhost GPU/ctrl;
- BufferQueue/HWC/VI;
- GPU worker / DmaPusher;
- Vulkan swapchain/scheduler/graphics pipeline;
- prior GPU-command, GPU-submit and guest-submit profiler headers.

Existing sync request / NVDRV service / previous profiler call counts are preserved.

The pass must not add `BeginWait`, `EndWait`, dummy-thread behavior, extra server workers, `WaitHost`, `StallApplication`, sleeps, scheduling/priority/core changes, GPU submission behavior, swap/buffer-count/target/speed changes.

## Recommended first runtime after a future successful build

Use the same TOTK 1.2.1 gameplay route, DFPS OFF first.

ON:

- NVDRV IPC Dispatch Gap
- Guest Submit Thread Attribution
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

## Build state

Static preparation complete.

Workflow:

`Build dc95 X1 NVDRV IPC Dispatch Gap`

Normal trigger must remain:

`workflow_dispatch` only.

- IPC-dispatch ARM64 build attempts: 0
- IPC-dispatch reruns: 0
- current ARM64 build authorization: **none**

**Stop before ARM64 Actions. A fresh explicit user authorization is required for exactly one build attempt.**
