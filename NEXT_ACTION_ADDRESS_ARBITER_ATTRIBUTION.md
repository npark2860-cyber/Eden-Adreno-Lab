# NEXT ACTION — X1 Waker Pre-Signal Attribution (Stage C)

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- current source branch: `exp/x1-address-arbiter-signal-owner`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`

Never change the Eden baseline without explicit baseline-change approval.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Stage A — closed

The dominant GPU submitter `tid=0x53` performs one gameplay `WaitForAddress(..., WaitIfEqual, timeout=-1)` per rendered frame. Direct wait duration reconciles essentially exactly with reason-level `Arbitration`.

The absolute guest VA relocates between runs, so the profiler dynamically latches the current process's target address instead of hardcoding it.

## Stage B — closed

Dynamic-latch runtime:

`eden_log(20260828-122253).txt`

This run latched target address `0x210b1bc120`.

The matching signal path is unambiguous:

- victim / GPU submitter: `tid=0x53`
- sole observed waker: **`tid=0x4f`**
- signal type: **`SignalAndIncrementIfEqual`** (`incEq`)
- value: `1`
- count: `-1`
- approximately one matching signal per rendered frame
- post-warmup missing/no-active/overflow: `0`

Slow-regime timing proves late producer rather than slow wake completion:

- frame 1800: direct `70.368 ms`, `w2s=70.270 ms`, `s2e=0.098 ms`
- frame 1920: direct `40.185 ms`, `w2s=40.177 ms`, `s2e=0.008 ms`
- frame 2040: direct `45.026 ms`, `w2s=45.020 ms`, `s2e=0.007 ms`
- frame 2160: direct `50.797 ms`, `w2s=50.778 ms`, `s2e=0.019 ms`

Therefore do not spend another experiment re-proving the victim wait or AddressArbiter wake-completion path.

## Exact next causal question

> What delays the dynamically identified signal-owner thread before it calls the matching `SignalToAddress`?

In the observed run the waker is `tid=0x4f`, but Stage C should **not hardcode that TID across runs**. Latch the signal-owner TID from the current run's first matching target-address signal, just as Stage B now latches the target address.

## Stage C — waker-only inter-signal attribution

Instrument only the dynamically identified waker thread, and only while the AddressArbiter diagnostic is active.

Preferred measurement window:

`previous matching SignalToAddress completion -> next matching SignalToAddress entry`

or an equivalent narrowly bounded interval that answers what consumed the time before the next wake.

Required aggregate fields per 120 rendered frames:

- dynamically latched waker TID
- matching signal call count
- inter-signal total/avg/max duration
- waker KThread `Waiting` duration by existing wait-reason enum
- runnable/CPU residual for the waker
- dominant wait reason(s) in fast vs slow regimes
- current/last SVC attribution for waker waits if cheap
- guest PC and, if readily available/read-only, LR at matching `SignalToAddress` entry
- stability/change count for PC/LR across the window

The first goal is to decide which of these owns the 40-70 ms late-signal interval:

1. the waker is itself blocked in a specific KThread wait reason;
2. the waker is runnable/CPU-active for most of the interval;
3. the signal call site changes with regime;
4. a single stable call site exists and the delay is upstream of it.

## Correlation requirement

Compare identical 120-frame windows with existing:

- `[X1-ADDRSIG]`
- `[X1-ADDRARB]`
- `[X1-GUESTWAIT]`
- Frame Build / GPU Submit / GPU Command correlation logs
- raw QueueBuffer cadence

Use at least:

- fast raw-swap2 window
- transition window
- stable raw-swap3 window

## Scope constraints

Do **not**:

- trace all guest threads;
- add broad scheduler tracing;
- add a generic all-SVC profiler;
- emit per-event log flood;
- hardcode `tid=0x4f` as process-invariant;
- add waits/sleeps/locks;
- alter signal address/value/type/count;
- alter thread priority/core affinity;
- alter NVDRV/GPU/BufferQueue/HWC/VI/cadence/swap behavior.

Observation-only, default OFF or gated by the existing Address Arbiter diagnostic control.

## `None` fallback

Do not chase `None` in parallel with Stage C.

Only revisit it if a future controlled stable-slow window shows that the proven waker-before-signal interval is small while `None` becomes the dominant unexplained owner.

## Build state

Stage C has **not** been implemented or ARM64-built.

Current ARM64 authorization: **NONE**.

Before any Stage C ARM64 attempt:

1. implement only dynamically latched waker pre-signal attribution;
2. statically verify exact dc95 thread-state and signal call counts / unchanged semantics;
3. verify persistent workflow remains `workflow_dispatch` only;
4. verify branch diff contains only intended Stage C instrumentation/workflow/docs changes;
5. request fresh explicit authorization for exactly one ARM64 attempt;
6. no automatic retry on failure.
