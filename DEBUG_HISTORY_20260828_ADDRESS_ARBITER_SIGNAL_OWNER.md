# DEBUG HISTORY — X1 Address Arbiter Signal Owner

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- source branch: `exp/x1-address-arbiter-signal-owner`
- dynamic-latch source record HEAD before runtime documentation: `4d88b7231f3b4c7d45d567e372b61d7550da3631`
- ARM64 build run: `33168281215`
- ARM64 build HEAD: `b2dbc9dbe7cb69a5856850d5d60750355f186b19`
- runtime log: `eden_log(20260828-122253).txt`

Never change the exact Eden baseline without explicit baseline-change approval.

## Why Stage B needed a correction

The first Stage B implementation hardcoded the absolute guest VA observed in the first corrected Stage A run: `0x210adbc120`.

A later run showed the same logical once-per-frame `WaitIfEqual(timeout=-1)` object at `0x210b5bc120`, exactly `+0x800000` higher. Therefore the absolute guest VA is stable within one run but can relocate between runs.

Stage B was corrected to dynamically latch the first post-warmup target-thread `WaitIfEqual(timeout=-1)` address and trace `SignalToAddress` only for that latched address.

## Dynamic-latch runtime result

The new run dynamically latched:

- target submitter: `tid=0x53`
- target wait address: `0x210b1bc120`
- wait type: `WaitIfEqual`
- timeout: `-1`

The signal side is unambiguous:

- sole observed signaling guest thread: **`tid=0x4f`**
- signal type: **`incEq` = SignalAndIncrementIfEqual**
- value argument: **`1`**, stable (`vvar=0`)
- count argument: **`-1`**, stable (`cvar=0`)
- one signal slot only
- no signal-slot overflow
- no missing matched signal
- no no-active-wait signal in post-warmup gameplay windows
- after the first report boundary, `120` matching signal calls per `120` rendered frames

The first gameplay report at frame 240 has `119` completed/matched signals because one synchronous wait crosses the report boundary; this is the same boundary behavior already seen on the wait side.

## Timing result

Representative 120-frame windows:

| frame | raw swap2 | raw swap3 | direct Wait avg | wait-start -> signal (`w2s`) | signal -> wait-return (`s2e`) |
|---:|---:|---:|---:|---:|---:|
| 240 | 120 | 0 | 1.331 ms | 1.322 ms | 0.009 ms |
| 360 | 98 | 22 | 25.090 ms | 25.078 ms | 0.013 ms |
| 1560 | 120 | 0 | 1.072 ms | 1.062 ms | 0.011 ms |
| 1680 | 120 | 0 | 1.184 ms | 1.175 ms | 0.009 ms |
| 1800 | 15 | 105 | 70.368 ms | 70.270 ms | 0.098 ms |
| 1920 | 0 | 120 | 40.185 ms | 40.177 ms | 0.008 ms |
| 2040 | 0 | 120 | 45.026 ms | 45.020 ms | 0.007 ms |
| 2160 | 0 | 120 | 50.797 ms | 50.778 ms | 0.019 ms |

For post-warmup windows, `direct_avg - (w2s_avg + s2e_avg)` stays within about `0.001 ms` at report precision.

In the stable slow windows, more than `99.96%` of the measured synchronous wait is before the matching signal. The target wait returns essentially immediately once `tid=0x4f` performs the signal.

The existing reason-level `Arbitration` bucket still reconciles with direct `WaitForAddress` time. Even the largest runtime-window total mismatch in this log is only about `11.606 ms` across 120 frames (`~0.097 ms/frame`), at frame 1800.

## Stage B causal conclusion

Stage B is complete.

> The dominant GPU submitter `tid=0x53` blocks once per rendered frame on one dynamically relocated `WaitForAddress(..., WaitIfEqual, timeout=-1)` synchronization object. The matching wake is issued by one guest thread, `tid=0x4f`, using `SignalAndIncrementIfEqual(value=1, count=-1)`. Slow 20-FPS-regime waits are not caused by delayed wake completion after the signal: almost the entire 40-70 ms delay occurs before `tid=0x4f` calls `SignalToAddress`; `signal -> wait-return` is normally only a few microseconds.

Therefore the causal frontier moves from the victim wait (`tid=0x53`) to the producer/waker (`tid=0x4f`).

## Important non-conclusion

This does **not** yet prove what makes `tid=0x4f` late.

Do not claim that AddressArbiter itself is the final root cause. AddressArbiter is the synchronization edge through which upstream lateness reaches the GPU-submit thread.

Also retain the existing `None` warning: some slow windows in other controlled runs can contain substantial `None` wait time. Do not chase it unless a controlled stable-slow run demonstrates that the proven `tid=0x4f -> signal -> tid=0x53` edge is small while the frame remains slow.

## Next causal question

> What is `tid=0x4f` doing between consecutive target-address signals, and which state/wait/SVC or guest-code site expands before the late signal?

Next instrumentation should remain narrow:

- dynamically latch the signal-owner TID from the exact target-address signal (`tid=0x4f` in this run);
- attribute only that waker thread between consecutive matching signals;
- aggregate its KThread Waiting reasons and runnable/CPU residual;
- record current/last SVC information only for that waker if useful;
- cheaply record the guest PC/LR at the matching `SignalToAddress` call site if accessible without changing behavior;
- no all-thread scheduler tracing and no generic all-SVC profiler.

## ARM64 status

The dynamic-latch ARM64 run completed successfully and its one-shot workflow was removed after the runtime artifact was obtained.

Current ARM64 authorization: **NONE**.

No new ARM64 build/rebuild/rerun may be started without fresh explicit user authorization for exactly one attempt.
