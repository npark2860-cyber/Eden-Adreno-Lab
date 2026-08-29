# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-e-recursive-arbiter`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime record: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D implementation/build record: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- Stage D runtime record: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E implementation/static record: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_IMPLEMENTED.md`
- next action: `NEXT_ACTION_WAKER_STAGE_E.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest ARM64 build — Stage D SUCCESS

- run `33217783844`
- job `99005198468`
- attempt `1`
- branch `exp/x1-waker-stage-d-cpu-scheduler`
- build HEAD `faf518e70811ba9f0c1a754c14d5da8584753904`
- exact Eden source `dc95cd09eea9749250fe31a3072684d341d19417`
- conclusion `success`
- artifact `Eden-dc95-X1-waker-stage-d`
- artifact id `9704658049`
- size `31,387,303` bytes
- SHA-256 `cd7e8e2f218a522ad9a90e8ccff8170461be1d40732c15bcf24bd0ebc1cef7b5`

No rerun occurred. Persistent ARM workflow remains manual-only `workflow_dispatch`.

## Closed causal chain retained

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe remains rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is mapped adaptive fast stream; heavy payload repeat does not make blind lifetime reuse safe.
- classic-cache fallback did not break the gameplay ceiling.
- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- swap3->effective2 clamp and DFPS did not raise upstream production rate.
- BufferQueue free-slot/backpressure is closed as primary owner.
- GPU worker is mostly starved for command supply; active GPU-command work is not the missing interval.
- long inter-submit gap exists before NVDRV handler entry; handler/SubmitGPFIFO/locks/fence/syncpoint are tiny.
- dominant guest submitter in tested runs = `tid=0x53`, CPU share about 1-2%.
- NVDRV IPC dispatch is about 0.02-0.03 ms/request; host service scheduling is not the missing owner.

## Address Arbiter Stage A — COMPLETE

Dominant submitter waits on one stable per-process gameplay AddressArbiter key:

- victim / submitter: `tid=0x53` in tested runs
- operation: `WaitIfEqual`
- timeout: `-1`
- direct `WaitForAddress` duration reconciles with reason-level `Arbitration`.

Absolute guest VA relocates across launches, so the profiler dynamically latches the current run's target address.

## Address Arbiter Stage B — COMPLETE

Measured edge:

- victim `tid=0x53`
- sole matching waker `tid=0x4f` in measured runs
- signal `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- normal gameplay one matching signal per rendered frame
- `direct WaitForAddress ~= wait-start -> matching-signal (w2s)`
- signal -> victim return (`s2e`) essentially zero

Therefore the long victim wait occurs before the waker signals.

## Stage C — RUNTIME COMPLETE

Runtime:

`eden_log(20260828-173023).txt`

Stage C established the dynamic waker signal-to-signal total split only.

Stable fast:

- inter-signal `33.722 ms`
- total Waiting `27.708 ms`
- residual `6.014 ms`

Stable slow:

- inter-signal `55.022 ms`
- total Waiting `34.183 ms`
- residual `20.839 ms`

Its old named wait-reason breakdown is invalid because exact dc95 often assigns the debug wait reason after `BeginWait`.

## Stage D — RUNTIME COMPLETE

Runtime:

`eden_log(20260829-024002).txt`

Measured identity:

- exact dc95
- dynamic victim address `0x210b1bc120`
- victim `tid=0x53`
- dynamic waker `tid=0x4f`
- waker switches `0`
- matching signal guest PC `0x85a03528`
- waker priority `44`
- latest active/current core `0/0`
- malformed CPU/wait/interval `0`

Stable block selection:

- pure swap2: frames `480, 600, 720, 840, 960, 1080, 1320, 1440`
- pure swap3: frames `1800, 1920, 2040, 2160, 2280`
- transition frame 1680 excluded

### Stage D aggregate split

| metric | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| residual | 7.748 ms | 22.075 ms | +14.327 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled | 0.239 ms | 0.307 ms | +0.068 ms |

**Runnable/scheduler starvation is closed for this slowdown.**

Slowdown is mixed:

- about +14.28 ms additional dynamic-waker CPU execution;
- about +9.19 ms additional Waiting;
- negligible runnable-unscheduled growth.

### Corrected wait-reason mode shift

Average corrected reason time per signal:

