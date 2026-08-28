# CURRENT HANDOFF — Eden Adreno X1 Guest Submit Thread Attribution

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
- do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

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

- matched TOTK 1.4.2 raw main QueueBuffer `swap=2` maps to nominal ~30-FPS opportunities.
- raw `swap=3` maps to nominal ~20-FPS opportunities.
- VI remains ~60 Hz.
- raw swap interval originates in guest QueueBuffer input, not Qualcomm Vulkan Present/Mailbox/Target_60.
- raw-3 -> effective-2 HardwareComposer A/B executed correctly but did not create upstream frames.
- HardwareComposer interval gating is not the root <=20-FPS renderer-performance cause.
- DFPS ON could remain ~20-FPS class with raw swap=1.
- DFPS OFF could remain ~20-FPS class with raw swap=3.
- therefore DFPS and raw swap=3 are not the root cause of the ~45-50 ms frame-production interval.

### BufferQueue / Dequeue

Fast state:

- Queue -> Queue ~16.66 ms.
- free-slot wait ~14 ms class because producer is fast.

Slow gameplay:

- Queue -> Queue ~45-50 ms class.
- Queue -> next Dequeue entry ~0.16 ms.
- Dequeue total ~0.05 ms.
- free-slot wait ~0.001 ms.
- Dequeue END -> next Queue ~45-47 ms.

Conclusion — CLOSED:

> Slow gameplay is not waiting for a free BufferQueue slot. The buffer is immediately available; the missing time is after Dequeue returns and before the next QueueBuffer.

Heavy X1 diagnostic logging was also A/B checked and did not create the ~20-FPS behavior.

## Frame-Build Attribution — completed

Successful build:

