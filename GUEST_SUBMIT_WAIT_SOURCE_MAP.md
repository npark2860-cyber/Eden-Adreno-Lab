# Guest GPU Submit Wait — exact dc95 source map

Updated: 2026-08-28 KST

## Fixed source

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Runtime target: TOTK 1.2.1 / Windows ARM64 / Adreno X1-85

This document records only what exact dc95 source plus the completed runtime attribution supports.

## Runtime boundary already established

The completed guest-submit-thread run showed:

- one guest thread, `tid=0x53`, owns essentially all candidate GPU-submit ioctls;
- saved submit-entry PC is overwhelmingly `0x8522f458`;
- priority 30, core 1 in the observed slow gameplay;
- slow-gameplay submitter `cpuShare` is only about 1-2% (weighted representative value about 1.4%);
- GPU worker is simultaneously idle for roughly 30-35 ms/frame waiting for upstream command supply;
- NVDRV GPU-submit handler body / `SubmitGPFIFOImpl` / `PushGPUEntries` are individually tiny compared with the inter-submit gap.

Therefore the submitter is not CPU-bound between observed NVDRV handler entries.

## Exact synchronous IPC path

`Svc::SendSyncRequest()`

-> `KClientSession::SendSyncRequest()`

-> `KSession::OnRequest()`

-> `KServerSession::OnRequest()`

For a synchronous request, `KServerSession::OnRequest()`:

1. queues the `KSessionRequest`,
2. marks the current guest thread wait reason as `ThreadWaitReasonForDebugging::IPC`,
3. calls `BeginWait()`.

The guest thread is resumed only when the server reply path calls `EndWait()`.

Therefore a low `KThread::GetCpuTime()` delta across consecutive NVDRV handler observations is structurally expected if much of the interval is spent waiting for HLE service processing/reply.

## Exact wait-reason classes already implemented by dc95

`KThread` exposes these debugging wait reasons:

- `None`
- `Sleep`
- `IPC`
- `Synchronization`
- `ConditionVar`
- `Arbitration`
- `Suspended`

Relevant exact paths:

- `Sleep`: positive `Svc::SleepThread()` -> `KThread::Sleep()` -> `BeginWait()`.
- `IPC`: synchronous `KServerSession::OnRequest()` -> `BeginWait()`.
- `Synchronization`: `Svc::WaitSynchronization()` -> `KSynchronizationObject::Wait()` -> `BeginWait()`.
- `ConditionVar`: `KConditionVariable::WaitForAddress()` / `Wait()` -> `BeginWait()`.
- `Arbitration`: `KAddressArbiter::WaitIfLessThan()` / `WaitIfEqual()` -> `BeginWait()`.

Source alone does not identify which one `tid=0x53` occupies during the full interval; runtime attribution is still required for that.

## Critical host-service architecture finding

`Services::Services()` launches Nvidia services as:

`kernel.RunOnHostCoreProcess("nvservices", Nvidia::LoopProcess).detach()`

This differs from the large set of services launched through `RunOnGuestCoreProcess()`.

`Nvidia::LoopProcess()` creates ONE `ServerManager` and registers all of:

- `nvdrv`
- `nvdrv:a`
- `nvdrv:s`
- `nvdrv:t`
- `nvmemp`

Then it calls `ServerManager::RunServer()`.

There is no `StartAdditionalHostThreads()` call in this Nvidia loop.

Therefore these Nvidia service sessions are serviced by a single host-service event loop unless another path explicitly adds workers.

## ServerManager behavior

`ServerManager::LoopProcessImpl()` repeatedly:

1. `WaitSignaled()`
2. selects one signaled holder,
3. `Process(holder)`
4. for a session, `ReceiveRequestHLE()`
5. `CompleteSyncRequest()`
6. invokes the service handler
7. sends the HLE reply
8. relinks the session for future requests.

`MultiWait::WaitAny()` itself uses `KSynchronizationObject::Wait()`.

Because `nvservices` is a host-core process, its KThread is a dummy host KThread. Exact dc95 implements dummy-thread waiting with a host `std::condition_variable`:

- waiting dummy thread -> `RequestDummyThreadWait()` / `DummyThreadBeginWait()`;
- signal path -> scheduler registers dummy for wakeup;
- scheduler unlock path -> `DummyThreadEndWait()` -> condition-variable notify.

No deliberate 20-30 ms sleep/timer is present in this wake path.

## Important correction to the previous interpretation

Previous GPU-submit-gap instrumentation measured the body of the NVDRV candidate submit handler and the lower `nvhost_gpu` / `SubmitGPFIFOImpl` work.

It did NOT measure the complete interval from:

`guest enters SendSyncRequest`

to

`nvservices host thread reaches NVDRV::Ioctl1/Ioctl2 handler`.

Therefore this statement is too strong and must not be used anymore:

> "The entire ~25-30 ms gap is proven to occur before the guest issues the NVDRV submit IPC."

What is actually proven is:

> Once the NVDRV submit handler begins, its body and lower GPFIFO submission path are very fast.

The still-unmeasured interval may be split between:

1. guest-side work/wait after the previous NVDRV reply and before the next `SendSyncRequest`, and/or
2. IPC request-to-handler dispatch latency after `SendSyncRequest` has already put `tid=0x53` to sleep.

## Single-thread head-of-line / host scheduling candidate

Because all Nvidia service sessions share one host `ServerManager` loop, the following remain live candidates:

- the `nvservices` Windows host thread is not scheduled promptly after being signaled;
- another Nvidia service/session request occupies the single event loop before the GPU-submit request is serviced;
- a rare blocking Nvidia ioctl causes head-of-line delay.

This is a structural possibility, not yet runtime proof.

### Known blocking special case

`nvhost_ctrl::IocCtrlEventWait()` is normally implemented as event registration / timeout return and is not inherently a long blocking call.

However, after repeated failures (`fails > 2`), exact dc95 has a fallback that does:

- `system.StallApplication()`
- `host1x_syncpoint_manager.WaitHost(...)`
- `system.UnstallApplication()`

That fallback can block, but source alone does not show that it is occurring in the measured gameplay. Do not promote it to root cause without runtime evidence.

## Decisive next split

Do NOT start with a broad all-thread scheduler profiler.

For the dominant submitter, measure exactly four boundaries:

- `A`: guest `Svc::SendSyncRequest` entry for the request that becomes the NVDRV GPU-submit ioctl;
- `B`: NVDRV `Ioctl1/Ioctl2` handler entry;
- `C`: NVDRV handler/reply completion;
- `A_next`: next matching `SendSyncRequest` entry from the same guest thread.

Then split the inter-submit interval into:

### C -> A_next

Guest-side post-reply interval.

If this owns ~25-30 ms, the game/SDK thread is waiting or coordinating elsewhere before issuing the next NVDRV request.

### A -> B

HLE IPC dispatch interval.

If this owns ~25-30 ms, the guest already issued the request and is sleeping in IPC while the single host `nvservices` loop is late servicing it.

Primary suspects then become host-thread scheduling/wakeup and single-thread Nvidia-service head-of-line delay.

### B -> C

Service body/reply interval.

Existing evidence predicts this remains tiny.

## Pairing safety

A synchronous guest KThread cannot issue another synchronous request while it is blocked waiting for the current reply. Therefore a per-`KThread` timestamp captured at `SendSyncRequest` entry can be paired with the subsequent NVDRV handler context for that same originator thread without needing a general request profiler.

## Current causal status

Closed as primary owner:

- BufferQueue free-slot wait
- HWC swap-interval gate
- DFPS/raw-swap cause
- Vulkan Draw/Configure alone
- GPU worker command interpretation alone
- lower NVDRV `nvhost_gpu` GPFIFO preparation
- `SubmitGPFIFOImpl`

Still live:

1. guest post-reply synchronization/work before next NVDRV IPC;
2. HLE sync-IPC dispatch latency;
3. Windows scheduling/wakeup latency of the detached `nvservices` host thread;
4. single-thread Nvidia-service head-of-line blocking.

The next experiment must distinguish (1) from (2-4) before deeper wait-reason or Dynarmic work.
