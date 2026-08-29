# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-d-cpu-scheduler`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime record: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D implementation/build record: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- Stage D runtime record: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- next action: `NEXT_ACTION_WAKER_STAGE_E.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest ARM64 build — Stage D SUCCESS

- run `33217783844`
- job `99005198468`
- attempt `1`
- branch `exp/x1-waker-stage-d-cpu-scheduler`
- build HEAD `faf518e70811ba9f0c1a754c14d5da8584753904`
- exact Eden source `dc95cd09eea9749250fe31a3072684d341d19417`
- conclusion `success`
- exact dc95 verify / retained chain / Stage A-C / Stage D apply+verify / configure / ARM64 compile / package / upload: all `success`
- artifact `Eden-dc95-X1-waker-stage-d`
- artifact id `9704658049`
- size `31,387,303` bytes
- SHA-256 `cd7e8e2f218a522ad9a90e8ccff8170461be1d40732c15bcf24bd0ebc1cef7b5`
- created `2026-08-28T23:12:10Z`
- expires `2026-09-11T23:12:08Z`

No rerun occurred and no second ARM64 attempt was created. Persistent Stage D ARM workflow is manual-only `workflow_dispatch`.

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

Profiler dynamically latches the current run's first post-warmup target-thread `WaitIfEqual(timeout=-1)` address.

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

Stage C established only the total waker signal-to-signal Waiting versus residual split. Its old wait-reason breakdown is invalid because exact dc95 commonly assigns Arbitration / ConditionVar / Synchronization / Sleep after `BeginWait`.

Correct completed-wait classification, implemented in Stage D:

> exit reason if non-None, otherwise entry reason fallback

Stable-fast raw swap2 in Stage C was approximately:

- inter-signal `33.722 ms`
- total Waiting `27.708 ms`
- residual `6.014 ms`

Stable-slow raw swap3 was approximately:

- inter-signal `55.022 ms`
- total Waiting `34.183 ms`
- residual `20.839 ms`

Slow-minus-fast:

- inter-signal `+21.299 ms`
- Waiting `+6.474 ms`
- residual `+14.825 ms`

These total values remain valid; the Stage C named-reason split does not.

## Stage D — RUNTIME COMPLETE

Runtime:

`eden_log(20260829-024002).txt`

Measured identity:

- exact dc95
- dynamic victim address `0x210b1bc120`
- victim `tid=0x53`
- dynamic waker `tid=0x4f`
- waker switches `0`
- signal `incEq`, value `1`, count `-1`
- matching signal guest PC `0x85a03528`
- waker priority `44`
- latest active/current core `0/0`
- malformed CPU/wait/interval `0`

Stable block selection:

- pure swap2: frames `480, 600, 720, 840, 960, 1080, 1320, 1440`
- pure swap3: frames `1800, 1920, 2040, 2160, 2280`
- transition frame 1680 (`10 swap2 / 110 swap3`, `interAvg=84.143 ms`) excluded from stable averages

### Stage D aggregate split

| metric | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| residual | 7.748 ms | 22.075 ms | +14.327 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled | 0.239 ms | 0.307 ms | +0.068 ms |

Therefore the slow-regime +23.52 ms is mixed:

- about +14.28 ms (~60.7%) additional waker CPU execution;
- about +9.19 ms (~39.1%) additional Waiting;
- only +0.07 ms (~0.3%) runnable-unscheduled.

**Runnable/scheduler starvation is closed for this slowdown.**

CPU accounting retains the known context-switch accumulation caveat, so use these multi-block aggregate trends rather than individual intervals.

### Corrected wait reason — decisive mode shift

Average corrected reason time per signal:

| reason | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| ConditionVar | 17.252 ms | 0.469 ms | -16.784 ms |
| Arbitration | 7.440 ms | 32.339 ms | +24.900 ms |
| Sleep | 0.996 ms | 1.358 ms | +0.362 ms |
| Synchronization | 0.019 ms | 0.687 ms | +0.668 ms |
| IPC | 0.023 ms | 0.038 ms | +0.015 ms |
| true None | 0.000 ms | 0.000 ms | 0.000 ms |

Stable-fast corrected Waiting is primarily ConditionVar (~67.1%) with Arbitration secondary (~28.9%).

Stable-slow corrected Waiting is overwhelmingly Arbitration (~92.7%) and ConditionVar nearly disappears (~1.3%).

The net Waiting increase is only +9.19 ms because `+24.90 ms` Arbitration expansion is offset by `-16.78 ms` ConditionVar contraction.

Exact dc95 `KAddressArbiter::WaitIfLessThan` and `WaitIfEqual` both assign `ThreadWaitReasonForDebugging::Arbitration` after `BeginWait`, so the Stage D corrected Arbitration bucket maps to an actual AddressArbiter wait path.

### True None branch — CLOSED

All focused reason-less Stage D sites remain zero:

- unknown None `0`
- SetActivity pinned `0`
- SetCoreMask pinned `0`
- process user-exception `0`

### Signal LR context

Signal PC stays `0x85a03528` in both regimes. Same LR set remains, so there is no wholesale callsite switch.

Stable-fast, 960 signals:

- `0x859cfb40`: 79.27%
- `0x859cfa8c`: 17.81%
- remaining contexts ~2.9%

Stable-slow, 600 signals:

- `0x859cfb40`: 66.33%
- `0x859cfa8c`: 30.67%
- remaining contexts ~3.0%

The second LR becomes more common in slow mode. Preserve this correlation but do not treat it alone as root cause.

Victim-side `w2s` also remains consistent with the causal direction:

- stable swap2 mean ~`1.381 ms`
- stable swap3 mean ~`42.112 ms`
- signal -> victim return remains near zero

## Current causal frontier — Stage E

Stage D is complete.

The next question is:

> Which AddressArbiter wait performed by the dynamically identified waker owns the slow-regime Arbitration expansion, and which guest thread releases that wait?

Stage E must remain narrow:

1. dynamically reuse the current-run matching-signal waker TID; do not hardcode `0x4f`;
2. aggregate only that thread's `WaitForAddress` calls by address/type/value/timeout and duration;
3. promote only the dominant current-run waker wait key into matching `SignalToAddress` owner attribution;
4. keep the CPU branch separate; if cheap, correlate interval Waiting/Arbitration/CPU with the existing top signal LR contexts;
5. do not broaden into all-thread scheduler or all-SVC tracing.

See `NEXT_ACTION_WAKER_STAGE_E.md` for the exact Stage E plan and prohibitions.

## Actions state / ARM64 authorization

Persistent Stage D ARM workflow is manual-only `workflow_dispatch`.

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