- workflow `Build dc95 X1 Frame Build Attribution`
- run `33115424368`
- job `98668715842`
- attempt 1
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact id `9665216124`
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`
- no rerun

Runtime conclusion:

- DFPS ON slow gameplay: ~48.8 ms/frame; measured Vulkan Draw ~11.1 ms/frame; Graphics Configure ~7.2 ms/frame; `FillImageViews` ~0.7 ms/frame; ~37 ms/frame remained outside measured RasterizerVulkan scopes.
- DFPS OFF slow gameplay: ~19-21 FPS; Draw count materially lower and measured Vulkan Draw ~8.4 ms/frame, yet ~39 ms/frame remained outside measured Draw/Dispatch/Clear scopes.
- `FillImageViews` alone is not the missing-time owner.
- high Draw count alone is not sufficient to explain the ceiling.

## GPU Command Attribution — completed

Successful build:

- workflow `Build dc95 X1 GPU Command Attribution`
- run `33129866149`
- job `98716608240`
- attempt 1
- build HEAD `dafee3f7f08832dbd39aedf7f2c2607bf1b6112b`
- artifact id `9670361329`
- SHA-256 `5c0d99f3539dd46e79b8b3002ef48216acbcb7de1282c5078b5fb411dd389758`
- success, no rerun
- predecessor cleanup HEAD `368752c0cd9f98b1a94b7599e9a9a687eb1cc8a0`

Representative slow windows:

- ~50-53 ms/frame wall.
- GPU worker queue `PopWait`: ~32-37 ms/frame.
- GPU worker active: ~16-20 ms/frame.
- `ProcessCommands`: ~15-17 ms/frame.
- `PushCommand` itself is tiny.
- synchronous caller `blockWait=0`.

Conclusion — STRONGLY SUPPORTED:

> The asynchronous GPU worker spends most slow-frame wall time idle waiting for upstream command supply. DmaPusher/command interpretation is material but does not own the missing ~30-35 ms.

Primary target moved upstream of `GPUThread::PushCommand`.

## GPU Submit Gap Attribution — completed

Successful authorized build:

- workflow `Build dc95 X1 GPU Submit Gap Attribution`
- run `33133440904`
- job `98728039155`
- attempt 1
- build HEAD `f65f93825979cde816aa41fc148deb042039416a`
- artifact `Eden-dc95-X1-gpu-submit-gap-attribution`
- artifact id `9671670627`
- size 31,331,056 bytes
- SHA-256 `0ef8e4172d812e4cfda90792f9bb2df0868dd192504cf2d3b11d30dcfbcdb313`
- success, no rerun
- one-shot trigger removed; cleanup HEAD `d17eb7314b2809c95e53874dbc7f64808df67006`

Runtime log:

`eden_log(20260828-030445).txt`

Runtime basis:

- exact Eden dc95
- TOTK 1.2.1
- Adreno X1-85
- Qualcomm 512.863.0 / Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- GPU Submit Gap Attribution ON
- GPU Command Attribution ON
- Frame Build Attribution ON
- Frame Cadence ON
- Dequeue Attribution ON
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- note: old swap 3->2 clamp and Descriptor Ring were still ON accidentally; both should be OFF in the next clean run

### GPU-submit runtime result

In stable slow gameplay the following inter-submit gaps are effectively identical:

1. candidate NVDRV GPU-submit service-entry gap,
2. confirmed `nvhost_gpu` device-submit-entry gap,
3. actual `PushGPUEntries` gap.

Representative stable behavior:

- roughly ~26 ms per submit interval,
- roughly two main GPU submits per ~52 ms frame,
- NVDRV service work only ~0.05-0.06 ms/frame class,
- `SubmitGPFIFOImpl` ~0.01-0.02 ms/frame class,
- channel-lock wait effectively zero,
- command copy/read and fence/syncpoint overhead tiny.

Conclusion — CLOSED / STRONGLY SUPPORTED:

> NVDRV IPC handling, `nvhost_gpu` GPFIFO preparation and `SubmitGPFIFOImpl` are not the owner of the ~25-30 ms inter-submit gap. The gap is already present before the GPU-submit ioctl reaches NVDRV.

This explains the GPU worker starvation structurally: the worker is not waiting behind an internal NVDRV queue; the guest/upstream side simply does not issue the next submit for that interval.

Do not optimize NVDRV/GPFIFO submission internals unless a later experiment contradicts this result.

## Exact new observation boundary

`HLERequestContext` retains the originator guest `Kernel::KThread` and exposes it through:

`ctx.GetThread()`

Exact dc95 `KThread` exposes:

- `GetThreadId()`
- `GetCpuTime()`
- `GetCurrentCore()`
- `GetActiveCore()`
- `GetPriority()`
- `GetContext().pc`

Exact dc95 `KScheduler::SwitchThread()` updates thread CPU time using the same `CoreTiming().GetClockTicks()` time base.

This enables a low-intrusion measurement at NVDRV entry without modifying scheduler behavior:

- wall time between consecutive GPU-submit requests from the same guest thread,
- guest CoreTiming tick delta between those requests,
- that thread's CPU-time tick delta,
- CPU share = thread CPU ticks / elapsed guest ticks.

## Current experiment — Guest Submit Thread Attribution

Branch:

`exp/x1-guest-submit-thread-attribution`

Goal:

Answer:

> Which guest thread produces the GPU submit requests, and is it CPU-bound or mostly waiting/preempted during the ~25-30 ms gap?

New runtime control:

`X1 Log: Guest Submit Thread Attribution`

Setting:

`x1_guest_submit_thread_attribution_log`

Default OFF.

New aggregate record:

`[X1-GUESTSUBMIT]`

120-frame reports include:

- active submitter thread count,
- dominant guest thread ID,
- dominant submit share,
- Ioctl1/Ioctl2 submit counts,
- same-thread submit wall-gap sum/max,
- guest CoreTiming tick delta,
- submitter `KThread::GetCpuTime()` delta,
- derived `cpuShare`,
- saved submit-entry PC and PC stability,
- current/active core and priority.

Up to 8 submitter thread IDs are tracked.

### Interpretation

#### High dominant share + high cpuShare

> One guest GPU producer thread is CPU-bound between submissions.

Next target becomes guest code / Dynarmic execution on that thread; use targeted PC/block attribution rather than scheduler-wait instrumentation.

#### High dominant share + low cpuShare

> One submitter owns GPU production but spends most of the gap not executing.

Then add targeted wait/SVC/synchronization attribution only for that thread.

#### Multiple material submitter threads

> GPU command production is distributed.

Attribute per-thread first before deeper kernel instrumentation.

Caller PC is identity evidence only; do not infer that the whole gap executes at that PC.

## Prepared files

- `src/video_core/x1_guest_submit_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_submit_thread_attribution.py`
- `tools/adreno_lab/analyze_x1_guest_submit_thread_attribution.py`
- `.github/workflows/build-dc95-x1-guest-submit-thread-attribution.yml`
- `NEXT_ACTION_GUEST_SUBMIT_THREAD_ATTRIBUTION.md`
- `DEBUG_HISTORY_20260828_GUEST_SUBMIT.md`

## Safety

The new pass is observation-only and modifies generated settings/UI, NVDRV service-entry observation and the rasterizer frame-report hook only.

The workflow hashes and requires unchanged:

- kernel scheduler,
- generic service framework / HLE IPC,
- `nvhost_gpu`,
- BufferQueue/HWC/VI,
- GPU worker / control scheduler / DmaPusher,
- Vulkan swapchain/scheduler/buffer cache/graphics pipeline,
- existing GPU command and GPU submit profiler headers.

Existing `ctx.ReadBuffer`, `nvdrv->Ioctl1/2` and GPU-submit service-record call counts must remain unchanged.

The new diff must not add sleeps, waits, thread-state/scheduling/priority/core-mask changes, swap/buffer-count/speed changes, or new `PushGPUEntries` behavior.

## Recommended first runtime after a future successful build

Use same TOTK 1.2.1 route, DFPS OFF first.

ON:

- Guest Submit Thread Attribution
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- swap 3 -> 2 clamp A/B
- Descriptor Ring
- Uniform cache A/B
- Draw/Dispatch skip A/B
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

## What NOT to do

- no ARM64 Actions without fresh explicit permission.
- no automatic rerun.
- no raw guest QueueBuffer modification.
- no VSync / Mailbox / Target_60 / speed-limit changes for attribution.
- no scheduler/fence/barrier/render-pass policy changes.
- no buffer-count modification.
- no simple alias dedupe.
- no blind persistent Uniform binding.
- no blind previous-staging reuse.
- do not treat intentional ForceStop as a crash.

## NEXT ACTION

Read:

`NEXT_ACTION_GUEST_SUBMIT_THREAD_ATTRIBUTION.md`

Finish static/pre-Actions validation. **Stop before ARM64 Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Guest Submit Thread Attribution`

If it fails, stop. No retry without another fresh explicit authorization.

## Build authorization state

- current branch: `exp/x1-guest-submit-thread-attribution`
- GPU-command ARM64 build attempts: 1 successful, 0 reruns
- GPU-submit-gap ARM64 build attempts: 1 successful, 0 reruns
- guest-submit-thread ARM64 build attempts: 0
- guest-submit-thread reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
