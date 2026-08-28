# DEBUG HISTORY — X1 Waker Pre-Signal Attribution Stage C Implemented

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- source branch: `exp/x1-waker-pre-signal-attribution`
- parent Stage B source HEAD: `6bc91809fd81ee973935ca463ac187ed9f1d571f`
- ARM64 authorization during this implementation: **NONE**

## Why Stage C exists

Stage B runtime `eden_log(20260828-122253).txt` proved:

- victim / dominant submitter: `tid=0x53`
- current-run wait address: `0x210b1bc120`
- wait: `WaitIfEqual`, timeout `-1`
- sole observed matching signal owner: `tid=0x4f`
- signal: `SignalAndIncrementIfEqual`, value `1`, count `-1`
- the slow 40-70 ms wait is almost entirely `wait -> signal`; `signal -> return` is near-zero.

Therefore the next causal owner is the signal-owner thread before it reaches the matching `SignalToAddress`.

## Stage C implementation

New profiler:

`src/core/x1_waker_pre_signal_profiler.h`

New transplant:

`tools/adreno_lab/transplant_dc95_waker_pre_signal_attribution.py`

New analyzer:

`tools/adreno_lab/analyze_x1_waker_pre_signal_attribution.py`

The profiler is gated by the existing `X1 Log: Address Arbiter Attribution` setting. No new runtime control is added.

### Dynamic waker latch

Stage C does **not** hardcode `tid=0x4f`.

At the first `SignalToAddress` that already matches Stage B's dynamically latched target address, the profiler atomically latches that call's guest thread ID as the current-run waker. Other signaler TIDs are counted as `wakerSwitch` and are not retargeted automatically.

### Measurement boundary

Stage C uses:

`matching SignalToAddress entry -> next matching SignalToAddress entry`

This is intentionally entry-to-entry rather than wrapping `SignalAddressArbiter`, so the original signal call and result semantics remain untouched. The prior signal call's own tiny execution time is therefore included in the next inter-signal interval.

### Waker-only state attribution

Only the dynamically latched waker thread is observed in the existing `KThread::SetState` transition point.

For each closed inter-signal interval, Stage C records:

- inter-signal total / average / maximum
- KThread `Waiting` duration
- wait-reason totals/counts for `None`, `Sleep`, `IPC`, `Synchronization`, `ConditionVar`, `Arbitration`, `Suspended`
- non-wait residual = inter-signal duration minus attributed wait duration
- last wait SVC id
- wait begin/end sanity counters

The residual is the runnable/CPU/non-wait remainder; it is not itself proof of active guest instruction execution.

### Signal call-site attribution

At matching `SignalToAddress` entry, Stage C reads the current guest thread's saved `ThreadContext` read-only:

- `pc`
- `lr`

Per 120-frame report it records the first PC/LR reference and mismatch counts plus latest PC/LR. This distinguishes a stable signal call site from regime-dependent call-site changes without broad guest tracing.

Primary log line:

`[X1-WAKER]`

## Scope / semantics

No new:

- wait/sleep/lock
- thread priority/core change
- scheduler policy change
- generic all-thread tracing
- generic all-SVC tracing
- SignalToAddress address/type/value/count modification
- NVDRV/GPU/BufferQueue/HWC/VI/cadence/swap behavior change

## Static validation

Ubuntu-only one-shot run:

- run `33172180578`
- job `98851759971`
- conclusion `success`

Validation recreated the retained diagnostic chain on exact dc95, applied Stage B dynamic-address attribution, then applied Stage C.

Passed checks included:

- Python compile for Stage C transplant/analyzer
- exact Eden HEAD remains `dc95cd09eea9749250fe31a3072684d341d19417`
- `git diff --check`
- no hardcoded `0x4f` in Stage C profiler
- required `[X1-WAKER]`, dynamic latch, wait attribution, PC/LR markers present
- original `WaitAddressArbiter` and `SignalAddressArbiter` call counts unchanged across Stage C
- existing AddressArbiter `RecordSignal` call count unchanged
- core KThread state-store / scheduler callback / wait tokens unchanged across Stage C
- behavior-changing wait/signal/scheduling/GPU-policy tokens rejected from Stage C diff

The temporary Ubuntu workflow was deleted after success.

Net source diff from Stage B parent contains only:

- `src/core/x1_waker_pre_signal_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_pre_signal_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_pre_signal_attribution.py`

## Current status

Stage C is **implemented and statically validated** but **not ARM64-built**.

Current ARM64 authorization: **NONE**.

Next after fresh one-attempt authorization:

1. build exact dc95 + retained chain + Stage B + Stage C once on Windows ARM64;
2. run the same controlled TOTK 1.2.1 scenario;
3. inspect `[X1-WAKER]` against `[X1-ADDRSIG]`, `[X1-ADDRARB]`, GuestWait and cadence;
4. decide whether the late waker interval is owned by a specific wait reason or by the non-wait residual, and whether PC/LR remain stable.
