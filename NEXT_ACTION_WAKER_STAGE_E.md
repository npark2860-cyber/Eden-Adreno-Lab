# NEXT ACTION — Waker Stage E Recursive AddressArbiter Attribution

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-d-cpu-scheduler`

Never change the baseline without explicit approval.

ARM64 build authorization: **NONE**.

## Established through Stage D

Victim edge:

- dominant submitter / victim in measured runs: `tid=0x53`
- per-run dynamic victim AddressArbiter key
- `WaitIfEqual(timeout=-1)`
- matching waker in measured runs: `tid=0x4f`
- `SignalAndIncrementIfEqual(value=1, count=-1)`
- signal -> victim return essentially immediate

Stage D stable-block result from `eden_log(20260829-024002).txt`:

| metric | raw swap2 | raw swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| residual | 7.748 ms | 22.075 ms | +14.327 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled | 0.239 ms | 0.307 ms | +0.068 ms |

Therefore:

- runnable-unscheduled is not the owner;
- true None wait sites are all zero;
- CPU execution increases materially;
- corrected Waiting also increases materially.

Most important corrected reason shift:

- ConditionVar: `17.252 -> 0.469 ms/signal`
- Arbitration: `7.440 -> 32.339 ms/signal`

Slow corrected Waiting is ~92.7% Arbitration.

The signal guest PC remains stable at `0x85a03528`. The same two dominant signal LR contexts remain, but `0x859cfa8c` rises from ~17.8% in stable fast to ~30.7% in stable slow.

## Stage E question

> Which AddressArbiter wait performed by the dynamically identified waker owns the slow-regime Arbitration expansion, and which guest thread releases that wait?

Keep the CPU branch separately quantified; do not assume the Arbitration edge explains the entire +23.5 ms slowdown.

## Stage E narrow instrumentation

### A. Dynamically identify waker-owned WaitForAddress calls

Do **not** hardcode `tid=0x4f`.

Reuse the existing dynamically latched matching-signal waker TID.

Observe only `WaitForAddress` calls made by that thread and aggregate by:

- guest address
- arbitration type
- value
- timeout
- call count / completed count
- total / avg / max duration
- success / timeout / other result

Use a fixed small slot table; no per-event log flood.

The purpose is to identify which address/type owns the Stage D corrected Arbitration time, especially in pure raw swap3 blocks.

### B. Recursively attribute the dominant waker AddressArbiter release

Once one dominant waker wait key is identified dynamically in the current run, observe matching `SignalToAddress` calls to that key and aggregate:

- signaler guest TID
- signal type
- value / count
- wait-start -> signal
- signal -> waker wait-return
- missing/no-active/overflow sanity

This is the same causal method that closed Stage B, but applied one edge upstream.

Do not recursively track arbitrary addresses. Only the dominant current-run waker wait key should be promoted into signal-owner attribution.

### C. Preserve the CPU branch with LR correlation only

Do not add broad PC sampling or all-SVC tracing yet.

For the existing top matching-signal LR contexts, if cheap, aggregate the completed signal-to-signal interval by the LR observed at the interval-ending matching signal:

- interval count
- inter-signal avg/max
- corrected Waiting avg
- Arbitration avg
- estimated CPU avg
- runnable-unscheduled avg

This is intended only to test whether the increased slow CPU work is associated with `0x859cfb40`, `0x859cfa8c`, or neither.

If this correlation is not cheap or would materially complicate Stage E, prioritize the recursive AddressArbiter edge first and leave CPU-LR partitioning for a separate static step.

## Decision tree

### A. One waker AddressArbiter key dominates slow Arbitration

Follow only its matching signal owner.

If its signal->waker-return latency is tiny, move the frontier to that producer thread before its signal, exactly as Stage B did.

### B. Several waker AddressArbiter keys share the time

Keep only the top contributors needed to explain most of the slow Arbitration total. Do not broaden to all waits.

### C. No direct waker WaitForAddress reconciles with Stage D Arbitration

Treat this as an instrumentation inconsistency and audit reason-to-SVC mapping before any optimization.

### D. CPU-LR correlation identifies one caller context

That caller becomes the later CPU-path target, but do not merge it with the AddressArbiter producer branch unless runtime evidence shows they are the same causal path.

## Hard prohibitions

- no ARM64 build/rerun without fresh explicit approval; one approval = one attempt
- no hardcoded `tid=0x4f`
- no hardcoded absolute guest wait address across process launches
- no all-thread scheduler trace
- no all-SVC profiler
- no broad PC sampler
- no per-event log flood
- no sleep/wait insertion
- no priority/core-affinity changes
- no GPU/BufferQueue/cadence behavior changes
- no baseline change

## Immediate work allowed without ARM64 approval

- implement Stage E source narrowly
- inspect exact dc95 diff
- run Ubuntu/static validation
- update documentation

After Stage E source/static validation is complete, stop and request a fresh explicit authorization for exactly one ARM64 attempt.
