# NEXT ACTION — X1 Waker Pre-Signal Attribution (Stage C)

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- current source branch: `exp/x1-waker-pre-signal-attribution`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C implementation record: `DEBUG_HISTORY_20260828_WAKER_STAGE_C_IMPLEMENTED.md`

Never change the Eden baseline without explicit baseline-change approval.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Stage A — closed

The dominant GPU submitter performs one gameplay `WaitForAddress(..., WaitIfEqual, timeout=-1)` per rendered frame in the tested scenario. Direct wait duration reconciles essentially exactly with reason-level `Arbitration`.

The absolute guest VA relocates between runs, so the profiler dynamically latches the current process's target address instead of hardcoding it.

## Stage B — closed

Runtime:

`eden_log(20260828-122253).txt`

This run proved:

- victim / GPU submitter: `tid=0x53`
- dynamically latched target address: `0x210b1bc120`
- sole observed matching waker: `tid=0x4f`
- signal type: `SignalAndIncrementIfEqual`
- value `1`, count `-1`
- one matching signal per rendered frame in normal gameplay
- slow wait time is almost entirely before signal; signal -> return is near-zero.

Representative slow timing:

- frame 1800: direct `70.368 ms`, `w2s=70.270 ms`, `s2e=0.098 ms`
- frame 1920: direct `40.185 ms`, `w2s=40.177 ms`, `s2e=0.008 ms`
- frame 2040: direct `45.026 ms`, `w2s=45.020 ms`, `s2e=0.007 ms`
- frame 2160: direct `50.797 ms`, `w2s=50.778 ms`, `s2e=0.019 ms`

Do not re-prove the victim wait or AddressArbiter wake-completion path.

## Stage C — implemented and statically validated

Stage C source:

- `src/core/x1_waker_pre_signal_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_pre_signal_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_pre_signal_attribution.py`

It is observation-only and gated by the existing Address Arbiter diagnostic control.

### Dynamic waker latch

Do **not** hardcode `tid=0x4f`.

The first current-run `SignalToAddress` that matches Stage B's dynamically latched target address latches its guest TID as the waker. Only that TID is attributed afterward.

### Measurement window

`matching SignalToAddress entry -> next matching SignalToAddress entry`

This avoids wrapping or changing the original `SignalAddressArbiter` call.

### `[X1-WAKER]` fields

Per 120 rendered frames:

- waker TID
- matching signal calls
- closed inter-signal interval count
- inter-signal total/avg/max
- waker KThread waiting total and wait share
- wait-reason count/time for `None`, `Sleep`, `IPC`, `Synchronization`, `ConditionVar`, `Arbitration`, `Suspended`
- non-wait residual total/avg/max
- last wait SVC id
- guest PC/LR at matching signal entry, with per-window mismatch counts and latest values
- wait/malformed/switch sanity counters

The non-wait residual is `inter-signal - attributed KThread waiting`; treat it as runnable/CPU/non-wait remainder, not automatic proof of guest instruction execution.

### Static validation

Ubuntu run:

- run `33172180578`
- job `98851759971`
- conclusion `success`

It verified exact dc95 reconstruction, Stage B reconstruction, Stage C transplant/analyzer syntax, required hooks, no hardcoded `0x4f`, unchanged wait/signal call counts and unchanged KThread state/scheduler core tokens, plus behavior-change guards.

Temporary static workflow removed after success.

Persistent workflow remains `workflow_dispatch` only.

## Exact next action

Stage C is **not ARM64-built yet**.

After fresh explicit authorization for exactly one ARM64 attempt:

1. build exact dc95 plus retained diagnostic chain + Stage B + Stage C once;
2. no retry on failure without another authorization;
3. run the same controlled TOTK 1.2.1 scenario;
4. enable at minimum:
   - `X1 Log: Address Arbiter Attribution`
   - `X1 Log: Guest Post Wait Attribution`
   - existing cadence/submit correlation logs used in Stage B;
5. keep behavioral A/B controls OFF;
6. collect enough runtime for fast swap2, transition and stable swap3;
7. analyze `[X1-WAKER]` together with `[X1-ADDRSIG]`, `[X1-ADDRARB]`, GuestWait and raw cadence.

## Runtime decision tree

Primary question:

> What owns the dynamically identified waker's 40-70 ms before the next matching signal?

- **specific wait reason grows with inter-signal time** -> next target only that wait path/SVC on the waker;
- **wait share small, residual grows** -> move into the waker's guest execution path immediately upstream of the stable signal call site;
- **PC/LR stable** -> one signal call site; delay is upstream of it;
- **PC/LR changes with regime** -> split by call site before deeper attribution;
- **alternate waker appears (`wakerSwitch`)** -> do not assume a single producer until that ownership change is understood.

## Scope constraints

Do **not**:

- trace all guest threads;
- add broad scheduler tracing;
- add a generic all-SVC profiler;
- emit per-event log flood;
- hardcode `tid=0x4f`;
- add waits/sleeps/locks;
- alter signal address/value/type/count;
- alter thread priority/core affinity;
- alter NVDRV/GPU/BufferQueue/HWC/VI/cadence/swap behavior.

Do not chase the separate GuestWait `None` class in parallel unless a controlled stable-slow runtime shows the Stage C waker-before-signal interval is small while the frame remains slow.

## ARM64 status

Current ARM64 authorization: **NONE**.

Do not start any Stage C ARM64 build until the user gives fresh explicit authorization for exactly one attempt.
