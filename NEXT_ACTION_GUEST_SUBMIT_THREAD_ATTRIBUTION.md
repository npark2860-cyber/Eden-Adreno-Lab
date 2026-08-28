# NEXT ACTION — X1 Guest Submit Thread Attribution — COMPLETED

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Lab branch: `exp/x1-guest-submit-thread-attribution`

Do not change the Eden baseline.

**ARM64 Actions rule: no build or rerun without fresh explicit user authorization. One authorization = exactly one attempt.**

## Build — completed

- workflow: `Build dc95 X1 Guest Submit Thread Attribution`
- run: `33139365151`
- job: `98746513852`
- attempt: 1
- build HEAD: `9d8f7ea603051db6eb8f9e9e6e1477583b554622`
- artifact: `Eden-dc95-X1-guest-submit-thread-attribution`
- artifact id: `9673831416`
- size: 31,341,758 bytes
- SHA-256: `fd19f1995af224f91d092b820e84394b1612b84884925fe9404228e2f4096db4`
- result: success
- reruns: 0
- one-shot trigger removed

## Runtime — completed

Log:

`eden_log(20260828-045417).txt`

Key clean setting:

- `x1_ab_clamp_main_swap_interval_3_to_2=false`

Descriptor Ring remained ON, but the decisive guest-thread attribution is unaffected.

### Result

- one guest KThread `tid=0x53` owns essentially all candidate GPU-submit ioctls;
- dominant share ~100%;
- priority 30;
- observed core 1;
- saved submit-entry PC overwhelmingly `0x8522f458`;
- slow-gameplay `cpuShare` only ~1-2%, representative weighted value ~1.4%.

Conclusion:

> The dominant GPU submitter is not CPU-bound between observed NVDRV handler entries. Most of the wall interval is spent not executing guest CPU instructions.

## Exact-source refinement

Subsequent exact dc95 source review found that this result must be interpreted together with the synchronous HLE IPC architecture.

For synchronous IPC:

- `KServerSession::OnRequest()` sets the originator KThread wait reason to `IPC` and calls `BeginWait()`;
- reply wakes it through `EndWait()`.

Nvidia HLE services are launched as a detached host-core process:

`RunOnHostCoreProcess("nvservices", Nvidia::LoopProcess)`

One Nvidia `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`; no additional Nvidia host service workers are started in that path.

Therefore the previous NVDRV handler-body timing does not distinguish:

1. guest waits/works a long time before issuing the next sync IPC, from
2. guest issues the sync IPC promptly and then sleeps while the host `nvservices` loop is late dispatching it.

See:

- `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`
- `DEBUG_HISTORY_20260828_GUEST_SUBMIT.md`

## Superseded next action

Do not add a broad wait-reason profiler yet.

The decisive next experiment is now:

`NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`

It must split:

- previous NVDRV reply -> next `Svc::SendSyncRequest` entry,
- `SendSyncRequest` entry -> NVDRV handler entry,
- handler entry -> reply completion.

This tells us whether the missing interval belongs to guest-side post-reply coordination or to host `nvservices` dispatch/wakeup/head-of-line latency.

## Current build state

Guest-submit-thread experiment: completed successfully.

Next IPC-dispatch experiment: not built.

Current ARM64 build authorization: **none**.
