# DEBUG HISTORY — 2026-08-28 Guest Submit Boundary

## GPU Submit Gap build

Successful authorized build:

- workflow: `Build dc95 X1 GPU Submit Gap Attribution`
- run: `33133440904`
- job: `98728039155`
- attempt: 1
- build HEAD: `f65f93825979cde816aa41fc148deb042039416a`
- artifact: `Eden-dc95-X1-gpu-submit-gap-attribution`
- artifact id: `9671670627`
- size: 31,331,056 bytes
- SHA-256: `0ef8e4172d812e4cfda90792f9bb2df0868dd192504cf2d3b11d30dcfbcdb313`
- successful, no rerun
- one-shot trigger restored to manual-only and marker removed
- cleanup HEAD: `d17eb7314b2809c95e53874dbc7f64808df67006`

## GPU-submit-gap runtime

Log:

`eden_log(20260828-030445).txt`

Basis:

- exact Eden dc95
- TOTK 1.2.1
- Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- GPU Submit Gap Attribution ON
- GPU Command Attribution ON
- Frame Build Attribution ON
- Dequeue Attribution ON
- Frame Cadence ON
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- note: swap 3->2 clamp and Descriptor Ring were still ON accidentally

### Result

In stable slow gameplay, the following three inter-submit gaps tracked each other essentially exactly:

1. candidate NVDRV GPU-submit handler-entry gap,
2. confirmed `nvhost_gpu` device-submit-entry gap,
3. actual `PushGPUEntries` call gap.

Representative stable windows were roughly ~26 ms per submit interval with about two main submits per ~52 ms frame.

At the same time:

- NVDRV handler work was only ~0.05-0.06 ms/frame class,
- `SubmitGPFIFOImpl` ~0.01-0.02 ms/frame class,
- channel-lock wait effectively zero,
- command-header copy/read cost tiny,
- fence/syncpoint/push call overhead tiny.

This proved that once the NVDRV GPU-submit handler begins, the lower submission machinery is not the missing-time owner.

At the time, the working interpretation was that the entire long gap existed before the guest issued the next NVDRV submit request. Later exact-source analysis below refines that interpretation because the request-to-handler IPC dispatch interval had not yet been measured.

---

## Guest Submit Thread Attribution build

Successful authorized build:

- workflow: `Build dc95 X1 Guest Submit Thread Attribution`
- run: `33139365151`
- job: `98746513852`
- attempt: 1
- build HEAD: `9d8f7ea603051db6eb8f9e9e6e1477583b554622`
- artifact: `Eden-dc95-X1-guest-submit-thread-attribution`
- artifact id: `9673831416`
- size: 31,341,758 bytes
- SHA-256: `fd19f1995af224f91d092b820e84394b1612b84884925fe9404228e2f4096db4`
- successful, no rerun
- one-shot trigger removed
- cleanup HEAD before documentation updates: `352867995e8c1623bfe2274f2125ffb4e10e4e2e`

## Guest-submit-thread runtime

Log:

`eden_log(20260828-045417).txt`

Basis:

- exact Eden dc95
- TOTK 1.2.1
- Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- Guest Submit Thread Attribution ON
- GPU Submit Gap Attribution ON
- GPU Command Attribution ON
- Frame Build Attribution ON
- Dequeue Attribution ON
- Frame Cadence ON
- swap 3->2 clamp OFF
- Descriptor Ring remained ON

### Runtime result

One guest thread owns essentially all candidate GPU-submit ioctls:

- dominant thread: `tid=0x53`
- dominant share: ~100%
- priority: 30
- observed core: 1
- saved submit-entry PC: overwhelmingly `0x8522f458`

In slow gameplay, the submitter CPU-share between consecutive observed NVDRV handler entries is only about 1-2%.

Representative values include:

- frame 1200 class: ~1.48%
- frame 1560 class: ~1.12%
- weighted representative slow value: ~1.4%

Conclusion:

> The dominant GPU submitter is not CPU-bound between the observed NVDRV submit-handler entries. It spends the overwhelming majority of that wall interval not executing guest CPU instructions.

This result does NOT mean the whole game CPU is idle, and it does NOT by itself identify which wait primitive owns the interval.

