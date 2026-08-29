# NEXT ACTION — Waker Stage E ARM64 Runtime

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current Stage E source branch:

`exp/x1-waker-stage-e-recursive-arbiter`

Never change the baseline without explicit approval.

ARM64 build authorization: **NONE**.

## Established through Stage D

Victim edge remains closed:

- dominant submitter / victim: `tid=0x53` in measured runs
- dynamic per-process victim AddressArbiter key
- `WaitIfEqual(timeout=-1)`
- matching waker: `tid=0x4f` in measured runs
- `SignalAndIncrementIfEqual(value=1,count=-1)`
- signal -> victim return essentially immediate

Stage D runtime `eden_log(20260829-024002).txt`:

| metric | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled | 0.239 ms | 0.307 ms | +0.068 ms |

Corrected wait shift:

- ConditionVar `17.252 -> 0.469 ms/signal`
- Arbitration `7.440 -> 32.339 ms/signal`

Therefore Stage E must explain the recursive AddressArbiter branch only. The separate CPU +14.28 ms branch remains open.

## Stage E implementation — COMPLETE / STATIC VALIDATED

New report:

`[X1-WAKERE]`

New source:

- `src/core/x1_waker_stage_e_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_e_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_e_attribution.py`

### Dynamic waker wait aggregation

No `tid=0x4f` hardcode.

Stage E reuses the Stage D dynamically latched waker identity and aggregates only that thread's `WaitForAddress` calls in a fixed 16-slot table by:

- address
- arbitration type
- value / timeout + variation counts
- call/completed count
- total / avg / max direct wait duration
- success / timeout / other result

### One-key recursive promotion

Every 120 rendered frames Stage E selects the waker wait key with the largest direct wait duration.

Only that top key is promoted for matching `SignalToAddress` owner attribution in the following report window.

This creates an intentional one-window discovery lag. Do not interpret the first `[X1-WAKERE]` block as having complete recursive signal-owner data.

### Recursive signal-owner fields

For only the promoted key Stage E reports:

- signaler guest TID
- signal type
- value/count + variation counts
- signal calls
- signals occurring during the active promoted wait
- wait-start -> signal (`w2s`) avg/max
- signal -> waker-return (`s2e`) avg/max
- no-active / no-signal-return / overflow sanity

### CPU branch

CPU-by-LR interval partitioning was intentionally deferred to keep Stage E causally narrow. Existing Stage D CPU and signal-LR observations remain the separate CPU branch.

## Static validation

Ubuntu-only run:

- run `33230000239`
- job `99041006308`
- attempt `1`
- conclusion `success`

Passed:

- exact dc95
- retained chain
- Stage A-D reconstruction
- Stage E application
- `git diff --check`
- Python compile + analyzer smoke test
- no hardcoded `0x4f`
- no hardcoded process-specific `0x210...` wait address
- original `WaitAddressArbiter` call count preserved
- original `SignalAddressArbiter` call count preserved
- validation helpers preserved
- exactly one Stage E BeginWait / EndWait / RecordSignal hook
- no kernel wait insertion
- no scheduler priority/affinity mutation
- no GPU/swap/cadence behavior mutation

Temporary Ubuntu workflow was removed after success.

## Exact next action

Only after fresh explicit authorization for exactly one ARM64 attempt:

1. build current Stage E branch against exact dc95;
2. no automatic retry/rerun;
3. run the same TOTK 1.2.1 field scenario long enough to contain stable swap2 and stable swap3 windows;
4. collect at minimum:
   - `[X1-WAKERE]`
   - `[X1-WAKERD]`
   - `[X1-ADDRSIG]`
   - `[X1-ADDRARB]`
   - raw QueueBuffer cadence;
5. compare pure swap2 and pure swap3 120-frame blocks.

## Runtime decision tree

### A. One waker wait key owns most slow Arbitration

If Stage E `top0` direct wait time reconciles with the Stage D slow Arbitration bucket, follow only that key.

If its promoted-key `w2s` is almost the entire direct wait and `s2e` is tiny, move the causal frontier to the recursive signaler TID before its signal.

### B. Dominant key switches at slow transition

Treat the key switch itself as a regime change and attribute the new key's release owner. Do not assume the fast key remains causal.

### C. Several keys share the time

Keep only enough top contributors to explain most of the Stage D Arbitration total. Do not broaden to arbitrary waits.

### D. No direct WaitForAddress reconciliation

Audit Stage D corrected reason mapping before any optimization.

### E. Recursive wait edge is real but does not explain CPU +14 ms

Keep the CPU branch separate and later use the existing LR correlation for a focused CPU-path attribution step.

## Hard prohibitions

- no ARM64 build/rerun without fresh explicit approval; one approval = one attempt
- no automatic retry
- no hardcoded waker TID
- no hardcoded absolute guest wait address
- no all-thread scheduler tracing
- no all-SVC profiler
- no broad PC sampler
- no per-event log flood
- no sleep/wait insertion
- no priority/core-affinity changes
- no GPU/BufferQueue/cadence behavior changes
- no baseline change
