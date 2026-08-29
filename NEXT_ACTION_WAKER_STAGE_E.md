# NEXT ACTION — Waker Stage E ARM64 Build Retry / Runtime

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_ARM_PRECHECK_FAILURE.md`

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

Stage E dynamically observes only the Stage-D-latched waker's `WaitForAddress` calls, ranks them in a fixed 16-slot table, promotes one top-duration key per 120-frame block, and recursively attributes only that promoted key's matching `SignalToAddress` owner and `w2s/s2e` timing.

No observed TID or process-specific guest address is hardcoded. CPU-by-LR partition remains intentionally separate.

Original Stage E Ubuntu static:

- run `33230000239`
- job `99041006308`
- conclusion `success`

## Stage E ARM64 attempts — BOTH CONSUMED BEFORE COMPILE

### Attempt 1

- run `33230457489`
- job `99042246285`
- build HEAD `0bab539c886a0c7b18be7ebe41476e81b7127a75`
- conclusion `failure`

Failure point: `Verify Stage E before configure`.

Cause: workflow checked nonexistent `TopSlotCount = 4` instead of the real `TopWaitCount = 4` / `TopSignalCount = 4`.

### Attempt 2

- run `33230727557`
- job `99042975831`
- build HEAD `72ca7f189611e24acb74494b63bbdeeba0ee73f5`
- conclusion `failure`

Failure point: again `Verify Stage E before configure`.

Cause: workflow checked nonexistent `ShouldTrackSignalAddress`; actual Stage E API is `ShouldTrackPromotedSignalAddress`.

Both attempts successfully reached and applied Stage E. In both attempts:

- MSYS2 setup was skipped
- CMake configure was skipped
- ARM64 C++ compile was skipped
- package/upload was skipped
- artifact count was zero
- no rerun/retry occurred

Therefore neither failure is evidence of a Stage E C++ build failure.

## Hardened ARM guard — UBUNTU PARITY PASSED

After attempt 2, the ARM pre-configure validation was audited against the actual Stage E transplant.

A third latent mismatch was removed: Stage E generates `x1_stage_e_profiler.RecordSignal(...)`, not `X1WakerStageEProfiler::Get().RecordSignal(...)`.

The validation was also changed to the safer pre-Stage-E snapshot model:

- reconstruct through Stage D
- snapshot `svc_address_arbiter.cpp` and `vk_rasterizer.cpp`
- record wait/signal/helper counts
- apply Stage E
- validate only Stage E delta against that snapshot

Persistent workflow hardening commit:

`34c5d3e563c77395ea8d0834e67b3b210fa8406f`

Ubuntu parity attempts:

- run `33230840202`, job `99043279158` — failed before full guard hardening
- run **`33230953769`**, job **`99043581687`** — **success**

The successful parity reproduced the current ARM pre-configure guard and passed exact dc95 reconstruction, Stage A-D, pre-E snapshot, Stage E apply, hook counts, call/helper preservation and behavior-diff guards.

Temporary parity workflow was removed after success.

Persistent ARM workflow remains **manual-only `workflow_dispatch`**.

## Exact next action

Only after a fresh explicit authorization for exactly one ARM64 attempt:

1. run the hardened manual-only Stage E ARM workflow exactly once;
2. no automatic retry/rerun;
3. if build succeeds, package artifact `Eden-dc95-X1-waker-stage-e`;
4. run the same TOTK 1.2.1 field scenario long enough to contain stable swap2 and stable swap3 windows;
5. collect at minimum:
   - `[X1-WAKERE]`
   - `[X1-WAKERD]`
   - `[X1-ADDRSIG]`
   - `[X1-ADDRARB]`
   - raw QueueBuffer cadence;
6. compare pure swap2 and pure swap3 120-frame blocks.

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
