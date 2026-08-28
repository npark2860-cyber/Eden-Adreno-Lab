# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-d-cpu-scheduler`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime record: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D implementation/static record: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- next action: `NEXT_ACTION_WAKER_STAGE_D.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest ARM64 build — Stage C SUCCESS

- run `33190793610`
- job `98915420071`
- attempt `1`
- build branch `exp/x1-waker-pre-signal-attribution`
- build HEAD `7fdb505cda0af8559e5cea600721dc2cb17ac38b`
- conclusion `success`
- exact dc95 verify / Stage C apply / configure / ARM64 compile / package / upload: all `success`
- artifact `Eden-dc95-X1-waker-stage-c`
- artifact id `9694545153`
- size `31,377,910` bytes
- SHA-256 `c47e008a951ce3a974a9694d2b7ee8b06c4fd4379b387ad687a6e7b5f35e91b0`

No rerun occurred. Persistent ARM workflow was restored to manual-only `workflow_dispatch` after the approved run.

## Closed causal chain retained

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe remains rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is mapped adaptive fast stream; heavy payload repeat does not make blind lifetime reuse safe.
- classic-cache fallback did not break the gameplay ceiling.
- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- swap3->effective2 clamp and DFPS experiments did not raise upstream production rate.
- BufferQueue free-slot/backpressure is closed as primary owner.
- slow Frame Build is roughly 48-55 ms/frame while measured Vulkan scopes explain only a minority.
- GPU worker is mostly starved in queue wait; active GPU-command work is not the missing interval.
- long inter-submit gap exists before NVDRV handler entry; handler/SubmitGPFIFO/locks/fence/syncpoint are tiny.
- dominant guest submitter in tested runs = `tid=0x53`, CPU share about 1-2%.
- NVDRV IPC dispatch is about 0.02-0.03 ms/request; host service scheduling is not the missing owner.
- post-submit interval is generally mostly guest KThread `Waiting`.

## Address Arbiter Stage A — COMPLETE

Within each process the dominant submitter waits on one stable gameplay key:

- victim / submitter: `tid=0x53` in tested runs
- operation: `WaitIfEqual`
- timeout: `-1`
- direct `WaitForAddress` duration reconciles essentially one-for-one with reason-level `Arbitration`.

Absolute guest VA is not process-invariant. Observed:

- `0x210adbc120`
- `0x210b5bc120`
- `0x210b1bc120`

Profiler now dynamically latches the current run's first post-warmup target-thread `WaitIfEqual(timeout=-1)` address.

## Address Arbiter Stage B — COMPLETE

Stage B proved the late-waker edge:

- victim `tid=0x53`
- sole matching waker `tid=0x4f` in measured runs
- signal `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- normal gameplay one matching signal per rendered frame
- missing/no-active/overflow `0`
- `direct WaitForAddress ~= wait-start -> matching-signal (w2s)`
- signal -> wait-return (`s2e`) is essentially zero

Therefore the long submitter AddressArbiter delay happens before the waker signals. Once the matching signal arrives, the victim returns essentially immediately.

## Stage C — RUNTIME COMPLETE

Runtime:

`eden_log(20260828-173023).txt`

Measured run:

- dynamic wait address `0x210b5bc120`
- victim `tid=0x53`
- dynamic waker `tid=0x4f`
- waker switches `0`
- matching-signal sanity clean

Stable-fast raw swap2 windows averaged approximately:

- inter-signal `33.722 ms`
- waker KThread Waiting `27.708 ms`
- Stage-C residual `6.014 ms`

Stable-slow raw swap3 windows averaged approximately:

- inter-signal `55.022 ms`
- waker KThread Waiting `34.183 ms`
- Stage-C residual `20.839 ms`

Slow-minus-fast:

- inter-signal `+21.299 ms`
- total Waiting `+6.474 ms`
- Stage-C residual `+14.825 ms`

This **total Waiting versus residual split remains valid**.

### Critical correction: Stage C wait-reason breakdown is NOT valid

Do not use the old Stage C claim that named waker waits were absent.

Stage C stored the debug reason when the thread **entered** `ThreadState::Waiting`. Exact dc95 commonly performs:

- `BeginWait(...); SetWaitReasonForDebugging(Arbitration);`
- `BeginWait(...); SetWaitReasonForDebugging(ConditionVar);`
- `BeginWait(...); SetWaitReasonForDebugging(Synchronization);`
- `BeginWait(...); SetWaitReasonForDebugging(Sleep);`

Thus named waits can have been counted as Stage-C `None`.

Some IPC paths assign the reason before BeginWait, so the entry value is useful only as fallback.

Correct Stage D rule:

> completed wait reason = exit reason if non-None, otherwise entry reason fallback

Accordingly, the earlier conclusion that Stage C disproved another named Arbitration/Sync/ConditionVar/Sleep wait is withdrawn. Stage C only established the signal-to-signal total Waiting/residual split.

### Signal callsite retained

Matching SignalToAddress PC was overwhelmingly `0x85f16528`; LR varied materially. This motivated a top-LR histogram rather than treating the common PC as a final caller identity.

## Stage D — IMPLEMENTED / STATIC VALIDATED

Current branch:

`exp/x1-waker-stage-d-cpu-scheduler`

New files:

- `src/core/x1_waker_stage_d_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_d_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_d_attribution.py`

New report:

`[X1-WAKERD]`

Stage D remains observation-only and does not hardcode `tid=0x4f`.

### A. CPU versus runnable-unscheduled

At each matching dynamic-waker signal entry Stage D samples read-only:

- `KThread::GetCpuTime()`
- `CoreTiming().GetClockTicks()`
- priority
- active core
- current core

Per matching-signal interval it reports:

- inter-signal wall elapsed
- corrected KThread Waiting
- residual = inter - Waiting
- estimated CPU time
- runnable-unscheduled estimate = max(residual - CPU, 0)

CPU conversion uses the same observed `GetClockTicks()` domain; no hardcoded CPU frequency is used.

Caveat: `GetCpuTime()` is updated on context switches, so the currently executing slice tail at a signal may be accounted on a later switch. Use 120-frame aggregate trends, not one interval, as primary evidence.

### B. Corrected wait reason / true None sites

Completed waits use exit reason first and entry reason as fallback.

After exact dc95 BeginWait rescan, the focused direct reason-less sites instrumented are only:

1. `KThread::SetActivity` pinned wait
2. `KThread::SetCoreMask` pinned wait
3. `KProcess::EnterUserException`

If a completed wait still has corrected reason `None`, Stage D reports those three sites separately plus unknown.

No broad all-kernel BeginWait trace was added.

### C. Signal LR histogram

A fixed 16-slot aggregate LR table reports top four matching-signal LRs per 120-frame block plus overflow. No per-event log flood was added.

## Stage D static validation

Initial Ubuntu-only run:

- run `33216227768`
- job `99000324527`
- failed only because the transplant incorrectly assumed the function name following the unique KProcess user-exception BeginWait.

Minimal anchor correction was applied; no semantic scope change.

Successful Ubuntu-only run:

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
- Python compile / analyzer smoke test
- no hardcoded `0x4f`
- CPU/clock/core metadata hooks present
- only the three focused reason-less wait sites instrumented
- original `SignalAddressArbiter` call count preserved
- original `KThread::BeginWait` count preserved
- original `KProcess::BeginWait` count preserved
- no sleep/wait insertion
- no priority/core-affinity mutation
- no GPU/swap/cadence behavior mutation

Temporary Stage D Ubuntu workflow was deleted after success.

## Current causal frontier — Stage D runtime

A future Stage D runtime must compare stable raw swap2 and stable raw swap3 windows and decide which branch owns the ~21 ms slow-regime signal-period increase:

1. actual dynamic-waker CPU execution;
2. runnable-but-unscheduled delay;
3. corrected named KThread wait reason;
4. one of the three true reason-less direct wait sites;
5. a mixture of the above.

Top LR distribution should then identify which higher-level signal caller is associated with the dominant branch.

Do not optimize or alter priority/core behavior before this split is measured.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
