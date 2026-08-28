# CURRENT HANDOFF — Eden Adreno X1 Guest Post Wait Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-guest-post-wait-attribution`
- predecessor completed branch HEAD: `exp/x1-nvdrv-ipc-dispatch-gap@491f911a6e7e13a9d43902edcc99a129ca08f893`

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
- Dequeue total ~0.05-0.07 ms.
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
- lower NVDRV GPFIFO work is tiny once candidate handler begins.

Conclusion:

> Lower NVDRV / GPFIFO submission is not the missing interval once the candidate handler starts.

## Guest Submit Thread Attribution — completed

Build:

- run `33139365151`
- job `98746513852`
- build HEAD `9d8f7ea603051db6eb8f9e9e6e1477583b554622`
- artifact id `9673831416`
- SHA-256 `fd19f1995af224f91d092b820e84394b1612b84884925fe9404228e2f4096db4`

Runtime:

- guest `tid=0x53` owns essentially all candidate GPU submits;
- dominant share ~100%;
- priority 30 / core 1;
- slow-gameplay CPU share only ~1-2%, representative weighted ~1.4%.

Important PC note:

- earlier Guest Submit runtime observed `0x8522f458`;
- latest IPC-dispatch runtime observed `0x8500f458`;
- do not conflate these addresses across runs.

Conclusion:

> The dominant submitter is not CPU-bound between candidate submissions.

## Exact dc95 source review — retained

Read `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`.

Confirmed:

- synchronous `SendSyncRequest` sleeps the originator KThread in IPC wait;
- Nvidia services run on detached host `nvservices` processing;
- one Nvidia `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`;
- no additional Nvidia host service workers are started in that path;
- no intentional 20-30 ms wake timer was found.

## NVDRV IPC Dispatch Gap Attribution — completed

Build:

- workflow `Build dc95 X1 NVDRV IPC Dispatch Gap`
- run `33145255519`
- job `98764725334`
- attempt 1
- build HEAD `4edb96cc33c3393df34cbe048600f0fb6b669d61`
- conclusion SUCCESS
- artifact id `9676070821`
- artifact name `Eden-dc95-X1-nvdrv-ipc-dispatch-gap`
- size `31,346,027` bytes
- SHA-256 `26d68afae986d8e526b110d8e19826d642d9accda23e68c47d4b8fe13fa93184`
- reruns 0

Runtime log:

`eden_log(20260828-061910).txt`

Environment:

- TOTK 1.2.1
- Adreno X1-85, driver 512.863.0, Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- swap 3 -> 2 clamp OFF
- Descriptor Ring remained ON but sampled DBUF reports showed zero alloc/reuse-wait activity.

Representative `[X1-IPCDISPATCH]` results:

- frame 840: `guestPostAvg=16.840 ms`, `ipcDispatchAvg=0.021 ms`, `serviceReplyAvg=0.014 ms`, submitter CPU share `1.45%`;
- frame 1320: `guestPostAvg=26.743 ms`, `ipcDispatchAvg=0.017 ms`, `serviceReplyAvg=0.039 ms`, submitter CPU share `1.64%`;
- frame 1440: `guestPostAvg=29.091 ms`, `ipcDispatchAvg=0.027 ms`, `serviceReplyAvg=0.033 ms`, submitter CPU share `1.38%`;
- representative slow reports: `missingA=0`, `missingB=0`.

Critical conclusion — CLOSED:

> Request -> `nvservices` handler dispatch is not the missing 20-30 ms owner. The dominant delay is previous candidate handler completion/reply-adjacent C -> next candidate sync-request issue A.

Therefore Windows host `nvservices` wake/scheduling, pre-candidate Nvidia ServerManager head-of-line delay, and lower candidate handler/reply body are closed as primary owners for this runtime.

## Exact KThread boundary for the next experiment

Exact dc95 `ThreadWaitReasonForDebugging` values:

- `None`
- `Sleep`
- `IPC`
- `Synchronization`
- `ConditionVar`
- `Arbitration`
- `Suspended`

`KThread::BeginWait()` drives the base state to Waiting.

`KThreadQueue::EndWait()` / `CancelWait()` drive it back to Runnable.

