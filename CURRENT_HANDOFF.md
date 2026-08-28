# CURRENT HANDOFF — Eden Adreno X1 Guest Submit / NVDRV IPC Dispatch Boundary

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-guest-submit-thread-attribution`
- predecessor cleanup HEAD: `exp/x1-gpu-submit-gap-attribution@d17eb7314b2809c95e53874dbc7f64808df67006`

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
- do not implement simple alias-copy dedupe or suppress required outside-RP copy work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse.
- gameplay fast selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`.
- classic cached Uniform path is mostly clean.
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint.
- classified same-frame repeats: 99.17% same fingerprint.
- wholesale classic-cache fallback A/B did not break the gameplay ceiling.
- do not blindly reuse prior staging allocations or enable persistent Uniform bindings.

### Frame cadence / swap / DFPS

- raw main QueueBuffer `swap=2` can express nominal ~30-FPS opportunities.
- raw `swap=3` can express nominal ~20-FPS opportunities.
- VI remains ~60 Hz.
- raw swap originates in guest QueueBuffer input, not Qualcomm Vulkan Present/Mailbox/Target_60.
- raw-3 -> effective-2 HardwareComposer A/B executed correctly but did not create upstream frames.
- DFPS ON and OFF can both remain ~20-FPS class under different raw swap values.
- raw swap / HWC cadence is a symptom/expression, not the root ~45-55 ms production-time cause.

### BufferQueue / Dequeue

Slow gameplay:

- Queue -> next Dequeue entry ~0.16 ms.
- Dequeue total ~0.05 ms.
- free-slot wait ~0.001 ms.
- Dequeue END -> next Queue owns nearly the whole slow interval.

Conclusion — CLOSED:

> Slow gameplay is not waiting for a free BufferQueue slot.

## Frame-Build Attribution — completed

Successful build:

- workflow `Build dc95 X1 Frame Build Attribution`
- run `33115424368`
- job `98668715842`
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact id `9665216124`
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`

Runtime conclusion:

- slow gameplay ~49 ms/frame class;
- measured Vulkan Draw/Configure work is only ~9-11 ms/frame class depending on DFPS/workload;
- ~37-39 ms/frame remained outside measured RasterizerVulkan scopes;
- `FillImageViews` and Draw count alone do not own the ceiling.

## GPU Command Attribution — completed

Successful build:

- workflow `Build dc95 X1 GPU Command Attribution`
- run `33129866149`
- job `98716608240`
- build HEAD `dafee3f7f08832dbd39aedf7f2c2607bf1b6112b`
- artifact id `9670361329`
- SHA-256 `5c0d99f3539dd46e79b8b3002ef48216acbcb7de1282c5078b5fb411dd389758`

Slow gameplay:

- ~50-53 ms/frame wall;
- GPU worker queue `PopWait` ~32-37 ms/frame;
- GPU worker active ~16-20 ms/frame;
- `ProcessCommands` ~15-17 ms/frame;
- `PushCommand` tiny;
- synchronous caller `blockWait=0`.

Conclusion — STRONGLY SUPPORTED:

> The async GPU worker is starved waiting for upstream command supply. DmaPusher/command interpretation is not the missing ~30-35 ms owner.

## GPU Submit Gap Attribution — completed

Successful build:

- workflow `Build dc95 X1 GPU Submit Gap Attribution`
- run `33133440904`
- job `98728039155`
- build HEAD `f65f93825979cde816aa41fc148deb042039416a`
- artifact id `9671670627`
- SHA-256 `0ef8e4172d812e4cfda90792f9bb2df0868dd192504cf2d3b11d30dcfbcdb313`

Runtime:

- candidate NVDRV submit-handler gap, `nvhost_gpu` device-submit gap and `PushGPUEntries` gap track each other at roughly ~26 ms/submit in stable slow gameplay;
- about two main submits per ~52 ms frame;
- NVDRV candidate handler work ~0.05-0.06 ms/frame class;
- `SubmitGPFIFOImpl` ~0.01-0.02 ms/frame class;
- channel-lock/copy/fence/syncpoint costs tiny.

Confirmed boundary:

> Once the NVDRV GPU-submit handler begins, the lower NVDRV/GPFIFO submission machinery is fast.

Important correction after exact-source review:

> This profiler did **not** measure `guest SendSyncRequest entry -> NVDRV handler entry`, so it did not prove the whole inter-submit gap occurs before the guest issues the IPC.

## Guest Submit Thread Attribution — completed

Successful build:

- workflow `Build dc95 X1 Guest Submit Thread Attribution`
- run `33139365151`
- job `98746513852`
- attempt 1
- build HEAD `9d8f7ea603051db6eb8f9e9e6e1477583b554622`
- artifact `Eden-dc95-X1-guest-submit-thread-attribution`
- artifact id `9673831416`
- size 31,341,758 bytes
- SHA-256 `fd19f1995af224f91d092b820e84394b1612b84884925fe9404228e2f4096db4`
- success, no rerun
- one-shot trigger removed
- cleanup HEAD before documentation updates: `352867995e8c1623bfe2274f2125ffb4e10e4e2e`

Runtime log:

`eden_log(20260828-045417).txt`

Clean important settings:

- Guest Submit Thread Attribution ON
- GPU Submit Gap ON
- GPU Command ON
- Frame Build ON
- Cadence ON
- Dequeue ON
- swap 3->2 clamp OFF
- Descriptor Ring remained ON

Runtime result:

- one guest thread `tid=0x53` owns essentially all candidate GPU-submit ioctls;
- dominant share ~100%;
- priority 30;
- observed core 1;
- saved submit-entry PC overwhelmingly `0x8522f458`;
- slow-gameplay submitter `cpuShare` only ~1-2%; representative weighted value ~1.4%; frame-1560 class ~1.12%.

Conclusion — STRONGLY SUPPORTED:

> The dominant GPU submitter is not CPU-bound between the observed NVDRV submit-handler entries. It spends most of that wall interval not executing guest CPU instructions.

Do not over-interpret this as the whole game CPU being idle.

## Exact dc95 source review — new critical boundary

See `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`.

### Synchronous IPC behavior

Exact path:

`Svc::SendSyncRequest`

-> `KClientSession::SendSyncRequest`

-> `KSession::OnRequest`

-> `KServerSession::OnRequest`

For sync IPC, `KServerSession::OnRequest()` queues the request, sets `ThreadWaitReasonForDebugging::IPC`, and calls `BeginWait()` on the originator guest KThread. The reply path wakes it via `EndWait()`.

Exact dc95 wait-reason classes include:

- Sleep
- IPC
- Synchronization
- ConditionVar
- Arbitration
- Suspended

### Nvidia HLE service architecture

`Services::Services()` launches Nvidia as:

`kernel.RunOnHostCoreProcess("nvservices", Nvidia::LoopProcess).detach()`

This is a host-core service process.

`Nvidia::LoopProcess()` creates one `ServerManager` and registers all of:

- `nvdrv`
- `nvdrv:a`
- `nvdrv:s`
- `nvdrv:t`
- `nvmemp`

No additional Nvidia host service workers are started in this path.

`ServerManager` handles one selected session event at a time. `MultiWait::WaitAny()` uses `KSynchronizationObject::Wait()`.

The host service uses a dummy KThread. Exact dc95 dummy wait/wakeup is implemented with a host `std::condition_variable` (`RequestDummyThreadWait` / `DummyThreadBeginWait` / `DummyThreadEndWait`). No intentional 20-30 ms timer was found in this wake path.

### Still-live structural candidates

Because the NVDRV handler-body profiler begins too late to include IPC dispatch latency, the missing interval may be either:

1. guest-side work/wait after the previous NVDRV reply and before the next `SendSyncRequest`, or
2. after the guest already issues `SendSyncRequest`, while `tid=0x53` sleeps in IPC waiting for the single host `nvservices` loop to service it.

If (2), live suspects include:

- Windows host scheduling/wakeup latency of `nvservices`;
- head-of-line delay from another Nvidia session/request in the single ServerManager loop;
- a blocking Nvidia ioctl occupying the loop.

Known exact special case:

`nvhost_ctrl::IocCtrlEventWait()` normally registers an event / returns timeout, but after repeated failures (`fails > 2`) has a fallback using `StallApplication()` + `WaitHost()` + `UnstallApplication()`. Source alone does not prove this fallback occurs in the measured gameplay.

## NEXT ACTION — decisive IPC dispatch split

Read:

- `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`
- `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`

Do **not** start with a broad all-thread wait profiler.

The next measurement should split one dominant submit cycle into:

- `A`: guest `Svc::SendSyncRequest` entry,
- `B`: NVDRV candidate `Ioctl1/Ioctl2` handler entry,
- `C`: handler/reply completion,
- `A_next`: next matching sync-request entry from the same guest KThread.

Interpretation:

- `C_prev -> A_next` dominant => guest post-reply wait/work owns the gap;
- `A -> B` dominant => guest already issued request; host `nvservices` dispatch/wakeup/head-of-line owns the gap;
- `B -> C` expected tiny from existing measurements.

A synchronous KThread cannot issue a second sync IPC before the first reply, so a per-KThread timestamp is sufficient for pairing; no general all-request tracer is necessary.

## What NOT to do

- no ARM64 Actions without fresh explicit permission;
- no automatic rerun;
- no scheduling/priority/core-mask changes;
- no `nvservices` multithreading experiment before attribution;
- no raw QueueBuffer modification;
- no VSync/Mailbox/Target_60/speed-limit changes;
- no buffer-count modification;
- no simple alias dedupe;
- no blind persistent Uniform binding or staging reuse.

## Build authorization state

- Frame Build: 1 successful attempt, no rerun
- GPU Command: 1 successful attempt, no rerun
- GPU Submit Gap: 1 successful attempt, no rerun
- Guest Submit Thread: 1 successful attempt, no rerun
- current ARM64 build authorization: **none**
- next IPC-dispatch instrumentation build attempts: 0
- gameplay optimization promoted: none
