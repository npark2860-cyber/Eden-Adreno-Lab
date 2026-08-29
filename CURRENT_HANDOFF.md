# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-f-producer-attribution`
- Stage B runtime: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D implementation/build: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- Stage D runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_IMPLEMENTED.md`
- Stage E ARM precheck failures: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_ARM_PRECHECK_FAILURE.md`
- Stage E build/runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- Stage F implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_F_IMPLEMENTED.md`
- next action: `NEXT_ACTION_WAKER_STAGE_F.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest successful ARM64 build — Stage E SUCCESS

- workflow: `Build dc95 X1 Waker Stage E`
- run: `33231201850`
- job: `99044246393`
- attempt: `1`
- build HEAD: `b750792e460f416a15ed1702c13232c19b9f6b4b`
- exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- conclusion: `success`
- artifact: `Eden-dc95-X1-waker-stage-e`
- artifact id: `9708884305`
- size: `31,402,413` bytes
- SHA-256: `a07b9d4d02a2617d710e32d3baae8a5b868e00f81b3b4df4e1390ed5f56dab60`
- rerun/retry: none

Persistent ARM workflow is currently manual-only `workflow_dispatch`. It is still wired for Stage E; Stage F ARM wiring must only be performed as part of a fresh explicitly authorized one-attempt ARM64 build.

## Closed historical chain

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe remains rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is mapped adaptive fast stream; payload repeat does not make blind lifetime reuse safe.
- classic-cache fallback did not break the gameplay ceiling.
- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- raw3->effective2 clamp and DFPS did not raise upstream frame generation.
- BufferQueue free-slot/backpressure is closed as primary owner.
- GPU worker is mostly starved for command supply; active GPU-command work is not the missing interval.
- long inter-submit gap exists before NVDRV handler entry; handler/SubmitGPFIFO/locks/fence/syncpoint are tiny.
- dominant guest submitter in tested runs = `tid=0x53`, CPU share about 1-2%.
- NVDRV IPC dispatch is about 0.02-0.03 ms/request; host service scheduling is not the missing owner.

## Stage A — COMPLETE

- dominant submitter / victim: `tid=0x53` in tested runs
- one stable per-process gameplay AddressArbiter key
- `WaitIfEqual`
- timeout `-1`
- direct `WaitForAddress` duration reconciles with reason-level Arbitration
- guest VA relocates between launches; target is dynamically latched

## Stage B — COMPLETE

Measured edge:

