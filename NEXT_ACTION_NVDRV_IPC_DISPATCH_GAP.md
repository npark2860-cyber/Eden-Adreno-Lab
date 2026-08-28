# NEXT ACTION — NVDRV IPC Dispatch Gap Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Current lab branch: `exp/x1-guest-submit-thread-attribution`
- Current cleanup lineage: `352867995e8c1623bfe2274f2125ffb4e10e4e2e` plus documentation-only updates

Do not change the Eden baseline.

**ARM64 Actions rule: no build or rerun without fresh explicit user authorization. One authorization = exactly one attempt.**

## Why the previous interpretation must be refined

Guest-submit-thread runtime established:

- one guest thread (`tid=0x53`) owns essentially all candidate GPU-submit requests;
- its submit-entry PC is overwhelmingly `0x8522f458`;
- its slow-gameplay CPU share between observed NVDRV handler entries is only about 1-2%;
- therefore it is not CPU-bound between those observations.

Exact dc95 source then showed an important architectural boundary:

- synchronous IPC puts the originator guest KThread into `IPC` wait;
- Nvidia HLE services run in a detached host-core process named `nvservices`;
- one `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`;
- the Nvidia loop does not start additional host service workers;
- the host dummy KThread sleeps on a host condition variable while `ServerManager::WaitAny()` waits for signaled sessions.

Existing GPU-submit-gap timers start at or inside the NVDRV handler. They do not measure request-to-handler dispatch latency.

Therefore we must distinguish:

> Did the guest issue the next submit late, or did it issue it promptly and then sleep while `nvservices` serviced it late?

## Decisive measurement

For candidate GPU-submit ioctls only, capture these timestamps:

- `A`: `Svc::SendSyncRequest` entry for the originator guest KThread;
- `B`: NVDRV `Ioctl1/Ioctl2` handler entry for that same KThread/request;
- `C`: NVDRV handler/reply completion;
- `A_next`: next matching sync-request entry from the same guest KThread.

Report:

- `guestPostReply = A_next - C_prev`
- `ipcDispatch = B - A`
- `serviceReply = C - B`
- request count / dominant thread ID / max values

Use one 120-frame aggregate aligned with the existing X1 reports.

## Pairing strategy

A synchronous KThread cannot issue a second synchronous IPC before the first reply completes.

Therefore a small per-KThread record is sufficient:

- on generic `Svc::SendSyncRequest` entry, store current KThread pointer/ID + wall timestamp;
- at NVDRV candidate-submit handler entry, read the latest sync-request timestamp for `ctx.GetThread()` and compute `ipcDispatch`;
- at NVDRV handler/reply completion, record completion timestamp for that originator;
- at the next matching sync-request entry from that thread, compute `guestPostReply` from the previous NVDRV completion.

Do not add a general all-request trace.

## Interpretation

### Case A — `guestPostReply` dominates

If `C_prev -> A_next` is roughly the missing 20-30 ms while `A -> B` is tiny:

> The submitter thread receives the NVDRV reply promptly but does not issue the next submit until much later.

Then inspect the submitter's non-NVDRV SVC/wait transitions and/or the producer thread(s) that wake it.

### Case B — `ipcDispatch` dominates

If `A -> B` is roughly the missing 20-30 ms:

> The guest already issued the NVDRV request and is sleeping in IPC; the host Nvidia service path is late dispatching it.

Then investigate:

1. Windows scheduling/wakeup latency of `nvservices` host thread;
2. single-thread ServerManager head-of-line delay from other Nvidia requests;
3. any blocking Nvidia ioctl occupying the event loop.

### Case C — both material

Attribute each part separately; do not collapse them into "guest wait".

## Exact source references to preserve

- `src/core/hle/kernel/svc/svc_ipc.cpp`
- `src/core/hle/kernel/k_client_session.cpp`
- `src/core/hle/kernel/k_server_session.cpp`
- `src/core/hle/service/services.cpp`
- `src/core/hle/service/server_manager.cpp`
- `src/core/hle/service/os/multi_wait.cpp`
- `src/core/hle/kernel/k_thread.cpp`
- `src/core/hle/kernel/k_scheduler.cpp`
- `src/core/hle/kernel/global_scheduler_context.cpp`
- `src/core/hle/service/nvdrv/nvdrv.cpp`
- `src/core/hle/service/nvdrv/nvdrv_interface.cpp`
- `src/core/hle/service/nvdrv/devices/nvhost_ctrl.cpp`

See `GUEST_SUBMIT_WAIT_SOURCE_MAP.md` for the static map.

## Safety constraints

The next profiler must be observation-only.

Do not change:

- scheduling policy / thread priority / core mask;
- dummy-thread wake behavior;
- `ServerManager` worker count;
- IPC semantics or deferral behavior;
- NVDRV ioctl behavior;
- syncpoint/fence behavior;
- GPU submission behavior;
- BufferQueue/HWC/VI;
- Vulkan rendering behavior;
- speed limit / VSync / frame pacing.

No experimental multithreading of `nvservices` yet. First prove where the latency resides.

## Build state

No new instrumentation has been built for this split.

Current ARM64 build authorization: **none**.

Do not start Actions until a future instrumentation branch is prepared and the user gives fresh explicit authorization.
