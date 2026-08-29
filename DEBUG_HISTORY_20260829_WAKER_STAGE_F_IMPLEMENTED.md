# DEBUG HISTORY — Waker Stage F Producer Attribution

Updated: 2026-08-29 KST

## Basis

Stage E runtime `eden_log(20260829-063358).txt` established:

- dynamic waker `tid=0x4f` spends most slow Arbitration time on promoted key `0x210b05b39c` in that run;
- the promoted key is repeatedly released by two dominant guest signalers observed as `tid=0x80` and `tid=0x81`;
- fast w2s is roughly 0.5 ms, slow w2s roughly 2-3 ms;
- signal -> waker return remains about 0.01 ms or less;
- absolute TIDs and guest address are runtime observations only and are not valid hardcoded selectors.

The separate Stage D dynamic-waker CPU growth branch remains open.

## Branch

`exp/x1-waker-stage-f-producer-attribution`

Created from Stage E runtime-recorded HEAD:

`976430bb33ae40d6f8daa84513d3a82e577a4a76`

Fixed Eden baseline remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

## New files

- `src/core/x1_waker_stage_f_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_f_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_f_attribution.py`

New report:

`[X1-WAKERF]`

## Design

### Dynamic candidate discovery

Stage F observes only signals that Stage E already recognizes as targeting its currently promoted AddressArbiter key.

A fixed 16-slot candidate table aggregates `(promoted address, signaler TID)` signal counts. No runtime-observed TID or address is hardcoded.

Every 120 rendered frames Stage F:

1. finds the promoted address with the largest candidate signal count in the completed window;
2. selects the top two signaler TIDs for that address;
3. arms only those two producers for the following window.

This intentionally creates a one-window discovery/arming lag, matching the causal discipline used by Stage E.

If the Stage E promoted key changes, Stage F can reselect both address and producer TIDs dynamically. Producer interval anchors are reset only when tracking identity changes.

### Producer signal-to-signal split

For each of the two armed producer threads, each promoted-key signal samples read-only:

- `KThread::GetCpuTime()`
- `CoreTiming().GetClockTicks()`
- priority
- active core
- current core

The signal-to-signal interval is split into:

- inter-signal wall time
- completed KThread Waiting time
- residual
- estimated guest CPU time using the same CPU-tick / CoreTiming scaling method as Stage D
- runnable-unscheduled = `max(residual - CPU, 0)`

The same Stage D caveat applies: `GetCpuTime()` is context-switch-accounted, so interpret 120-frame aggregates rather than individual intervals.

### Corrected wait reason

Stage F observes KThread state transitions only for the two currently armed producer TIDs.

Completed wait reason is classified as:

`exit reason if non-None, otherwise entry reason fallback`

and accumulated into:

- None
- Sleep
- IPC
- Synchronization
- ConditionVar
- Arbitration
- Suspended

No Stage F direct true-None-site sub-classification was added. If true None becomes material at runtime, audit that branch separately rather than broadening this stage preemptively.

### Explicitly deferred

Stage F does not add:

- producer PC/LR sampler
- broad all-thread scheduler trace
- all-SVC profiler
- per-event logging
- any priority/core-affinity mutation
- any wait/sleep insertion
- any GPU/BufferQueue/cadence behavior change

Producer CPU callsite attribution is deferred until runtime proves CPU growth dominates.

## Ubuntu static validation

One-shot workflow:

- run `33239570435`
- job `99066457540`
- attempt `1`
- conclusion `success`

Passed:

- exact dc95 checkout and HEAD preservation
- retained non-scheduler patch reconstruction
- retained diagnostic chain recreation
- focused attribution recreation through Stage C
- Stage D application
- Stage E application
- pre-Stage-F snapshot
- Stage F application
- `git diff --check`
- Stage F transplant/analyzer `py_compile`
- `[X1-WAKERF]` marker
- exactly two producer slots
- 16 candidate slots
- dynamic selection path present
- no hardcoded observed `0x80` / `0x81`
- no hardcoded process-specific `0x210...` address
- no producer LR sampler / guest LR field
- exactly one Stage F promoted-signal hook
- exactly one Stage F KThread transition hook
- exactly one Stage F initialize hook
- exactly one Stage F frame-report hook
- original `WaitAddressArbiter` call count preserved vs pre-F
- original `SignalAddressArbiter` call count preserved vs pre-F
- arbitration/signal validation-helper counts preserved vs pre-F
- no Stage-F-added kernel BeginWait/EndWait/yield/reschedule/priority/core-mask behavior
- no Stage-F-added QueueBuffer/swap/fence behavior
- analyzer synthetic-log smoke test for both producer rows

Temporary Ubuntu workflow was deleted after success.

## Runtime decision map

A. Producer CPU dominates slow-fast growth:

> follow only the selected producer CPU path with a focused callsite attribution stage.

B. Producer Waiting dominates:

> follow only the dominant corrected wait reason and its release owner.

C. Runnable-unscheduled dominates:

> reopen scheduling/core competition only for the dynamically selected producer threads.

D. Mixed:

> keep components quantified; do not collapse the producer branch prematurely.

Regardless of Stage F result, keep the separate Stage D `tid=0x4f` CPU-growth branch open until explicitly attributed.

## ARM64 state

No Stage F ARM64 build was triggered during implementation/static validation.

Current ARM64 authorization: NONE.
