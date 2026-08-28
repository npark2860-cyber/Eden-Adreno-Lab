# NEXT ACTION — Waker Stage D

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Never change it without explicit approval.

ARM64 build authorization: **NONE**.

## Closed Stage C result

The dynamically discovered waker remains `tid=0x4f` in the measured run and signals the dynamically latched target address once per rendered frame.

Stage C shows:

- fast swap2 inter-signal ~= 33.7 ms
- stable slow swap3 inter-signal ~= 55.0 ms
- stable slowdown increment ~= +21.3 ms/signal
- Waiting increment ~= +6.5 ms/signal
- Stage-C residual increment ~= +14.8 ms/signal
- named waker wait reasons are essentially absent
- almost all waker Waiting is debug reason `None`
- matching SignalToAddress PC is almost invariant at `0x85f16528`, while LR varies
- `lastWaitSvc=0x0` is non-informative

Do not equate Stage-C residual with CPU work. It also includes runnable-but-unscheduled time.

## Exact Stage D questions

1. How much waker time between matching signals is actual guest CPU execution?
2. How much of the Stage-C residual is runnable/unscheduled scheduler delay?
3. Which direct `BeginWait` site owns `ThreadState::Waiting + reason=None` for the waker?
4. Which LR/caller sites dominate matching SignalToAddress?

## Minimal instrumentation

Keep Stage D waker-only, dynamically latched, observation-only.

### A. Waker CPU delta

At each matching SignalToAddress for the dynamically latched waker:

- read `KThread::GetCpuTime()`
- compute delta from previous matching signal
- aggregate total/avg/max over the 120-frame report
- derive:
  - `cpuAvg`
  - `runnableUnscheduledAvg = residualAvg - cpuAvg` with defensive floor at zero

Optionally record current core, active core and priority only as aggregate/latest metadata. Do not alter them.

### B. `reason=None` wait-site owner

Do not add generic all-kernel tracing.

Instrument only exact dc95 direct `BeginWait(...)` paths which can produce Waiting without assigning a debug wait reason, and gate each record with `ShouldTrackThread(dynamic_waker_tid)`.

Use a fixed enum and aggregate total/count/max per site. Initial source candidates include:

- KThread pinned-wait paths in `k_thread.cpp`
- KProcess user-exception wait path in `k_process.cpp`

Before implementation, rescan exact dc95 direct `BeginWait` call sites and verify which paths already set Sleep/IPC/Synchronization/ConditionVar/Arbitration. Do not assume the candidate list is exhaustive without that scan.

### C. Signal LR histogram

Current PC is almost invariant and may simply be the common SVC wrapper.

Add a small fixed-size LR histogram at matching SignalToAddress:

- top 4 LR values
- calls/count share
- no per-event logging
- preserve PC latest/reference for correlation

## Runtime interpretation

If CPU time explains most of the residual increase:

> follow the dominant LR/caller path upstream in guest code; waker is doing more guest work before signaling.

If runnable-unscheduled explains most residual:

> next target is only the waker's scheduling competition/priority/core residency before SignalToAddress, not broad scheduler tracing.

If one `None` wait site explains the additional Waiting:

> follow only that kernel primitive/site and its producer/release owner.

If both are material, keep both branches quantified; do not collapse them into one root cause prematurely.

## Hard prohibitions

- no ARM64 build/rerun without fresh explicit approval; one approval = one attempt
- no all-thread scheduler trace
- no all-SVC profiler
- no per-event log flood
- no sleep/wait insertion
- no priority/core-affinity changes
- no GPU/BufferQueue/cadence behavior change
- no baseline change
