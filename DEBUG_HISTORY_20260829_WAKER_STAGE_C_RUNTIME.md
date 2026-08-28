# DEBUG HISTORY — Waker Stage C Runtime Attribution

Updated: 2026-08-29 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- lab branch: `exp/x1-waker-pre-signal-attribution`
- Stage C static-validated source anchor: `d26232a43cf95fffcd240646a83e56f939aab2cf`
- ARM64 build run: `33190793610`
- build HEAD: `7fdb505cda0af8559e5cea600721dc2cb17ac38b`
- runtime log: `eden_log(20260828-173023).txt`

Do not change the fixed Eden baseline without explicit approval.

ARM64 authorization after the successful one-shot attempt: **NONE**.

## Build result

Stage C ARM64 build completed successfully:

- run `33190793610`
- job `98915420071`
- conclusion `success`
- exact dc95 verify `success`
- Stage C transplant/verify `success`
- MSYS2 setup `success`
- configure `success`
- ARM64 compile `success`
- package `success`
- upload `success`
- artifact `Eden-dc95-X1-waker-stage-c`
- artifact id `9694545153`
- size `31,377,910` bytes
- SHA-256 `c47e008a951ce3a974a9694d2b7ee8b06c4fd4379b387ad687a6e7b5f35e91b0`

No rerun/retry occurred.

## Stage B retained result

This run independently retained the Stage B causal edge:

