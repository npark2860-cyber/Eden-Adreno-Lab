# DEBUG HISTORY — 2026-08-28 NVDRV IPC Dispatch Gap

## Static source review result

Exact dc95 source refined the previous runtime interpretation.

Confirmed architecture:

- synchronous `SendSyncRequest` eventually enters `KServerSession::OnRequest()`;
- the originator guest KThread is placed in `ThreadWaitReasonForDebugging::IPC` and `BeginWait()`;
- Nvidia services are launched by `RunOnHostCoreProcess("nvservices", Nvidia::LoopProcess)`;
- one Nvidia `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`;
- this Nvidia loop does not start additional host service workers;
- the host dummy KThread wait/wakeup path uses a host `std::condition_variable`;
- no deliberate 20-30 ms sleep was found in that wake path.

Therefore the prior statement that the full ~25-30 ms submit gap was already proven before the guest issued the NVDRV IPC was too strong.

The remaining interval must be split into:

1. previous candidate completion -> next candidate sync-request send boundary (`guestPostReply`), and
2. sync-request send boundary -> NVDRV candidate handler entry (`ipcDispatch`).

Existing lower NVDRV measurements already predict handler body / GPFIFO work is tiny.

## New branch

`exp/x1-nvdrv-ipc-dispatch-gap`

Created from documented guest-submit branch HEAD:

`5dfb93b831d59526083ab8616a61dda179ce9b4f`

## New observation-only pass

Runtime control:

`X1 Log: NVDRV IPC Dispatch Gap`

Setting:

`x1_nvdrv_ipc_dispatch_gap_log`

Default OFF.

Record:

`[X1-IPCDISPATCH]`

### Boundary A

In `SendSyncRequestImpl()` immediately before the existing `session->SendSyncRequest(...)` call:

- record current guest KThread ID + `steady_clock` timestamp;
- all synchronous IPC requests use only a fixed-size atomic timestamp table;
- no mutex/logging is taken on this generic hot path.

This is intentionally a send boundary just before the request can block, rather than an earlier SVC prologue timestamp.

### Boundary B

At candidate NVDRV GPU-submit handler entry in `NVDRV::Ioctl1/Ioctl2`:

- read the latest A timestamp for `ctx.GetThread()`;
- compute `ipcDispatch = B - A`;
- compute `guestPostReply = A - previous_candidate_C` for the same originator.

Candidate commands are aligned with the existing GPU-submit / guest-submit passes.

### Boundary C

A `SCOPE_EXIT` in the candidate NVDRV handler records handler completion after response construction.

Exact `ServerManager::CompleteSyncRequest()` then calls `SendReplyHLE()` directly on the same host service loop. Therefore C is a conservative reply-adjacent proxy with no intentional extra wait inserted by the profiler.

### 120-frame report

The new aggregate reports:

- dominant originator thread;
- request count / ioctl1 / ioctl2;
- `guestPostAvg`, total and max;
- `ipcDispatchAvg`, total and max;
- `serviceReplyAvg`, total and max;
- missing A/B pairing counters;
- number of generic sync entries recorded.

## Low-overhead design

Generic A recording is lock-free:

- fixed 256-slot array keyed by guest thread ID;
- atomic owner/timestamp pair;
- double owner read prevents accepting a slot while a collision is being rewritten.

Candidate B/C work is low frequency and uses the profiler mutex.

No per-instruction, per-method, all-thread wait or general IPC trace was added.

## Static safety workflow

Prepared workflow:

`Build dc95 X1 NVDRV IPC Dispatch Gap`

File:

`.github/workflows/build-dc95-x1-nvdrv-ipc-dispatch-gap.yml`

Normal trigger:

`workflow_dispatch` only.

The workflow reconstructs the complete existing diagnostic chain plus:

- Frame Build Attribution;
- GPU Command Attribution;
- GPU Submit Gap Attribution;
- Guest Submit Thread Attribution;
- then applies the new IPC-dispatch pass.

Before configure it hashes and requires unchanged:

- `k_client_session.cpp`;
- `k_server_session.cpp`;
- `k_thread.cpp`;
- `k_scheduler.cpp`;
- `global_scheduler_context.cpp`;
- `services.cpp`;
- `server_manager.cpp`;
- `multi_wait.cpp`;
- `nvhost_gpu.cpp`;
- `nvhost_ctrl.cpp`;
- BufferQueue/HWC/VI;
- GPU worker / control scheduler / DmaPusher;
- Vulkan swapchain/scheduler/graphics pipeline;
- prior GPU-command / GPU-submit / guest-submit profiler headers.

It also preserves counts of existing `session->SendSyncRequest`, NVDRV `Ioctl1/Ioctl2`, `RecordServiceEntry` and `RecordSubmitCaller` calls.

The new pass diff rejects added scheduling/wait/policy operations including `BeginWait`, `EndWait`, dummy-thread changes, `StartAdditionalHostThreads`, `WaitHost`, `StallApplication`, sleeps, rescheduling, priority/core-mask changes, `PushGPUEntries`, swap/buffer-count/target/speed changes.

## Interpretation for the next runtime

### guestPostAvg dominates

The prior NVDRV candidate completes promptly, but the guest does not issue the next candidate sync request until much later.

Next target: guest-side post-reply synchronization / other SVC waits / producer threads.

### ipcDispatchAvg dominates

The guest issued the synchronous request promptly and is sleeping in IPC, but `nvservices` does not enter the candidate handler until much later.

Next target: host `nvservices` wake/scheduling latency, single-thread ServerManager head-of-line delay, or a blocking Nvidia request.

### serviceReplyAvg dominates

Unexpected; re-open NVDRV handler/reply path because this would contradict previous lower-level timing.

## Build state

- new IPC-dispatch ARM64 build attempts: 0
- reruns: 0
- current ARM64 build authorization: none
- no Actions triggered during static preparation
