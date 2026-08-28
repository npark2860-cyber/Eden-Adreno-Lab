# CURRENT HANDOFF — Eden Adreno X1 NVDRV IPC Dispatch Gap

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-nvdrv-ipc-dispatch-gap`
- predecessor source-review HEAD: `exp/x1-guest-submit-thread-attribution@5dfb93b831d59526083ab8616a61dda179ce9b4f`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Closed / retained facts

### Draw / texture / alias

- Draw reason-level barrier owner: `PostCopyBarrier`.
- Draw outside-RP large texture parent: `FillImageViews`.
- repeated alias pair/region traffic is not trivial unchanged-state duplication.
- simple alias-copy dedupe remains rejected.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- adaptive small-Uniform fast path is mapped staging re-stream.
- payload fingerprint showed 97.65% of tracked repeated samples unchanged, but lifetime/in-flight/descriptor identity prevent blind staging reuse.
- wholesale classic-cache fallback A/B did not break the gameplay ceiling.

### Frame cadence / swap / DFPS

- raw main QueueBuffer `swap=2` can express nominal ~30-FPS opportunities; raw `swap=3` nominal ~20-FPS opportunities.
- VI remains ~60 Hz.
- raw swap originates from guest QueueBuffer input.
- raw-3 -> effective-2 HWC A/B worked but did not create upstream frames.
- DFPS ON and OFF can both remain ~20-FPS class.
- cadence/raw swap are symptoms, not the root ~45-55 ms production-time cause.

### BufferQueue / Dequeue

Slow gameplay:

- Queue -> next Dequeue entry ~0.16 ms.
- Dequeue total ~0.05 ms.
- free-slot wait ~0.001 ms.
- Dequeue END -> next Queue owns nearly the entire slow interval.

Conclusion — CLOSED:

> BufferQueue free-slot backpressure is not the primary owner.

## Frame Build Attribution — completed

Build:

- run `33115424368`
- job `98668715842`
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact id `9665216124`
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`

Runtime:

- slow gameplay ~49 ms/frame class;
- measured Vulkan Draw/Configure/Dispatch/Clear only ~9-12 ms/frame class;
- ~37-39 ms/frame remained outside measured RasterizerVulkan scopes.

## GPU Command Attribution — completed

Build:

- run `33129866149`
- job `98716608240`
- build HEAD `dafee3f7f08832dbd39aedf7f2c2607bf1b6112b`
- artifact id `9670361329`
- SHA-256 `5c0d99f3539dd46e79b8b3002ef48216acbcb7de1282c5078b5fb411dd389758`

Slow gameplay:

- wall ~50-53 ms/frame;
- GPU worker queue `PopWait` ~32-37 ms/frame;
- active ~16-20 ms/frame;
- `ProcessCommands` ~15-17 ms/frame;
- `PushCommand` tiny;
- synchronous caller `blockWait=0`.

Conclusion:

> The async GPU worker is starved waiting for upstream work; command interpretation does not own the missing 30-35 ms.

## GPU Submit Gap Attribution — completed

Build:

- run `33133440904`
- job `98728039155`
- build HEAD `f65f93825979cde816aa41fc148deb042039416a`
- artifact id `9671670627`
- SHA-256 `0ef8e4172d812e4cfda90792f9bb2df0868dd192504cf2d3b11d30dcfbcdb313`

Runtime:

- candidate NVDRV submit-handler gap, `nvhost_gpu` device-submit gap and `PushGPUEntries` gap track at roughly ~26 ms/submit in stable slow gameplay;
- about two main submits per ~52 ms frame;
- NVDRV candidate handler work ~0.05-0.06 ms/frame class;
- `SubmitGPFIFOImpl` ~0.01-0.02 ms/frame class;
- channel-lock/copy/fence/syncpoint costs tiny.

Correct conclusion:

> Once the candidate NVDRV handler begins, lower NVDRV/GPFIFO submission is fast.

Important correction:

> This pass did not measure generic sync-request send -> NVDRV handler dispatch latency, so it did not prove the whole inter-submit gap happened before the guest issued IPC.

## Guest Submit Thread Attribution — completed

Build:

- run `33139365151`
- job `98746513852`
- build HEAD `9d8f7ea603051db6eb8f9e9e6e1477583b554622`
- artifact id `9673831416`
- SHA-256 `fd19f1995af224f91d092b820e84394b1612b84884925fe9404228e2f4096db4`

Runtime log:

`eden_log(20260828-045417).txt`

Result:

- guest `tid=0x53` owns essentially all candidate GPU submits;
- dominant share ~100%;
- observed priority 30 / core 1;
- saved submit-entry PC overwhelmingly `0x8522f458`;
- slow-gameplay CPU share between candidate handler observations only ~1-2%, representative weighted ~1.4%.

Conclusion:

> The dominant submitter is not CPU-bound between observed candidate handler entries.