- victim / submitter: `tid=0x53`
- dynamic exact wait address: `0x210b5bc120`
- wait: `WaitIfEqual`, timeout `-1`
- sole observed signal owner: `tid=0x4f`
- signal: `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- post-warmup signal slots `1`
- waker switches `0`
- normal windows: one matching signal per rendered frame
- missing/noActive/overflow `0`
- signal-to-wait-return (`s2e`) remains essentially zero.

Representative Stage B timing in this Stage C run:

| frame | cadence | wait->signal (`w2s`) | signal->return (`s2e`) |
|---:|---|---:|---:|
| 240 | swap2 120/120 | 1.581 ms | 0.011 ms |
| 840 | swap2 120/120 | 1.137 ms | 0.014 ms |
| 1080 | swap3 120/120 | 79.632 ms | 0.008 ms |
| 1200 | swap3 120/120 | 33.653 ms | 0.007 ms |
| 1320 | swap3 120/120 | 21.071 ms | 0.007 ms |
| 1440 | swap3 120/120 | 17.385 ms | 0.008 ms |
| 1560 | swap3 120/120 | 41.198 ms | 0.012 ms |
| 1680 | swap3 120/120 | 44.778 ms | 0.008 ms |

Therefore the long `tid=0x53` AddressArbiter wait still ends immediately when `tid=0x4f` finally signals.

## Stage C output

New aggregate:

`[X1-WAKER]`

It measures the dynamically discovered waker only, between consecutive matching signals.

Representative windows:

| frame | cadence | inter-signal avg | waker Waiting avg | wait share | residual avg |
|---:|---|---:|---:|---:|---:|
| 240 | swap2 120/120 | 33.475 ms | 28.469 ms | 85.05% | 5.006 ms |
| 480 | swap2 120/120 | 33.613 ms | 27.398 ms | 81.51% | 6.214 ms |
| 840 | swap2 120/120 | 33.753 ms | 27.185 ms | 80.54% | 6.568 ms |
| 960 | swap2 117 / swap3 3 | 35.114 ms | 27.654 ms | 78.76% | 7.460 ms |
| 1080 | swap3 120/120 | 86.514 ms | 53.555 ms | 61.90% | 32.959 ms |
| 1200 | swap3 120/120 | 52.640 ms | 31.646 ms | 60.12% | 20.994 ms |
| 1320 | swap3 120/120 | 60.946 ms | 39.674 ms | 65.10% | 21.273 ms |
| 1440 | swap3 120/120 | 51.874 ms | 32.210 ms | 62.09% | 19.665 ms |
| 1560 | swap3 120/120 | 56.479 ms | 34.489 ms | 61.07% | 21.989 ms |
| 1680 | swap3 120/120 | 53.169 ms | 32.894 ms | 61.87% | 20.276 ms |

### Stable fast vs stable slow decomposition

Stable fast windows used:

- frame 240, 480, 600, 720, 840
- raw swap2 = 120/120 in each window

Mean:

- inter-signal: **33.722 ms**
- Waiting: **27.708 ms/signal**
- residual: **6.014 ms/signal**

Stable slow windows used:

- frame 1200, 1320, 1440, 1560, 1680
- raw swap3 = 120/120 in each window

Mean:

- inter-signal: **55.022 ms**
- Waiting: **34.183 ms/signal**
- residual: **20.839 ms/signal**

Slow-minus-fast increase:

- inter-signal: **+21.299 ms**
- Waiting: **+6.474 ms**
- residual: **+14.825 ms**

At this aggregate level, about 70% of the stable inter-signal slowdown increment lands in the current Stage C `residual`, and about 30% lands in additional KThread Waiting.

This is attribution of the measured interval, not yet a root-cause percentage claim.

## Waker wait reasons

For `tid=0x4f`, named reasons are essentially absent:

- Sleep: `0`
- Synchronization: `0`
- ConditionVar: `0`
- Arbitration: `0`
- Suspended: `0`
- IPC: only a few milliseconds total per 120-frame report, negligible per signal

Nearly all recorded Waiting time is reason `None`.

Examples:

- frame 840: `none=3259.908 ms`, `ipc=2.272 ms`
- frame 1200: `none=3792.149 ms`, `ipc=5.430 ms`
- frame 1320: `none=4757.335 ms`, `ipc=3.515 ms`
- frame 1680: `none=3943.289 ms`, `ipc=3.937 ms`

The number of `None` wait completions remains of the same general order rather than exploding in slow mode. Typical average `None` event duration rises from roughly 1.1-1.25 ms in fast windows to roughly 1.3-1.7 ms in stable slow windows; frame1080 is a transient extreme at about 2.39 ms/event.

## Important semantic caution about `None`

Exact dc95 defines `ThreadWaitReasonForDebugging::None` as "Thread is not waiting", but the Stage C profiler only accumulates a reason when the KThread old state is actually `ThreadState::Waiting`.

Therefore Stage C `none=...` does **not** mean CPU/runnable time. It means:

> the thread was in KThread `Waiting`, but the debug wait-reason field was `None` at the exit transition.

Exact dc95 has direct `BeginWait(...)` paths which do not assign a debug wait reason, including pinned-thread waiter paths in `k_thread.cpp` and the process user-exception wait path in `k_process.cpp`. This proves `None` is not an exhaustive semantic owner label.

Do not claim those specific paths are the waker owner yet; current runtime does not identify the `None` wait call site.

## Signal guest PC / LR

Matching SignalToAddress context:

- PC is overwhelmingly **`0x85f16528`**.
- stable slow PC mismatch counts are only 0-4 per 120 signals.
- `latestPc` repeatedly returns `0x85f16528`.
- LR varies substantially; common/latest observed values include `0x85ee2b40` and `0x85ee2a8c`.

This strongly says the signal reaches one stable guest SVC site. However, because PC is captured at the SVC context, it may be the common SignalToAddress SVC wrapper rather than the higher-level producer call site. Current LR output only reports one reference plus mismatch count, so it is not enough to identify the dominant caller chain.

Do not symbolically name the PC/LR without a grounded module/callsite mapping.

## `lastWaitSvc`

`lastWaitSvc=0x0` throughout this run.

Treat current SVC-ID attribution as non-informative. It does not invalidate the KThread state-duration measurement.

## Stage C conclusion

Stage C rejects the simple hypothesis:

> `tid=0x4f` is delayed by another single named Arbitration / Synchronization / ConditionVar / Sleep wait before SignalToAddress.

Instead, in stable slow swap3 gameplay the waker's inter-signal interval expands from about 33.7 ms to about 55.0 ms and the increase is split between:

1. more time in **unclassified KThread Waiting (`reason=None`)**, and
2. a much larger **non-Waiting residual**.

The residual is **not yet equivalent to guest CPU work**. It can include both actual guest execution and runnable-but-unscheduled time.

Therefore Stage C narrows the causal frontier but does not yet identify the final producer function/root cause.

## Next causal frontier

Exact next questions:

1. Of the 20-21 ms stable-slow residual, how much is actual guest CPU time for the dynamically latched waker and how much is runnable/unscheduled scheduler delay?
2. Which exact dc95 `BeginWait` site owns the waker's large `reason=None` Waiting time?
3. What are the dominant guest LR/caller sites at matching SignalToAddress, rather than only PC plus mismatch count?

Recommended next stage must remain waker-only and observation-only:

- capture waker `GetCpuTime()` delta between consecutive matching signals;
- derive CPU time vs runnable/unscheduled residual;
- add fixed-enum attribution for only `reason=None` direct BeginWait sites, gated by the dynamically latched waker;
- collect a small fixed-size top-LR histogram at matching SignalToAddress;
- retain dynamic address and dynamic waker latch;
- no all-thread tracing, per-event flood, waits/sleeps/priority/core changes, or GPU/cadence behavior changes.
