# NEXT ACTION — Waker Stage G ARM Build / Runtime

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-g-producer-cpu-attribution`

Pre-G repository snapshot:

`4281991be0790584247de71c071e04c4374a6d74`

Never change the exact Eden baseline without explicit approval.

## Stage G implementation state

Stage G implementation and Ubuntu static validation are complete.

Ubuntu validation:

- workflow: `Validate dc95 X1 Waker Stage G`
- run: `33242026006`
- job: `99072879855`
- attempt: `1`
- conclusion: `success`
- validation HEAD: `40b59fff8728ead7df503db6b7279ef5af297ff5`

Temporary Ubuntu workflow was deleted after success.

Persistent ARM workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current persistent workflow name:

`Build dc95 X1 Waker Stage G`

Trigger state:

`workflow_dispatch` only.

No Stage G ARM64 attempt has been made.

Current ARM64 authorization: **NONE**.

## Stage G measurement design now fixed

Stage G reuses only Stage F's dynamically armed two producer identities.

No runtime-observed TID or promoted guest VA is hardcoded.

At exact dc95 `KScheduler::SwitchThread`:

- Stage F identity check happens first.
- Only a selected producer has its saved guest `PC/LR` read.
- The PC/LR context receives the exact `tick_diff` that dc95 adds through `KThread::AddCpuTime()`.
- selected producer switch-in is recorded to pair a steady-clock slice duration with the completed CPU slice.

Aggregation:

- producer slots: `2`
- fixed PC/LR context slots per producer: `64`
- report cadence: `120` rendered frames
- top PC/LR contexts reported: `4`
- no per-switch logging
- no all-thread PC sampler
- no behavior mutation

Primary runtime quantity:

`cpuTicks`

This is in the exact scheduler/CoreTiming CPU-accounting domain used by Stage F `GetCpuTime()`.

`cpuWall` is a separate switch-in -> switch-out steady-clock sanity measurement; do not substitute it for Stage F's signal-interval CPU estimate.

## Immediate next action

Do nothing until the user gives a fresh explicit ARM64 authorization.

A fresh `ㄱㄱ` after the Stage G implementation/static report means:

> trigger exactly one Stage G ARM64 attempt using the persistent manual workflow on `exp/x1-waker-stage-g-producer-cpu-attribution`.

Rules:

- one authorization = exactly one ARM64 attempt
- no retry
- no rerun
- no second attempt after failure without another fresh authorization
- do not reinterpret older approvals
- do not change the baseline

## After a successful authorized ARM build

Record before runtime testing:

- workflow run ID
- job ID
- attempt number
- build HEAD
- exact dc95 verification result
- Stage G pre-configure verification result
- conclusion
- artifact name / ID / size / SHA-256
- explicit retry/rerun state

Then run the same TOTK 1.2.1 gameplay comparison used for Stage F with behavior-changing A/Bs OFF.

Capture enough clean `120`-frame windows to separate pure swap2 and pure swap3 periods.

Analyze together:

- `[X1-WAKERF]`
- `[X1-WAKERG]`
- raw QueueBuffer cadence

For each dynamically selected producer compare pure swap2 vs pure swap3:

- Stage F interval-count-weighted CPU trend
- Stage G total CPU ticks
- Stage G PC/LR tick shares
- unknown/overflow/missing/malformed/clock-mismatch counters
- priority/core sanity metadata

Do not use one context-switch slice or one report window as a causal conclusion.

## Runtime decision map

A. One/few PC/LR contexts gain most of the slow-mode producer CPU ticks:

> map those exact guest contexts to the guest execution/work path.

B. Slow-mode CPU tick growth is diffuse across many contexts:

> retain CPU as diffuse workload growth and move next to the already-open producer Arbitration branch.

C. Stage G CPU ticks fail to reconcile with the Stage F aggregate trend, or sanity counters are material:

> audit Stage G instrumentation before optimization.

## Open branches that must remain open

Do not erase either branch:

1. producer-side corrected Waiting remains ~96% Arbitration and grows by about `+2.38 / +2.88 ms` per producer interval in slow mode; after CPU attribution, recurse only the dominant producer `WaitForAddress` key/release owner.
2. the separate Stage D dynamic-waker CPU growth branch remains open and must not be merged with producer CPU without direct evidence.

No optimization is justified yet.