- victim `tid=0x53`
- sole matching waker `tid=0x4f` in measured runs
- signal `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- one matching signal per rendered frame
- direct wait ~= wait-start -> signal (`w2s`)
- signal -> victim return (`s2e`) essentially zero

Therefore the long victim wait occurs before the waker signals.

## Stage C — RUNTIME COMPLETE

Runtime: `eden_log(20260828-173023).txt`

Stable fast:

- inter-signal `33.722 ms`
- total Waiting `27.708 ms`
- residual `6.014 ms`

Stable slow:

- inter-signal `55.022 ms`
- total Waiting `34.183 ms`
- residual `20.839 ms`

Stage C total Waiting remains valid. Its old entry-only named wait-reason breakdown is invalid because exact dc95 commonly assigns the debug wait reason after `BeginWait`.

## Stage D — RUNTIME COMPLETE

Runtime: `eden_log(20260829-024002).txt`

Aggregate stable split:

| metric | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 33.454 ms | 56.972 ms | +23.518 ms |
| corrected Waiting | 25.706 ms | 34.897 ms | +9.190 ms |
| residual | 7.748 ms | 22.075 ms | +14.327 ms |
| estimated waker CPU | 7.526 ms | 21.802 ms | +14.276 ms |
| runnable-unscheduled | 0.239 ms | 0.307 ms | +0.068 ms |

**Runnable/scheduler starvation is closed for the dynamic-waker slowdown.**

Corrected wait-reason shift:

| reason | stable swap2 | stable swap3 | slow-fast |
|---|---:|---:|---:|
| ConditionVar | 17.252 ms | 0.469 ms | -16.784 ms |
| Arbitration | 7.440 ms | 32.339 ms | +24.900 ms |
| Sleep | 0.996 ms | 1.358 ms | +0.362 ms |
| Synchronization | 0.019 ms | 0.687 ms | +0.668 ms |
| IPC | 0.023 ms | 0.038 ms | +0.015 ms |
| true None | 0.000 ms | 0.000 ms | 0.000 ms |

Slow corrected Waiting is overwhelmingly Arbitration. Keep the separate dynamic-waker CPU growth branch open.

## Stage E — RUNTIME COMPLETE

Runtime: `eden_log(20260829-063358).txt`

Environment:

- Eden `HEAD-dc95cd09ee`
- Windows 11 25H2 build 26220.9223
- Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- TOTK 1.2.1
- Address Arbiter attribution ON
- behavior-changing A/Bs OFF, including swap3->2 clamp

### Direct-wait reconciliation

Stage E direct `WaitForAddress` time closely reconciles with Stage D corrected Arbitration in fast and slow gameplay.

Representative fast frame 960:

- Stage D inter `33.750 ms`
- Stage D CPU `6.166 ms/signal`
- Stage D Arbitration `655.440 ms / 120f`
- Stage E direct wait `665.202 ms / 120f`
- top0 `0x210b05b39c`: `624.914 ms / 120f`, `0.514 ms` average
- top1 `0x2181c09eb4`: `30.968 ms / 120f`

Representative fast frame 1080:

- Stage D inter `35.559 ms`
- Stage D CPU `9.047 ms/signal`
- Stage D Arbitration `719.537 ms / 120f`
- Stage E direct wait `735.168 ms / 120f`
- top0 `0x210b05b39c`: `678.477 ms / 120f`, `0.591 ms` average
- top1 `0x2181c09eb4`: `29.993 ms / 120f`

Stable slow windows rise to roughly `31 ms/frame` for both Stage D Arbitration and Stage E direct waits.

### Dominant recursive key

Observed dominant slow key in this run:

`0x210b05b39c`

It owns roughly `26 ms/frame` of the ~31 ms/frame slow Arbitration. Secondary key `0x2181c09eb4` contributes roughly `4-5 ms/frame`.

This is repeated short synchronization, not one single ~32 ms wait per frame:

- roughly 8-10 waits/frame on the dominant key;
- fast per-wait latency about `0.5-0.6 ms`;
- slow per-wait latency about `2.7-3.2 ms`;
- wait count does not explode; release latency per handshake grows.

### Recursive signal owners

For the observed promoted key, Stage E found two dominant guest signalers:

- observed `tid=0x80`
- observed `tid=0x81`

Representative slow frame 1440:

- observed `0x80`: 527 signals, `w2s ~= 2.371 ms`, `s2e ~= 0.011 ms`
- observed `0x81`: 518 signals, `w2s ~= 3.037 ms`, `s2e ~= 0.011 ms`

Representative fast frame 960:

- observed `0x80`: `w2s ~= 0.518 ms`
- observed `0x81`: `w2s ~= 0.497 ms`
- signal -> waker return about `0.005-0.007 ms`

Therefore the slow recursive delay occurs before the producer signals. Once either producer signals, the waker returns essentially immediately.

Absolute TIDs and guest addresses above are runtime observations only and must never be hardcoded into later profilers.

## Stage F — IMPLEMENTED / UBUNTU STATIC VALIDATED

Current branch:

`exp/x1-waker-stage-f-producer-attribution`

New files:

- `src/core/x1_waker_stage_f_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_f_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_f_attribution.py`

New report:

`[X1-WAKERF]`

### Dynamic producer discovery

Stage F sees only signals already accepted by Stage E as targeting its promoted key.

It aggregates `(promoted address, signaler TID)` in a fixed 16-slot candidate table and, every 120 frames:

1. selects the address with the largest candidate signal population;
2. selects the top two signaler TIDs for that address;
3. arms only those two producers for the following window.

This creates an intentional one-window discovery lag. If the promoted key changes, address and producer identities can both be reselected dynamically.

No observed `0x80`, `0x81`, or `0x210...` value is hardcoded.

### Producer interval decomposition

For each armed producer, promoted-key signal entry samples read-only:

- `KThread::GetCpuTime()`
- `CoreTiming().GetClockTicks()`
- priority
- active core
- current core

Each producer's signal-to-signal interval is split into:

- inter-signal wall time
- corrected total Waiting
- residual
- estimated guest CPU
- runnable-unscheduled = max(residual - CPU, 0)

KThread state transitions are observed only for the two armed producer TIDs.

Corrected completed wait reason uses:

`exit reason if non-None, otherwise entry reason fallback`

with totals for None / Sleep / IPC / Synchronization / ConditionVar / Arbitration / Suspended.

No producer PC/LR sampling is present yet. That is intentionally deferred until runtime shows CPU growth dominates.

### Stage F Ubuntu static validation

- workflow: `One-shot X1 Waker Stage F Static`
- run: `33239570435`
- job: `99066457540`
- attempt: `1`
- conclusion: `success`

Passed:

- exact dc95 checkout and HEAD preservation
- retained chain recreation
- Stage A-E recreation
- pre-F snapshot
- Stage F application
- `git diff --check`
- Stage F transplant/analyzer `py_compile`
- dynamic two-producer / 16-candidate design markers
- no hardcoded observed producer TIDs
- no hardcoded observed guest wait VA
- no producer PC/LR sampler
- exactly one Stage F promoted-signal hook
- exactly one Stage F KThread transition hook
- exactly one Stage F init and frame hook
- original WaitAddressArbiter and SignalAddressArbiter call counts preserved vs pre-F
- validation helper counts preserved vs pre-F
- no Stage-F-added wait/yield/reschedule/priority/core-mask behavior
- no Stage-F-added GPU/swap/fence behavior
- analyzer synthetic smoke test

Temporary Ubuntu workflow was deleted after success.

## Current causal frontier — Stage F ARM64 runtime

Next runtime question:

> For the two dynamically selected Stage E promoted-key signal producers, is slow signal delivery caused primarily by their own guest CPU work, another wait dependency, or runnable-but-unscheduled delay?

Decision map:

A. producer CPU dominates slow-fast growth:

> next stage = focused CPU callsite attribution for only the dynamically selected producer thread(s).

B. producer Waiting dominates:

> follow only the dominant corrected wait primitive/release owner; if Arbitration dominates, recurse only the dominant producer wait key.

C. runnable-unscheduled dominates:

> reopen scheduling/core competition only for those dynamically selected producers; no priority/affinity mutation yet.

D. mixed:

> keep CPU, Waiting and runnable-unscheduled quantified; no premature collapse.

Regardless of Stage F outcome, keep the separate Stage D dynamic-waker CPU-growth branch open until explicitly attributed.

See `NEXT_ACTION_WAKER_STAGE_F.md`.

## Actions state / ARM64 authorization

No Stage F ARM64 build has been triggered.

Persistent ARM workflow remains manual-only and still contains Stage E wiring.

Current ARM64 build authorization: **NONE**.

Do not wire/trigger/rerun/rebuild Stage F ARM64 until the user gives fresh explicit authorization for exactly one attempt.
