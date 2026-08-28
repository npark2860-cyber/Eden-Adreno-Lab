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

## Runtime

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

## Key result

In stable slow gameplay, the following three inter-submit gaps track each other essentially exactly:

1. candidate NVDRV GPU-submit service entry gap,
2. confirmed `nvhost_gpu` device-submit entry gap,
3. actual `PushGPUEntries` call gap.

Representative stable windows are roughly ~26 ms per submit interval with about two main submits per ~52 ms frame.

At the same time:

- NVDRV service work is only ~0.05-0.06 ms/frame class,
- `SubmitGPFIFOImpl` is ~0.01-0.02 ms/frame class,
- channel-lock wait is effectively zero,
- command-header copy/read cost is tiny,
- fence/syncpoint/push call overhead is tiny.

Therefore the long gap is already present before `NVDRV::Ioctl1/Ioctl2` begins useful work.

## Causal conclusion

CLOSED / strongly supported:

> NVDRV IPC handling, `nvhost_gpu` GPFIFO preparation and `SubmitGPFIFOImpl` are not the owner of the ~25-30 ms inter-submit gap. The guest/upstream side simply does not issue the next GPU-submit ioctl for that interval.

This corroborates the previous GPU-command result:

> The asynchronous GPU worker is starved because upstream command production arrives late; the GPU worker and NVDRV submission machinery are not sitting on already-produced work.

## New causal boundary

Current target moves above NVDRV to the request-originating guest thread.

Exact dc95 provides the needed observation point without immediately modifying the scheduler:

- `HLERequestContext::GetThread()` returns the originator `KThread`.
- `KThread::GetCpuTime()` is updated by `KScheduler` using the same `CoreTiming().GetClockTicks()` time base used by guest timing.
- thread ID, core, priority and saved PC are directly readable.

This enables a low-intrusion next split:

- high submitter CPU-tick share between requests => guest submit producer is CPU-bound,
- low CPU-tick share => submitter is mostly waiting/preempted and targeted kernel wait attribution is needed.

## Next branch

`exp/x1-guest-submit-thread-attribution`

See:

`NEXT_ACTION_GUEST_SUBMIT_THREAD_ATTRIBUTION.md`

No ARM64 build authorization exists at the time of this entry.
