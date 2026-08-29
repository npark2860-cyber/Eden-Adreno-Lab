# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-f-producer-attribution`

Primary records:

- Stage B runtime: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D implementation/build: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- Stage D runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_IMPLEMENTED.md`
- Stage E ARM precheck failures: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_ARM_PRECHECK_FAILURE.md`
- Stage E build/runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- Stage F implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_F_IMPLEMENTED.md`
- Stage F runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- next action: `NEXT_ACTION_WAKER_STAGE_G.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest successful ARM64 build — Stage F SUCCESS

- workflow: `Build dc95 X1 Waker Stage F`
- run: `33239788740`
- job: `99067041921`
- attempt: `1`
- build HEAD: `309c8cc5ab430289f9c1489ec7d4b79272ad88f4`
- exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- conclusion: `success`
- exact dc95 verification: success
- Stage F pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 compile: success
- package/upload: success
- rerun/retry: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-f`
- artifact id: `9711330615`
- size: `31,411,478` bytes
- SHA-256: `f3171da4a9756864b5c3f71b3870f435a8b11b74f3ec0895479331759b71b83f`
- created: `2026-08-29T07:29:03Z`
- expires: `2026-09-12T07:29:01Z`
- expired: false at verification

Persistent ARM workflow was restored to manual-only `workflow_dispatch` after the approved run was created.

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

- dominant submitter / victim observed as `tid=0x53`
- one stable per-process gameplay AddressArbiter key
- `WaitIfEqual`
- timeout `-1`
- direct `WaitForAddress` duration reconciles with reason-level Arbitration
- guest VA relocates between launches; target must be dynamically latched

## Stage B — COMPLETE

Measured edge:

- victim observed `tid=0x53`
- sole matching waker observed `tid=0x4f`
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

Stage E established:

- Stage E direct `WaitForAddress` time reconciles with Stage D corrected Arbitration;
- dominant slow promoted key observed in that run: `0x210b05b39c`;
- secondary slow key observed: `0x2181c09eb4`;
- dominant promoted-key signalers observed: `tid=0x80` and `tid=0x81`;
- fast promoted-key `w2s` about `0.5-0.6 ms`;
- slow promoted-key `w2s` about `2.7-3.2 ms`;
- signal -> dynamic waker return about `0.01 ms` or less.

The dominant key is repeated short synchronization, not one single ~32 ms wait per frame. Slowdown is increased release latency per handshake.

Absolute TIDs and guest addresses above are runtime observations only and must never be hardcoded.

## Stage F — RUNTIME COMPLETE

Runtime: `eden_log(20260829-073615).txt`

Environment:

- Eden `HEAD-dc95cd09ee`
- Windows 11 25H2 build 26220.9223
- Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- TOTK 1.2.1
- Address Arbiter attribution ON
- behavior-changing A/Bs OFF, including swap3->2 clamp

### Dynamic identity in this run

Stage F dynamically settled on:

- promoted address observed: `0x210b45b39c`
- producer 0 observed TID: `0x80`
- producer 1 observed TID: `0x81`
- producer 0 active/current core: `1/1`
- producer 1 active/current core: `2/2`
- both priority `44`
- no candidate overflow in stable windows
- no tracking switch after discovery settles

These are runtime observations only; no hardcoding.

### Stable cadence blocks

Pure swap2:

- frames `480, 600, 720, 840, 960` — each 120/120 swap2

Transition excluded:

- frame `1080` — 13 swap2 / 107 swap3

Pure swap3:

- frames `1200, 1320, 1440` — each 120/120 swap3

### Producer 0 aggregate — observed `tid=0x80`

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 6.111 ms | 12.185 ms | +6.074 ms |
| corrected Waiting | 5.002 ms | 7.467 ms | +2.465 ms |
| residual | 1.109 ms | 4.719 ms | +3.610 ms |
| estimated guest CPU | 1.005 ms | 4.439 ms | +3.434 ms |
| runnable-unscheduled | 0.324 ms | 0.698 ms | +0.373 ms |
| Arbitration | 4.785 ms | 7.166 ms | +2.381 ms |

Arbitration owns ~95.7% of fast Waiting and ~96.0% of slow Waiting.

### Producer 1 aggregate — observed `tid=0x81`

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 7.314 ms | 14.415 ms | +7.100 ms |
| corrected Waiting | 6.072 ms | 9.119 ms | +3.047 ms |
| residual | 1.243 ms | 5.296 ms | +4.054 ms |
| estimated guest CPU | 1.121 ms | 5.025 ms | +3.904 ms |
| runnable-unscheduled | 0.348 ms | 0.702 ms | +0.354 ms |
| Arbitration | 5.847 ms | 8.729 ms | +2.881 ms |

Arbitration owns ~96.3% of fast Waiting and ~95.7% of slow Waiting.

### Reconciliation with Stage E

Across the same pure windows, weighted promoted-key signal timing:

- observed `0x80` fast: `w2s ~0.564 ms`, `s2e ~0.011 ms`
- observed `0x80` slow: `w2s ~3.152 ms`, `s2e ~0.014 ms`
- observed `0x81` fast: `w2s ~0.543 ms`, `s2e ~0.010 ms`
- observed `0x81` slow: `w2s ~3.045 ms`, `s2e ~0.013 ms`

Signal -> waker return remains tiny. The slowdown is before producer signal.

### Stage F conclusion

Stage F result is **mixed CPU + upstream Arbitration**.

For both producers:

- signal-to-signal wall time roughly doubles in slow mode;
- Waiting grows materially;
- residual grows even more;
- estimated CPU increase nearly matches residual increase across stable 120-frame aggregates;
- runnable-unscheduled growth remains small relative to CPU and Waiting growth;
- corrected Waiting is ~96% Arbitration in both regimes;
- core residency remains stable in the reports.

Therefore host scheduler starvation is **not the primary Stage F owner**.

Two quantified branches remain:

1. producer CPU branch: roughly `+3.43 ms` / `+3.90 ms` per producer interval;
2. producer upstream Arbitration branch: roughly `+2.38 ms` / `+2.88 ms` per producer interval.

Do not collapse them without further evidence.

CPU caveat: `GetCpuTime()` is context-switch accounted, so `cpuOverResidual` is nonzero in individual intervals. Use 120-frame aggregate trends, not single-interval additive arithmetic.

## Current causal frontier — Stage G design / implementation not started

Current measured chain:

GPU command starvation
-> dominant guest submitter / victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dominant producer threads
-> **producer-side CPU work + producer-side Arbitration dependency both grow in slow mode**

Priority next diagnostic:

> focused CPU-slice PC/LR attribution for only the dynamically selected Stage F producers.

Reason: CPU is the largest single slow-fast increase for both producer cycles and Stage F intentionally deferred PC/LR attribution until runtime proved CPU growth material.

The producer Waiting branch remains open and is overwhelmingly Arbitration. After CPU attribution, recurse only the dominant producer `WaitForAddress` key/release owner.

The separate Stage D dynamic-waker CPU-growth branch also remains open.

No optimization is justified yet.

See `NEXT_ACTION_WAKER_STAGE_G.md`.

## Actions state / ARM64 authorization

Persistent ARM workflow is manual-only `workflow_dispatch` and currently contains Stage F wiring.

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild ARM64 until the user gives fresh explicit authorization for exactly one attempt.
