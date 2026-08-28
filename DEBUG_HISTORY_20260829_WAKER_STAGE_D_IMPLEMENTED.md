# DEBUG HISTORY — Waker Stage D Implemented / Static Validated

Date: 2026-08-29 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage D branch:

`exp/x1-waker-stage-d-cpu-scheduler`

ARM64 authorization remained **NONE** throughout this work. No ARM64 build or rerun was triggered.

## Stage C runtime input retained

Runtime source:

`eden_log(20260828-173023).txt`

Established facts retained:

- victim / submitter in measured run: `tid=0x53`
- dynamically discovered waker: `tid=0x4f`
- matching signal type: `SignalAndIncrementIfEqual`
- matching signal -> victim return remains essentially immediate
- stable fast inter-signal ~= 33.7 ms
- stable slow inter-signal ~= 55.0 ms
- slow-minus-fast inter-signal ~= +21.3 ms
- Stage C total KThread Waiting increased by about +6.5 ms/signal
- Stage C `inter - Waiting` residual increased by about +14.8 ms/signal

## Important Stage C correction discovered before Stage D

Stage C total Waiting duration remains valid, but its **wait-reason breakdown is not valid**.

Reason:

Stage C recorded the debug wait reason when the thread entered `ThreadState::Waiting`. Exact dc95 commonly performs:

- `BeginWait(...); SetWaitReasonForDebugging(Arbitration);`
- `BeginWait(...); SetWaitReasonForDebugging(ConditionVar);`
- `BeginWait(...); SetWaitReasonForDebugging(Synchronization);`
- `BeginWait(...); SetWaitReasonForDebugging(Sleep);`

Therefore those waits can enter Stage C as reason `None` even though their correct named reason is present by the time the wait exits.

Some IPC paths set the reason before `BeginWait`, so entry reason is still useful as a fallback.

Stage D corrects completed-wait classification to:

> `exit reason if non-None, otherwise entry reason fallback`

Accordingly, the previous claim that Stage C disproved another named waker wait is withdrawn. Only the total wait/residual split remains established from Stage C.

## Exact dc95 direct reason-less BeginWait scan

After excluding paths which assign Sleep / IPC / Synchronization / ConditionVar / Arbitration, the focused direct reason-less candidates instrumented are:

1. `KThread::SetActivity` pinned wait
2. `KThread::SetCoreMask` pinned wait
3. `KProcess::EnterUserException`

No broad all-kernel BeginWait tracing was added.

## Stage D implementation

New source:

- `src/core/x1_waker_stage_d_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_d_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_d_attribution.py`

New aggregate report:

`[X1-WAKERD]`

### Dynamic waker / signal boundary

Stage D does not hardcode `tid=0x4f`.

It latches the first matching current-run signaler TID and measures between consecutive matching SignalToAddress entries, alongside the existing Stage C observation point.

### CPU versus runnable-unscheduled split

At each matching signal, Stage D samples read-only:

- `KThread::GetCpuTime()`
- `CoreTiming().GetClockTicks()`
- priority
- active core
- current core

CPU ticks are converted into the same signal-to-signal wall interval using the observed clock-tick delta. Stage D reports:

- inter-signal elapsed
- corrected KThread Waiting
- residual = inter - Waiting
- estimated CPU time
- runnable-unscheduled estimate = max(residual - CPU, 0)

Caveat: `GetCpuTime()` is accumulated on context switches, so the currently executing slice tail at a matching signal is accounted at a later switch. Use 120-frame aggregate trends, not single-frame CPU deltas, as the primary evidence.

### Corrected wait attribution

Completed waits use exit reason first and entry reason only as fallback.

If the corrected reason is still `None`, Stage D separately counts/times:

- unknown reason-less wait
- SetActivity pinned wait
- SetCoreMask pinned wait
- process user-exception wait

### Signal caller context

Stage D retains matching signal PC and adds a fixed 16-slot LR histogram, reporting the top four LR values per 120-frame block plus overflow.

No per-event logging was added.

## Static validation

First Ubuntu-only validation:

- run `33216227768`
- job `99000324527`
- failed only at Stage D transplant application
- exact failure: wrong assumed region-end anchor around the unique KProcess user-exception BeginWait

This was an instrumentation anchor error, not a runtime/semantic failure.

Minimal correction:

- replace the unique comment + `cur_thread->BeginWait(...)` pair globally exactly once
- do not assume a following function name

Second Ubuntu-only validation:

- run `33216436564`
- job `99000993229`
- conclusion `success`

Passed:

- exact dc95 checkout
- retained diagnostic reconstruction
- focused Stage A through C reconstruction
- Stage D application
- exact dc95 HEAD preservation
- `git diff --check`
- Python compile for Stage C/D transplant and analyzers
- dynamic-waker/no-hardcoded-`0x4f` guard
- Stage D CPU/clock/core metadata hooks
- focused three-site reason-less wait hooks
- original `SignalAddressArbiter` call count preserved
- original `KThread::BeginWait` call count preserved
- original `KProcess::BeginWait` call count preserved
- no wait/sleep insertion
- no priority/core-affinity mutation
- no GPU/swap/cadence behavior mutation
- analyzer synthetic-log smoke test

The temporary Ubuntu workflow was deleted after success.

## Runtime question now ready

A Stage D ARM64 runtime, only after fresh explicit one-attempt authorization, should decide:

1. whether the stable-slow residual increase is mostly actual waker CPU time;
2. whether it is mostly runnable-but-unscheduled time;
3. which corrected named wait reason owns the additional Waiting;
4. whether any of the three true reason-less BeginWait sites contributes materially;
5. which LR caller dominates matching signals in fast versus slow regimes.

No optimization or behavior-changing A/B should be attempted before this split is measured.
