# NEXT ACTION — Waker Stage D Runtime

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current Stage D branch:

`exp/x1-waker-stage-d-cpu-scheduler`

Never change the baseline without explicit approval.

ARM64 build authorization: **NONE**.

## Established before Stage D runtime

Stage B remains closed:

- victim / submitter in measured runs: `tid=0x53`
- dynamic waker in measured runs: `tid=0x4f`
- matching `SignalAndIncrementIfEqual`, value `1`, count `-1`
- long victim wait is almost entirely wait-start -> signal
- signal -> victim return is essentially immediate

Stage C total interval split remains valid:

- stable fast inter-signal ~= 33.7 ms
- stable slow inter-signal ~= 55.0 ms
- slowdown increment ~= +21.3 ms/signal
- total KThread Waiting increment ~= +6.5 ms/signal
- Stage-C residual increment ~= +14.8 ms/signal

### Stage C reason-breakdown correction

Do **not** use Stage C `none/sleep/ipc/sync/cond/arb` breakdown as causal evidence.

Stage C captured wait reason at entry into `ThreadState::Waiting`. Exact dc95 commonly sets Arbitration / ConditionVar / Synchronization / Sleep **after** `BeginWait`, so named waits could be misreported as `None`.

Stage D corrects completed waits using:

> exit reason if non-None, otherwise entry reason fallback

Therefore the prior claim that another named waker wait was disproved is withdrawn. Stage C proved total Waiting versus residual only.

## Stage D implementation — READY / STATIC VALIDATED

New report:

`[X1-WAKERD]`

It remains dynamically waker-latched and observation-only.

Per 120 rendered frames it reports:

- inter-signal avg/max
- corrected Waiting avg and reason totals
- residual avg
- estimated waker CPU avg/max from `GetCpuTime()` in the same `GetClockTicks()` domain
- estimated runnable-unscheduled avg/max = max(residual - CPU, 0)
- reason-less direct wait-site totals for:
  - unknown
  - `KThread::SetActivity` pinned wait
  - `KThread::SetCoreMask` pinned wait
  - `KProcess::EnterUserException`
- priority / active core / current core latest metadata
- matching signal PC
- top-4 LR histogram + overflow
- malformed/sanity counters

CPU caveat:

`GetCpuTime()` is updated at context switches, so use 120-frame aggregate trends rather than individual signal intervals as exact CPU accounting.

## Static validation

Successful Ubuntu-only validation:

- run `33216436564`
- job `99000993229`
- conclusion `success`

No ARM64 run occurred.

## Runtime procedure after fresh ARM64 authorization

One authorization = one ARM64 attempt.

Build the current Stage D source against exact dc95 and run the same TOTK field scenario long enough to obtain both stable raw swap2 and stable raw swap3 windows if possible.

Collect at minimum:

- `[X1-WAKERD]`
- `[X1-WAKER]`
- `[X1-ADDRSIG]`
- `[X1-ADDRARB]`
- `[X1-GUESTWAIT]`
- raw cadence / QueueBuffer swap interval

Compare stable-fast versus stable-slow 120-frame blocks.

## Decision tree

### A. CPU increase dominates

If `cpuAvg` grows by roughly the same amount as the Stage-C residual increase while `runUnschedAvg` stays small:

> the waker is doing materially more guest CPU work before signaling.

Next target: dominant LR/caller path only. Do not broaden scheduler tracing.

### B. Runnable-unscheduled dominates

If CPU remains near fast-regime levels while `runUnschedAvg` expands materially:

> the waker is ready but not getting CPU promptly enough.

Next target: waker-only scheduling competition/core residency. Do not change priority/affinity before attribution.

### C. Corrected named Waiting dominates

If Arbitration / Sync / ConditionVar / Sleep / IPC expands materially after corrected classification:

> follow only that wait primitive and its release/producer owner.

### D. True reason-less direct site dominates

If one focused None-site bucket expands materially:

> follow only that exact site and its release condition.

### E. Mixed result

Keep CPU, runnable-unscheduled, named wait and reason-less wait as separately quantified branches. Do not collapse them into one root cause prematurely.

## Hard prohibitions

- no ARM64 build/rerun without fresh explicit approval; one approval = one attempt
- no automatic rerun after failure
- no all-thread scheduler trace
- no all-SVC profiler
- no per-event log flood
- no sleep/wait insertion
- no priority/core-affinity changes
- no GPU/BufferQueue/cadence behavior change
- no baseline change