---

## Exact dc95 static wait-path review

The user correctly challenged that the source should be inspected before adding another broad profiler.

### Synchronous IPC

Exact path:

`Svc::SendSyncRequest`

-> `KClientSession::SendSyncRequest`

-> `KSession::OnRequest`

-> `KServerSession::OnRequest`

For a synchronous request, `KServerSession::OnRequest()`:

- queues the request,
- sets `ThreadWaitReasonForDebugging::IPC`,
- calls `BeginWait()` on the originator guest thread.

The reply path wakes it with `EndWait()`.

Therefore low submitter CPU share is structurally consistent with the thread sleeping in synchronous IPC for some portion of the interval.

### Other exact wait reasons

Exact dc95 provides:

- `Sleep`
- `IPC`
- `Synchronization`
- `ConditionVar`
- `Arbitration`
- `Suspended`

Relevant wait implementations were verified in:

- `KThread::Sleep`
- `KSynchronizationObject::Wait`
- `KConditionVariable::WaitForAddress` / `Wait`
- `KAddressArbiter::WaitIfLessThan` / `WaitIfEqual`

### Critical Nvidia HLE architecture finding

`Services::Services()` launches Nvidia through:

`kernel.RunOnHostCoreProcess("nvservices", Nvidia::LoopProcess).detach()`

This is a host-core service process, not a normal guest-core service process.

`Nvidia::LoopProcess()` creates one `ServerManager` and registers:

- `nvdrv`
- `nvdrv:a`
- `nvdrv:s`
- `nvdrv:t`
- `nvmemp`

No Nvidia `StartAdditionalHostThreads()` call exists in this path.

Therefore one host service event loop serially services the Nvidia sessions.

`ServerManager::WaitAny()` uses `KSynchronizationObject::Wait()`.
The host service uses a dummy KThread, and exact dc95 blocks/wakes dummy host threads with a host `std::condition_variable` through:

- `RequestDummyThreadWait()` / `DummyThreadBeginWait()`
- scheduler dummy wake registration
- `DummyThreadEndWait()`

No deliberate 20-30 ms sleep/timer was found in this wake path.

### Important correction

The previous GPU-submit-gap profiler begins at or inside the NVDRV candidate handler. It does not measure:

`guest SendSyncRequest entry -> nvservices handler entry`.

Therefore this previous wording is too strong:

> the whole ~25-30 ms gap is proven to happen before the guest issues the NVDRV ioctl.

Correct boundary:

> Once the NVDRV submit handler begins, the handler body and lower GPFIFO submission path are fast. The still-unmeasured interval may be before the guest issues the sync IPC, or after it issues the sync IPC but before the single host `nvservices` loop services it.

### Single-thread host-service candidates still alive

- Windows host scheduling/wakeup latency of the detached `nvservices` thread;
- head-of-line delay from another Nvidia request/session in the single ServerManager loop;
- a blocking Nvidia ioctl occupying that loop.

`nvhost_ctrl::IocCtrlEventWait()` is normally event-registration/nonblocking-style, but exact dc95 has a repeated-failure fallback (`fails > 2`) that performs `StallApplication()` + `WaitHost()` + `UnstallApplication()`. Source alone does not prove that fallback occurs in the measured route.

---

## New decisive boundary

Before any broad wait profiler, split one dominant submit cycle into:

- `A`: guest `Svc::SendSyncRequest` entry,
- `B`: NVDRV `Ioctl1/Ioctl2` candidate-submit handler entry,
- `C`: NVDRV handler/reply completion,
- `A_next`: next sync-request entry from the same guest KThread.

Interpret:

- `C_prev -> A_next` dominant => guest-side post-reply wait/work is the owner.
- `A -> B` dominant => guest already issued the request; host `nvservices` dispatch/wakeup/head-of-line latency is the owner.
- `B -> C` is expected to stay tiny from existing evidence.

A synchronous KThread cannot issue another sync IPC before the current reply, so per-KThread timestamp pairing is sufficient and does not require a general request tracer.

See:

- `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`
- `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`

## Current build authorization

None.

No ARM64 build/re-run without fresh explicit user authorization; one authorization equals exactly one attempt.