## Exact dc95 source review — completed

Read `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`.

Confirmed:

- synchronous `SendSyncRequest` queues a request and places the originator KThread in `ThreadWaitReasonForDebugging::IPC` / `BeginWait()`;
- reply wakes it via `EndWait()`;
- Nvidia services run via `RunOnHostCoreProcess("nvservices", Nvidia::LoopProcess)`;
- one Nvidia `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`;
- no additional Nvidia host service workers are started in this path;
- host dummy-thread wait/wakeup uses a host `std::condition_variable`;
- no intentional 20-30 ms timer was found in that wake path.

Still-live structural candidates:

1. guest-side post-reply work/wait before the next candidate sync request;
2. sync-IPC request-to-handler dispatch latency;
3. Windows scheduling/wakeup latency of the `nvservices` host thread;
4. single-thread Nvidia `ServerManager` head-of-line delay;
5. a blocking Nvidia request occupying that event loop.

Known special case only, not runtime proof:

- `nvhost_ctrl::IocCtrlEventWait()` has a repeated-failure fallback using `StallApplication()` + `WaitHost()`.

## Current experiment — NVDRV IPC Dispatch Gap Attribution

Branch:

`exp/x1-nvdrv-ipc-dispatch-gap`

New control:

`X1 Log: NVDRV IPC Dispatch Gap`

Setting:

`x1_nvdrv_ipc_dispatch_gap_log`

Default OFF.

New report:

`[X1-IPCDISPATCH]`

### A — sync-request send boundary

In `SendSyncRequestImpl()` immediately before the existing `session->SendSyncRequest(...)` call:

- record current guest KThread ID + steady-clock timestamp;
- fixed 256-slot atomic table;
- no mutex or per-request log on the generic sync-IPC path.

### B — candidate NVDRV handler entry

For candidate GPU-submit `Ioctl1/Ioctl2`:

- pair the latest A timestamp for `ctx.GetThread()`;
- compute `ipcDispatch = B - A`;
- compute `guestPostReply = A - previous candidate C`.

### C — candidate handler completion / reply-adjacent proxy

A `SCOPE_EXIT` records handler completion after response construction.

Exact `ServerManager::CompleteSyncRequest()` immediately follows service completion with `SendReplyHLE()` on the same host loop, so C is a conservative reply-adjacent boundary.

### 120-frame aggregate

Reports dominant thread plus:

- `guestPostAvg` / total / max;
- `ipcDispatchAvg` / total / max;
- `serviceReplyAvg` / total / max;
- ioctl1/ioctl2 counts;
- missing-pair counters;
- generic sync-entry count.

Interpretation:

- `guestPostAvg` dominates -> guest-side post-reply wait/work;
- `ipcDispatchAvg` dominates -> host `nvservices` dispatch/wakeup/head-of-line;
- `serviceReplyAvg` dominates -> reopen handler/reply path;
- both material -> attribute separately.

## Prepared files

- `src/core/x1_nvdrv_ipc_dispatch_profiler.h`
- `tools/adreno_lab/transplant_dc95_nvdrv_ipc_dispatch_gap.py`
- `tools/adreno_lab/analyze_x1_nvdrv_ipc_dispatch_gap.py`
- `.github/workflows/build-dc95-x1-nvdrv-ipc-dispatch-gap.yml`
- `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`
- `DEBUG_HISTORY_20260828_IPC_DISPATCH.md`

## Safety

The new pass is observation-only.

Allowed generated-source modifications are limited to:

- settings/UI;
- `svc_ipc.cpp` A timestamp hook;
- `nvdrv_interface.cpp` B/C hooks;
- rasterizer initialization/report hook;
- the new profiler header.

Workflow hashes and requires unchanged:

- KClient/KServer session behavior;
- KThread / KScheduler / GlobalSchedulerContext;
- `services.cpp`, `server_manager.cpp`, `multi_wait.cpp`;
- nvhost GPU/ctrl;
- BufferQueue/HWC/VI;
- GPU worker / DmaPusher;
- Vulkan swapchain/scheduler/graphics pipeline;
- prior GPU command / GPU submit / guest submit profiler headers.

No server-worker, wait/scheduler, GPU submission, frame pacing, swap, buffer-count, priority/core or speed behavior may be changed.

## Recommended runtime after a future successful build

Use same TOTK 1.2.1 route, DFPS OFF first.

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

## NEXT ACTION

Read `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`.

Static preparation is complete. Verify current branch HEAD, workflow `workflow_dispatch`-only state and Actions count before any future build.

## Build authorization state

- Frame Build: 1 successful attempt, no rerun
- GPU Command: 1 successful attempt, no rerun
- GPU Submit Gap: 1 successful attempt, no rerun
- Guest Submit Thread: 1 successful attempt, no rerun
- NVDRV IPC Dispatch Gap: 0 attempts, 0 reruns
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
