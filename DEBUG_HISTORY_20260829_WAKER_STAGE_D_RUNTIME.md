# DEBUG HISTORY — Waker Stage D Runtime

Date: 2026-08-29 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage D branch:

`exp/x1-waker-stage-d-cpu-scheduler`

Stage D ARM64 artifact:

- run `33217783844`
- build HEAD `faf518e70811ba9f0c1a754c14d5da8584753904`
- artifact `Eden-dc95-X1-waker-stage-d`
- artifact id `9704658049`
- SHA-256 `cd7e8e2f218a522ad9a90e8ccff8170461be1d40732c15bcf24bd0ebc1cef7b5`

Runtime log:

`eden_log(20260829-024002).txt`

ARM64 authorization after this run remains **NONE**. No build/rerun was triggered while analyzing or documenting the runtime.

## Runtime identity / sanity

The runtime is exact dc95 and the focused chain remained stable:

- victim / submitter: `tid=0x53`
- dynamic wait address: `0x210b1bc120`
- dynamic matching waker: `tid=0x4f`
- signal: `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- waker switches `0`
- matching signal sanity clean after warmup
- Stage D malformed CPU/wait/interval counters `0`
- true reason-less wait-site buckets all `0`
- waker priority `44`
- latest active/current core `0/0`
- matching signal guest PC stable at `0x85a03528`

The Stage B conclusion remains valid: matching signal -> victim return is essentially immediate; the long victim delay is still before the waker signal.

## Stable block selection

For the Stage D comparison, use only pure-cadence 120-frame blocks.

Stable-fast raw swap2 blocks:

- frame 480
- frame 600
- frame 720
- frame 840
- frame 960
- frame 1080
- frame 1320
- frame 1440

All eight blocks contain `120 swap2 / 0 swap3`.

Stable-slow raw swap3 blocks:

- frame 1800
- frame 1920
- frame 2040
- frame 2160
- frame 2280

All five blocks contain `0 swap2 / 120 swap3`.

Do not use startup/transition blocks as stable representatives. In particular frame 1680 contains `10 swap2 / 110 swap3` and a transition outlier (`interAvg=84.143 ms`).

## Stage D aggregate result

Averaged over the stable blocks:

| metric | stable fast swap2 | stable slow swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected KThread Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| residual = inter - Waiting | 7.748 ms | 22.075 ms | +14.327 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled estimate | 0.239 ms | 0.307 ms | +0.068 ms |

Interpretation of the ~23.52 ms slow-regime signal-period increase:

- approximately `+14.28 ms` (~60.7%) is accounted by additional estimated waker CPU execution;
- approximately `+9.19 ms` (~39.1%) is additional KThread Waiting;
- runnable-but-unscheduled adds only about `+0.07 ms` (~0.3%).

Therefore the scheduler-starvation branch is closed for this measured slowdown. The dynamic waker is not spending the missing interval ready-but-denied-CPU.

The CPU estimate must retain the existing caveat that `GetCpuTime()` is accumulated on context switches and individual intervals can carry slice-tail accounting into the next sample. The conclusion above is based on multi-block aggregates, not any single interval.

## Corrected wait reason result — decisive mode switch

Average corrected wait-reason time per matching-signal interval:

| reason | stable fast swap2 | stable slow swap3 | slow-fast |
|---|---:|---:|---:|
| ConditionVar | 17.252 ms | 0.469 ms | -16.784 ms |
| Arbitration | 7.440 ms | 32.339 ms | +24.900 ms |
| Sleep | 0.996 ms | 1.358 ms | +0.362 ms |
| Synchronization | 0.019 ms | 0.687 ms | +0.668 ms |
| IPC | 0.023 ms | 0.038 ms | +0.015 ms |
| true None | 0.000 ms | 0.000 ms | 0.000 ms |

This is the most important Stage D correction to Stage C.

Stable fast waits are primarily `ConditionVar` (~67.1% of corrected wait time), with `Arbitration` secondary (~28.9%).

Stable slow waits are overwhelmingly `Arbitration` (~92.7% of corrected wait time), while `ConditionVar` nearly disappears (~1.3%).

The net Waiting increase is only +9.19 ms because the `+24.90 ms` Arbitration expansion is partially offset by `-16.78 ms` ConditionVar contraction.

Thus the slow regime is not merely a longer version of the fast wait mix. The dynamic waker changes into an AddressArbiter-dominated wait regime.

Exact dc95 `KAddressArbiter::WaitIfLessThan` and `WaitIfEqual` both perform `BeginWait(...)` and then assign `ThreadWaitReasonForDebugging::Arbitration`, confirming that the corrected Stage D Arbitration bucket corresponds to an actual address-arbiter wait path.

## True None branch — CLOSED

Across all stable Stage D blocks:

- `noneUnknown = 0`
- `KThread::SetActivity` pinned wait = `0`
- `KThread::SetCoreMask` pinned wait = `0`
- `KProcess::EnterUserException` wait = `0`

The three focused reason-less candidates do not own this slowdown.

## Signal caller context

Matching SignalToAddress guest PC stayed at:

`0x85a03528`

The same LR set appears in both regimes, so there is no wholesale signal-callsite switch.

Aggregated top LR counts:

### Stable fast — 960 matching signals

- `0x859cfb40`: 761 / 960 = 79.27%
- `0x859cfa8c`: 171 / 960 = 17.81%
- `0x859ea364`: 21 / 960 = 2.19%
- `0x859dc78c`: 7 / 960 = 0.73%

### Stable slow — 600 matching signals

- `0x859cfb40`: 398 / 600 = 66.33%
- `0x859cfa8c`: 184 / 600 = 30.67%
- `0x859ea364`: 15 / 600 = 2.50%
- `0x859dc78c`: 3 / 600 = 0.50%

So the second LR context becomes materially more common in slow mode, but the same two dominant caller contexts remain. Treat this as a correlation to preserve, not a root-cause conclusion by itself.

## Victim-side correlation retained

Across the stable blocks, the victim's matching wait-start -> signal latency remains small in stable-fast and large in stable-slow:

- stable-fast mean `w2s ~= 1.381 ms`
- stable-slow mean `w2s ~= 42.112 ms`

Signal -> victim return stays near zero.

This remains consistent with Stage B: the waker's pre-signal path owns the victim delay.

## Stage D conclusion

**Stage D is complete.**

Correct causal statement:

> In the raw-swap3 slow regime, the dynamic waker `tid=0x4f` is not primarily delayed by host/guest runnable scheduling starvation or any true reason-less KThread wait. The ~23.5 ms longer signal period is a mixed increase: about +14.3 ms of additional waker CPU execution plus +9.2 ms of additional Waiting. The corrected Waiting composition changes sharply from ConditionVar-dominant in raw-swap2 to AddressArbiter/Arbitration-dominant in raw-swap3; Arbitration itself expands by about +24.9 ms per signal while ConditionVar contracts by about -16.8 ms.

This moves the causal frontier to two narrow branches only:

1. identify the dynamic waker's own dominant AddressArbiter wait key/type and the producer which releases it;
2. keep the measured CPU branch separate and correlate it with the existing top signal LR contexts before any wider CPU tracing.

Do not reopen runnable-unscheduled, true-None waits, broad scheduler tracing, or priority/core-affinity tuning without contrary evidence.
