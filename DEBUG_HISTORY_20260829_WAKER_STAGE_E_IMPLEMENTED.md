# DEBUG HISTORY — Waker Stage E Implemented / Static Validated

Date: 2026-08-29 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage E branch:

`exp/x1-waker-stage-e-recursive-arbiter`

ARM64 authorization remained **NONE** throughout Stage E implementation/static validation. No ARM64 build or rerun was triggered.

## Runtime input retained from Stage D

Runtime:

`eden_log(20260829-024002).txt`

Established stable-block split:

| metric | raw swap2 | raw swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| residual | 7.748 ms | 22.075 ms | +14.327 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled | 0.239 ms | 0.307 ms | +0.068 ms |

Corrected wait-reason mode shift:

- ConditionVar: `17.252 -> 0.469 ms/signal`
- Arbitration: `7.440 -> 32.339 ms/signal`

Therefore Stage E addresses only the upstream AddressArbiter branch. The separate +14.28 ms CPU branch remains open and must not be collapsed into the recursive wait edge without runtime evidence.

## Stage E implementation

New source:

- `src/core/x1_waker_stage_e_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_e_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_e_attribution.py`

New report:

`[X1-WAKERE]`

### A. Dynamic-waker WaitForAddress aggregation

Stage E does not hardcode the observed `tid=0x4f`.

At every `WaitForAddress` SVC call, Stage E asks the existing Stage D profiler whether the current thread is the dynamically latched matching-signal waker. Only that thread is observed.

A fixed 16-slot table aggregates by:

- guest address
- arbitration type
- reference value + variation count
- reference timeout + variation count
- call / completed count
- total / average / max direct wait duration
- success / timeout / other result

No per-event logging was added.

### B. One-key recursive promotion

At each 120-rendered-frame report, Stage E ranks the dynamic waker's WaitForAddress keys by direct wait duration.

Only the top-duration key is promoted for recursive signal-owner attribution in the following report window.

This intentionally creates a one-window discovery lag:

- current window identifies the dominant waker wait key;
- next window attributes only matching `SignalToAddress` calls for that promoted key.

Stage E never recursively tracks all observed addresses in parallel.

The promoted key is process-dynamic and may switch if a different waker wait key becomes dominant in a later report block. Promotion switches are reported explicitly.

### C. Recursive signal-owner attribution

For only the currently promoted waker wait key, Stage E aggregates matching `SignalToAddress` by:

- signaler guest TID
- signal type
- reference value / count and variation counts
- matching signal calls
- signals occurring while the promoted waker wait is active
- wait-start -> signal (`w2s`) average/max
- signal -> waker wait return (`s2e`) average/max
- signal-with-no-active-wait sanity
- promoted wait returns without a matched signal
- signal-slot overflow

This is the same causal method used in Stage B, moved one AddressArbiter edge upstream.

### D. CPU branch intentionally not expanded in Stage E

`NEXT_ACTION_WAKER_STAGE_E.md` allowed cheap CPU/LR interval partitioning if it did not materially complicate the recursive AddressArbiter work.

It was intentionally deferred.

Reason:

- the Stage D CPU branch is already independently quantified;
- Stage E's primary purpose is to identify/release-owner the ~32 ms slow Arbitration branch;
- adding interval-by-LR CPU accounting would increase concurrency/state complexity in the same patch and make causal validation less clean.

The existing Stage D LR correlation remains available for a later focused CPU step if the recursive wait edge does not explain the full slowdown.

## Observation-only invariants

Stage E changes only observation around existing SVC calls and rasterizer report cadence.

It does not:

- add/remove/duplicate `WaitAddressArbiter` calls
- add/remove/duplicate `SignalAddressArbiter` calls
- change `IsValidArbitrationType`
- change `IsValidSignalType`
- add kernel waits
- alter scheduler priority or core masks
- alter GPU/BufferQueue/cadence behavior
- hardcode `0x4f`
- hardcode an absolute `0x210...` guest wait address

## Ubuntu static validation

One-shot Ubuntu-only workflow:

- run `33230000239`
- job `99041006308`
- conclusion `success`
- attempt `1`

Passed:

- exact dc95 checkout
- retained diagnostic chain reconstruction
- focused Stage A through D reconstruction
- pre-Stage-E invariant snapshot
- Stage E application
- exact dc95 HEAD preservation
- `git diff --check`
- Python compile for Stage D/E transplant + analyzers
- dynamic Stage D waker predicate present
- fixed 16-slot waker wait aggregation present
- one-key promotion markers present
- recursive matching-signal markers present
- no hardcoded `0x4f`
- no hardcoded process-specific `0x210...` wait address
- original `WaitAddressArbiter(address...)` call count preserved
- original `SignalAddressArbiter(address...)` call count preserved
- `IsValidArbitrationType` occurrence count preserved
- `IsValidSignalType` occurrence count preserved
- exactly one Stage E BeginWait hook
- exactly one Stage E EndWait hook
- exactly one Stage E promoted-key RecordSignal hook
- no added kernel BeginWait/EndWait, priority/core-affinity mutation, scheduler yield/reschedule, GPU/swap behavior mutation
- Stage E analyzer synthetic-log smoke test

The temporary Ubuntu workflow was removed immediately after success.

## Runtime question now ready

A Stage E ARM64 runtime, only after fresh explicit one-attempt authorization, should answer:

1. which dynamic-waker WaitForAddress address/type accounts for most of the slow corrected Arbitration time;
2. whether one key dominates both fast and slow or a different key becomes dominant in swap3;
3. which guest TID signals the promoted key;
4. whether `w2s` explains the promoted direct wait duration and `s2e` remains tiny;
5. whether the recursive release owner is stable enough to move the causal frontier one guest thread upstream.

The separate Stage D CPU +14.28 ms branch remains open regardless of the Stage E wait result.
