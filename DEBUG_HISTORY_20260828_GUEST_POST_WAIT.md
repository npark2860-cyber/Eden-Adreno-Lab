# DEBUG HISTORY — 2026-08-28 Guest Post Wait Boundary

## Completed predecessor: NVDRV IPC Dispatch Gap

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Build:

- workflow `Build dc95 X1 NVDRV IPC Dispatch Gap`
- run `33145255519`
- job `98764725334`
- attempt 1
- build HEAD `4edb96cc33c3393df34cbe048600f0fb6b669d61`
- conclusion SUCCESS
- artifact ID `9676070821`
- artifact name `Eden-dc95-X1-nvdrv-ipc-dispatch-gap`
- artifact size `31,346,027` bytes
- SHA-256 `26d68afae986d8e526b110d8e19826d642d9accda23e68c47d4b8fe13fa93184`

Runtime log:

`eden_log(20260828-061910).txt`

Environment:

- TOTK 1.2.1
- Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- swap 3 -> 2 clamp OFF
- NVDRV IPC Dispatch / Guest Submit / GPU Submit / GPU Command / Frame Build / Cadence / Dequeue ON
- Descriptor Ring remained ON, but reported zero alloc/reuse-wait activity in sampled reports.

## Runtime result

Representative `[X1-IPCDISPATCH]` reports:

### frame 840

- tid `0x53`
- 240 / 240 candidate requests
- `guestPostAvg = 16.840 ms`
- `ipcDispatchAvg = 0.021 ms`
- `serviceReplyAvg = 0.014 ms`
- `missingA=0`, `missingB=0`
- corresponding submitter CPU share `1.45%`

### frame 1320

- tid `0x53`
- 244 / 244 candidate requests
- `guestPostAvg = 26.743 ms`
- `ipcDispatchAvg = 0.017 ms`
- `serviceReplyAvg = 0.039 ms`
- `missingA=0`, `missingB=0`
- corresponding submitter CPU share `1.64%`

### frame 1440

- tid `0x53`
- 242 / 242 candidate requests
- `guestPostAvg = 29.091 ms`
- `ipcDispatchAvg = 0.027 ms`
- `serviceReplyAvg = 0.033 ms`
- `missingA=0`, `missingB=0`
- corresponding submitter CPU share `1.38%`

In this runtime the saved candidate-entry PC was `0x8500f458`; do not silently substitute the `0x8522f458` value seen in the earlier Guest Submit runtime.

## Closed conclusion

The missing 20-30 ms is **not** request-to-`nvservices` handler dispatch latency.

The host-side candidates below are closed as primary owner for this matched runtime:

- Windows wake/scheduling latency of the `nvservices` host thread;
- Nvidia `ServerManager` head-of-line delay before this candidate request;
- lower candidate NVDRV handler/reply processing.

The dominant interval is:

> previous candidate handler completion / reply-adjacent C -> next candidate sync-request send boundary A.

That guest-side interval grows from ~16.8 ms/request in the lighter state to ~26.7-29.1 ms/request in slow gameplay.

`tid=0x53` still owns essentially all candidate GPU submits while consuming only ~1-2% observed guest CPU ticks, so plain CPU-bound execution by the submitter remains unlikely.

## Exact dc95 source review for the next split

`KThread` exposes debugging wait reasons:

- None
- Sleep
- IPC
- Synchronization
- ConditionVar
- Arbitration
- Suspended

`KThread::BeginWait()` drives the base state to Waiting.

`KThreadQueue::EndWait()` / `CancelWait()` drive the base state back to Runnable.

The common `KThread::SetState()` clears the debugging wait reason before applying the new base state. Therefore an observation hook can capture the old reason before the existing clear on Waiting -> Runnable without changing wait behavior.

## New static experiment

Branch:

`exp/x1-guest-post-wait-attribution`

New control:

`X1 Log: Guest Post Wait Attribution`

New aggregate:

`[X1-GUESTWAIT]`

Design:

- candidate handler completion C opens the target window;
- immediate candidate reply wake is excluded;
- common KThread state transitions for the dynamic candidate submitter are timed;
- completed waits are attributed by reason and by current SVC ID captured on wait entry;
- next candidate handler entry closes the window;
- completed IPC-dispatch data proves the B-vs-A endpoint error is only ~0.02 ms/request;
- residual window time after subtracting completed waits remains explicit.

No per-wait line logging is added.

Interpretation:

- high waitShare -> follow dominant wait reason/SVC;
- low waitShare + persistent ~1-2% submitter CPU share -> move to Runnable residency / scheduler competitor attribution;
- mixed -> preserve both components and instrument only the dominant remainder.

## Build state

No ARM64 build for the new Guest Post Wait pass has been run.

Current ARM64 build authorization: **none**.
