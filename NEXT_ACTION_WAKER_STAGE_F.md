# NEXT ACTION — Waker Stage F Producer Attribution

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current branch:

`exp/x1-waker-stage-f-producer-attribution`

Never change the baseline without explicit approval.

ARM64 authorization: **NONE**.

## Stage E established

In runtime `eden_log(20260829-063358).txt`:

- Stage E direct WaitForAddress time reconciles with Stage D corrected Arbitration;
- dominant slow promoted key in that run: `0x210b05b39c`;
- secondary slow key: `0x2181c09eb4`;
- dominant promoted-key signalers observed in that run: `tid=0x80` and `tid=0x81`;
- fast promoted-key w2s about 0.5 ms;
- slow promoted-key w2s about 2-3 ms;
- signal -> dynamic waker return about 0.01 ms or less.

These TIDs and addresses are runtime observations only. Stage F does not hardcode them.

## Stage F implementation — COMPLETE / STATIC VALIDATED

New report:

`[X1-WAKERF]`

New files:

- `src/core/x1_waker_stage_f_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_f_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_f_attribution.py`

Stage F uses a fixed candidate table to discover the top two signaler TIDs for the current promoted address, then arms them for the following 120-frame window.

For each armed producer it reports:

- signal count / interval count
- inter-signal average/max
- corrected Waiting average
- residual average
- estimated guest CPU average/max
- runnable-unscheduled average/max
- corrected None/Sleep/IPC/Sync/ConditionVar/Arbitration/Suspended totals
- priority / active core / current core
- malformed and CPU-over-residual counters

No producer PC/LR sampler is included yet.

## Static validation

Ubuntu-only one-shot:

- run `33239570435`
- job `99066457540`
- attempt `1`
- conclusion `success`

The temporary static workflow was removed after success.

## Exact next action

Only after fresh explicit authorization for exactly one ARM64 attempt:

1. wire the persistent manual-only diagnostic workflow for Stage F;
2. trigger exactly one Stage F ARM64 build;
3. immediately restore the persistent workflow to manual-only after the run is created;
4. no retry/rerun if it fails;
5. if build succeeds, package a Stage F artifact containing the analyzer;
6. run the same TOTK 1.2.1 field scenario long enough to include stable swap2 and stable swap3 windows;
7. keep behavior-changing A/Bs OFF;
8. collect at minimum:
   - `[X1-WAKERF]`
   - `[X1-WAKERE]`
   - `[X1-WAKERD]`
   - `[X1-ADDRSIG]`
   - `[X1-ADDRARB]`
   - raw QueueBuffer cadence.

Because Stage F has a one-window discovery lag, do not interpret the first 120-frame block as complete producer attribution. Prefer at least two stable 120-frame blocks after the promoted key and top producer identities settle.

## Runtime decision tree

### A. Producer CPU dominates

If slow-fast producer interval growth is mostly estimated guest CPU time while runnable-unscheduled remains tiny:

> next stage = focused CPU callsite attribution only for the dynamically selected producer thread(s).

Do not broaden to all guest threads.

### B. Producer Waiting dominates

If corrected Waiting explains most producer interval growth:

> follow only the dominant corrected reason.

If Arbitration dominates again, recurse one edge upstream only for the dominant producer wait key. If ConditionVar/Synchronization dominates, attribute only that primitive's release owner.

### C. Runnable-unscheduled dominates

If residual grows while estimated CPU does not and `runUnschedAvg` becomes material:

> reopen scheduling/core-residency competition only for the two selected producers.

No priority or affinity mutation yet.

### D. Mixed

Keep CPU, Waiting and runnable-unscheduled branches quantified. Do not force a single owner until one branch explains the missing interval.

## Separate open branch

The Stage D dynamic-waker CPU growth remains independently open. Stage F producer results must not be used to erase or merge that branch without direct evidence.

## Hard prohibitions

- no ARM64 build/rerun without fresh explicit approval; one approval = one attempt
- no automatic retry
- no hardcoded runtime producer TIDs
- no hardcoded absolute guest wait address
- no all-thread scheduler trace
- no all-SVC profiler
- no broad PC sampler
- no per-event log flood
- no sleep/wait insertion
- no priority/core-affinity changes
- no GPU/BufferQueue/cadence behavior changes
- no baseline change
