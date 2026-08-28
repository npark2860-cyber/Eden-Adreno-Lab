# CURRENT HANDOFF — Eden Adreno X1 Waker Pre-Signal Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-pre-signal-attribution`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C implementation record: `DEBUG_HISTORY_20260828_WAKER_STAGE_C_IMPLEMENTED.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest ARM64 build — Stage B SUCCESS

Dynamic-address Stage B build:

- run `33168281215`
- job `98838856202`
- attempt `1`
- build branch `exp/x1-address-arbiter-signal-owner-build`
- build HEAD `b2dbc9dbe7cb69a5856850d5d60750355f186b19`
- conclusion `success`
- artifact `Eden-dc95-X1-address-arbiter-dynamic-latch`
- artifact id `9685245645`
- size `31,385,379` bytes
- SHA-256 `a421cb6beaa7528ba024a1fee943c2c9a80bbb353142963e0391d2d00e67cfd7`

The temporary Stage B ARM64 workflow was removed after success. No rerun occurred.

The persistent workflow on the source branch remains manual-only (`workflow_dispatch`).

## Closed causal chain retained

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe remains rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is mapped adaptive fast stream; payload repeats heavily but blind lifetime reuse remains unsafe.
- classic-cache fallback did not break the gameplay ceiling.
- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- swap3->effective2 clamp and DFPS experiments did not raise upstream production rate.
- BufferQueue free-slot/backpressure is closed as primary owner.
- slow Frame Build is roughly 48-55 ms/frame while measured Vulkan scopes explain only a minority.
- GPU worker is mostly starved in queue wait; active GPU-command work is not the missing interval.
- long inter-submit gap exists before NVDRV handler entry; handler/SubmitGPFIFO/locks/fence/syncpoint are tiny.
- dominant guest submitter is the runtime thread observed as `tid=0x53` in the Stage A/B runs, with CPU share about 1-2%.
- NVDRV IPC dispatch is about 0.02-0.03 ms/request; host service scheduling is not the missing owner.
- post-submit interval is generally 96-99% guest KThread `Waiting`.

## Address Arbiter Stage A — COMPLETE

Stage A proved one stable gameplay wait key within each process:

- victim / dominant submitter in tested runs: `tid=0x53`
- operation: `WaitIfEqual` (`ArbitrationType=2`)
- timeout: `-1`
- one active gameplay key
- direct `WaitForAddress` duration reconciles essentially one-for-one with reason-level `Arbitration`.

The absolute guest address is **not process-invariant**. Observed across runs:

- `0x210adbc120`
- `0x210b5bc120`
- `0x210b1bc120`

The profiler therefore dynamically latches the current run's first post-warmup target-thread `WaitIfEqual(timeout=-1)` address.

## Address Arbiter Stage B — COMPLETE

Runtime:

`eden_log(20260828-122253).txt`

This run dynamically latched:

- victim: `tid=0x53`
- wait address: `0x210b1bc120`
- wait: `WaitIfEqual`
- timeout: `-1`
- sole observed matching waker: `tid=0x4f`
- signal type: `SignalAndIncrementIfEqual` (`incEq`)
- value: `1`, stable
- count: `-1`, stable
- normal gameplay: one matching signal per rendered frame
- missing/no-active/overflow: `0`

Representative slow timing:

| frame | direct wait avg | wait -> signal (`w2s`) | signal -> return (`s2e`) |
|---:|---:|---:|---:|
| 1800 | 70.368 ms | 70.270 ms | 0.098 ms |
| 1920 | 40.185 ms | 40.177 ms | 0.008 ms |
| 2040 | 45.026 ms | 45.020 ms | 0.007 ms |
| 2160 | 50.797 ms | 50.778 ms | 0.019 ms |

Therefore:

> The 40-70 ms slow-regime delay occurs before the matching signal. Once the waker signals, the victim returns essentially immediately. The causal frontier is the signal-owner thread before `SignalToAddress`, not AddressArbiter wake-completion latency.

## Stage C — IMPLEMENTED / STATIC-VALIDATED

Current branch:

`exp/x1-waker-pre-signal-attribution`

New source:

- `src/core/x1_waker_pre_signal_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_pre_signal_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_pre_signal_attribution.py`

Stage C does **not** hardcode the observed `tid=0x4f`.

The first signal that already matches Stage B's dynamically latched target address atomically latches its current guest TID as the current-run waker. Only that TID is then observed between consecutive matching signal entries.

Primary report:

`[X1-WAKER]`

It records per 120 rendered frames:

- dynamically latched waker TID
- matching signal count
- matching signal-entry -> next matching signal-entry total/avg/max
- waker KThread waiting duration and wait-reason breakdown
- non-wait residual (`inter-signal - attributed wait`)
- last wait SVC id
- guest PC/LR at matching `SignalToAddress` entry, reference plus mismatch counts and latest values
- sanity counters for waits, malformed intervals and alternate signaler TIDs

The PC/LR are read-only from the current guest thread's saved `ThreadContext` at the matching SVC entry.

No new checkbox was added. Stage C is gated by the existing `X1 Log: Address Arbiter Attribution` control.

### Static validation — SUCCESS

Ubuntu-only run:

- run `33172180578`
- job `98851759971`
- conclusion `success`

Passed:

- exact dc95 reconstruction
- Stage B dynamic-address reconstruction
- Stage C transplant/analyzer Python compile
- Stage C application
- exact dc95 HEAD preservation
- `git diff --check`
- no hardcoded `0x4f`
- original `WaitAddressArbiter` / `SignalAddressArbiter` counts unchanged
- existing AddressArbiter `RecordSignal` count unchanged
- core KThread state-store / scheduler callback / existing wait-token counts unchanged
- behavior-changing wait/signal/scheduling/GPU-policy diff guard

The temporary Ubuntu workflow was deleted after success.

Net Stage C source diff from parent `6bc91809fd81ee973935ca463ac187ed9f1d571f` contained only the three Stage C source/analyzer files before this documentation update.

## Current causal frontier

Exact runtime question after Stage C ARM64 build:

> During the long 40-70 ms inter-signal interval, is the dynamically latched waker itself blocked in a specific KThread wait reason, or is most of the interval non-wait/runnable residual? Does the matching `SignalToAddress` PC/LR remain one stable guest call site?

Interpretation:

- if one wait reason expands with the slow regime, follow only that waker wait path next;
- if wait share stays small and non-wait residual expands, move upstream into the waker's guest execution path/call site;
- if PC/LR change by regime, split by the observed call sites before going deeper;
- if PC/LR are stable, the delay is upstream of one stable signal site.

Do not chase `None` in parallel unless a controlled stable-slow window shows the proven waker-before-signal interval is small while the frame remains slow.

## ARM64 status

Stage C is **not ARM64-built yet**.

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