| reason | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| ConditionVar | 17.252 ms | 0.469 ms | -16.784 ms |
| Arbitration | 7.440 ms | 32.339 ms | +24.900 ms |
| Sleep | 0.996 ms | 1.358 ms | +0.362 ms |
| Synchronization | 0.019 ms | 0.687 ms | +0.668 ms |
| IPC | 0.023 ms | 0.038 ms | +0.015 ms |
| true None | 0.000 ms | 0.000 ms | 0.000 ms |

Stable slow corrected Waiting is ~92.7% Arbitration.

True None branch is closed: unknown / SetActivity pinned / SetCoreMask pinned / process user-exception are all zero.

Signal PC remains stable at `0x85a03528`; same two LR contexts remain. The second LR `0x859cfa8c` becomes more common in slow mode, but CPU-LR correlation is not yet causal proof.

## Stage E — IMPLEMENTED / STATIC VALIDATED

Current branch:

`exp/x1-waker-stage-e-recursive-arbiter`

New files:

- `src/core/x1_waker_stage_e_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_e_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_e_attribution.py`

New report:

`[X1-WAKERE]`

Stage E is observation-only and does not hardcode `tid=0x4f` or any process-specific absolute guest wait address.

### A. Dynamic-waker WaitForAddress aggregation

At each `WaitForAddress` call, Stage E reuses Stage D's dynamically latched waker identity and observes only that thread.

Fixed 16-slot aggregate fields:

- address
- arbitration type
- reference value / timeout and variation counts
- call / completed count
- total / average / max direct wait duration
- success / timeout / other result

No per-event log flood.

### B. One-key recursive promotion

Every 120 rendered frames Stage E ranks the dynamic waker's direct `WaitForAddress` keys by total duration.

Only the top key is promoted for recursive matching `SignalToAddress` owner attribution in the following report window.

This creates an intentional one-window discovery lag. First report selects the key; later stable reports carry its signal-owner timing.

Promotion may switch dynamically if a different key becomes dominant. Stage E never tracks arbitrary wait addresses recursively in parallel.

### C. Recursive signal-owner attribution

For only the promoted key Stage E aggregates:

- signaler guest TID
- signal type
- value / count + variation counts
- signal calls and calls during the active promoted wait
- wait-start -> signal (`w2s`) avg/max
- signal -> waker wait return (`s2e`) avg/max
- no-active / no-signal-return / overflow sanity

This moves the Stage B causal method exactly one AddressArbiter edge upstream.

### D. CPU branch remains separate

Stage E intentionally does not add CPU-by-LR interval partitioning. The Stage D +14.28 ms CPU branch is already independently quantified and remains open.

Do not merge the recursive wait producer with the CPU branch unless runtime evidence proves they are the same path.

## Stage E static validation

Ubuntu-only one-shot:

- run `33230000239`
- job `99041006308`
- attempt `1`
- conclusion `success`

Passed:

- exact dc95 checkout
- retained diagnostic chain reconstruction
- Stage A through D reconstruction
- Stage E application
- exact HEAD preservation
- `git diff --check`
- Python compile + analyzer smoke test
- no hardcoded observed waker TID
- no hardcoded process-specific guest wait VA
- original `WaitAddressArbiter` call count preserved
- original `SignalAddressArbiter` call count preserved
- validation helper occurrence counts preserved
- exactly one Stage E BeginWait hook
- exactly one Stage E EndWait hook
- exactly one Stage E promoted-key RecordSignal hook
- no kernel wait insertion
- no priority/core-affinity/scheduler mutation
- no GPU/swap/cadence behavior mutation

Temporary Stage E Ubuntu workflow was deleted after success.

## Current causal frontier — Stage E runtime

The next runtime question is:

> Which direct AddressArbiter wait made by the dynamically identified waker owns the ~32 ms slow Arbitration bucket, and which guest thread releases that promoted key?

Runtime decision:

1. if one `top0` direct wait reconciles with slow Stage D Arbitration, follow only that key;
2. if its `w2s` is essentially the direct wait and `s2e` tiny, move the frontier to its signaler TID before signal;
3. if dominant wait key changes between swap2 and swap3, treat the key switch as the regime change;
4. if several keys share time, retain only enough top contributors to explain most slow Arbitration;
5. if direct waits do not reconcile with corrected Arbitration, audit instrumentation before optimization;
6. regardless of result, keep the separate +14.28 ms CPU branch open until explicitly attributed.

See `NEXT_ACTION_WAKER_STAGE_E.md`.

## Actions state / ARM64 authorization

Persistent ARM workflow is manual-only `workflow_dispatch`.

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
