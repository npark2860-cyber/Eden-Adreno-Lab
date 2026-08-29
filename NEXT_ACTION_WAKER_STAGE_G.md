# NEXT ACTION — Waker Stage G Focused Producer CPU Attribution

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-f-producer-attribution`

Never change the baseline without explicit approval.

ARM64 authorization: **NONE**.

## Stage F established

Runtime:

`eden_log(20260829-073615).txt`

Pure cadence blocks used:

- swap2: frames 480, 600, 720, 840, 960
- swap3: frames 1200, 1320, 1440
- frame 1080 excluded as transition: 13 swap2 / 107 swap3

Stage F dynamically tracked the same promoted address with two dominant producer TIDs observed in this run. These runtime identities must not be hardcoded.

Producer 0 aggregate slow-fast:

- inter `+6.074 ms`
- Waiting `+2.465 ms`
- residual `+3.610 ms`
- estimated guest CPU `+3.434 ms`
- runnable-unscheduled `+0.373 ms`
- Waiting ~96% Arbitration

Producer 1 aggregate slow-fast:

- inter `+7.100 ms`
- Waiting `+3.047 ms`
- residual `+4.054 ms`
- estimated guest CPU `+3.904 ms`
- runnable-unscheduled `+0.354 ms`
- Waiting ~96% Arbitration

Result: **mixed CPU + upstream Arbitration**. Scheduler starvation is not the primary producer owner.

## Exact next diagnostic scope

Stage G should attribute only the **producer CPU branch** first.

Goal:

> determine which guest PC/LR context owns the additional producer CPU execution in slow swap3, for only the two dynamically selected Stage F producer threads.

### Required design

1. Reuse Stage F dynamic producer identities. No hardcoded observed TIDs or guest VA.
2. Observe scheduler/context-switch accounting only when the switched-out/running thread is one of the armed Stage F producers.
3. Attribute completed CPU slices to guest PC/LR context with a fixed-size aggregate histogram.
4. Report every 120 frames only; no per-switch logging.
5. Keep producer 0 and producer 1 independent.
6. Preserve Stage F CPU/Waiting/runUnsched totals so the CPU-context totals can be reconciled against the existing aggregate CPU branch.
7. Do not instrument all threads.
8. Do not change priority, affinity, yielding, wait behavior, GPU behavior, BufferQueue, cadence, or baseline.

### Preferred report

New marker, e.g. `[X1-WAKERG]`, with for each producer:

- dynamic TID
- CPU slice count
- total attributed CPU ticks/time
- top fixed number of PC/LR contexts and their CPU share
- unknown/overflow/malformed counters
- current priority/core metadata for sanity only

The implementation should use the same clock/tick domain as Stage F scheduler CPU accounting. Do not infer a hardcoded CPU frequency.

## Decision after Stage G runtime

A. one/few PC-LR contexts dominate the slow-fast CPU increase:

> map those exact guest contexts back to the guest call path / work type.

B. CPU attribution is diffuse:

> retain CPU as diffuse workload growth and switch next to the open producer Arbitration branch.

C. CPU-context totals do not reconcile with Stage F CPU trend:

> audit instrumentation before any optimization.

## Open parallel branch — do not erase

Producer corrected Waiting is overwhelmingly Arbitration and grows by ~2.4-2.9 ms per producer interval in slow mode.

After the CPU branch is attributed, recurse only the dominant producer `WaitForAddress` key/release owner. Do not add broad AddressArbiter tracing now unless separately scoped.

The separate Stage D dynamic-waker CPU-growth branch also remains open.

## Build rule

Stage G implementation and Ubuntu static validation do not authorize an ARM build.

After static validation, a fresh explicit user authorization is required for exactly one ARM64 attempt.

Current ARM64 authorization: **NONE**.