`KThread::SetState()` is the common transition point and clears the debugging wait reason before applying the new base state. Therefore an observation hook can snapshot old state/reason before the existing clear without changing wait semantics.

## Current experiment — Guest Post Wait Attribution

Branch:

`exp/x1-guest-post-wait-attribution`

Predecessor HEAD:

`491f911a6e7e13a9d43902edcc99a129ca08f893`

New control:

`X1 Log: Guest Post Wait Attribution`

Setting:

`x1_guest_post_wait_attribution_log`

Default OFF.

New report:

`[X1-GUESTWAIT]`

### Measurement

- candidate handler completion C opens a post-submit window for the dynamically observed candidate submitter;
- the immediate reply wake for that just-completed candidate request is excluded;
- common `KThread::SetState()` transitions for that thread are observed;
- non-Waiting -> Waiting records start + current SVC ID;
- Waiting -> non-Waiting records duration and classifies by the old wait reason captured before dc95 clears it;
- next candidate handler entry closes the window;
- the current candidate request's own A -> reply IPC wait is excluded;
- B is used as window-end proxy for A; completed IPC-dispatch timing shows this adds only ~0.02 ms/request.

### 120-frame aggregate

Reports:

- target tid;
- candidate windows total/avg/max;
- completed tracked wait time;
- `waitShare`;
- residual window time;
- wait count/time by reason: None/Sleep/IPC/Synchronization/ConditionVar/Arbitration/Suspended;
- top 3 SVC IDs by wait duration;
- transition sanity counters.

No per-event wait logging. No mutex on KThread state-transition path; aggregation uses atomics.

### Interpretation

- high `waitShare` -> follow the dominant reason/SVC only;
- low `waitShare` while submitter CPU share stays ~1-2% -> next target is Runnable residency / scheduler competitor attribution;
- mixed -> preserve both and instrument only the dominant remainder.

## Prepared files

- `src/core/x1_guest_post_wait_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_post_wait_attribution.py`
- `tools/adreno_lab/analyze_x1_guest_post_wait_attribution.py`
- `.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml`
- `NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md`
- `DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`

## Safety

The new pass is observation-only.

Allowed generated-source modifications are limited to:

- settings/UI;
- `k_thread.cpp` common state-transition observation;
- candidate NVDRV boundary hooks;
- rasterizer initialization/report hook;
- new profiler header.

Workflow hashes and requires unchanged:

- `k_thread.h`, `k_thread_queue.cpp`;
- KClient/KServer session behavior;
- KScheduler / GlobalSchedulerContext;
- prior `svc_ipc.cpp` IPC-dispatch A hook;
- ServerManager / multi-wait;
- nvhost GPU/ctrl;
- BufferQueue/HWC/VI;
- GPU worker / control scheduler / DmaPusher;
- Vulkan swapchain/scheduler/graphics pipeline;
- all prior profiler headers.

Existing BeginWait/EndWait, state store, wait-reason clear, scheduler callback, NVDRV Ioctl and prior profiler call counts are guarded.

No wait/sleep behavior, WaitHost/StallApplication, scheduling/priority/core, GPU submission, frame pacing, swap, buffer-count or speed behavior may change.

## Recommended first runtime after a future successful build

Use the same TOTK 1.2.1 route, DFPS OFF first.

ON:

- Guest Post Wait Attribution
- NVDRV IPC Dispatch Gap
- Guest Submit Thread Attribution
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- Descriptor Ring
- swap 3 -> 2 clamp A/B
- all behavioral A/B controls
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

## NEXT ACTION

Read `NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md`.

Static preparation is complete. Before any build, verify current branch HEAD, workflow `workflow_dispatch`-only state and Actions count.

## Build authorization state

- Frame Build: 1 successful attempt, no rerun
- GPU Command: 1 successful attempt, no rerun
- GPU Submit Gap: 1 successful attempt, no rerun
- Guest Submit Thread: 1 successful attempt, no rerun
- NVDRV IPC Dispatch Gap: 1 successful attempt, no rerun
- Guest Post Wait Attribution: 0 attempts, 0 reruns
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
