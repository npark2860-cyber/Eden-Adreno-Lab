# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-g-producer-cpu-attribution`
- Stage G pre-implementation repository snapshot: `4281991be0790584247de71c071e04c4374a6d74`

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
- Stage G implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_IMPLEMENTED.md`
- next action: `NEXT_ACTION_WAKER_STAGE_G.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current workflow name:

`Build dc95 X1 Waker Stage G`

Trigger:

`workflow_dispatch` only.

It is prepared for Stage G but has not been triggered.

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

No Stage G ARM64 build has occurred.

## Closed historical chain

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe remains rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is adaptive mapped fast stream/re-stream.
- classic-cache fallback A/B did not break the gameplay ceiling.
- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- raw3->effective2 clamp did not improve upstream frame generation.
- DFPS is not the root.
- BufferQueue free-slot/backpressure is closed as primary owner.
- GPU worker is predominantly waiting for command supply.
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint are not the missing interval owner.
- dominant guest submitter in tested runs = observed `tid=0x53`.
- NVDRV IPC dispatch is about `0.02-0.03 ms/request`.
- host scheduler starvation is closed as the primary owner for both the Stage D dynamic-waker slowdown and the Stage F producer slowdown.

Runtime-observed TIDs and guest addresses are observations only and must not be hardcoded.

## Stage A — COMPLETE

Dominant submitter / victim observed as `tid=0x53`.

One stable per-process gameplay AddressArbiter key was found with:

- `WaitForAddress`
- `WaitIfEqual`
- timeout `-1`

Direct wait duration reconciles with reason-level Arbitration.

Guest VA relocates between launches; dynamic latching is mandatory.

## Stage B — COMPLETE

Measured edge:

- victim observed `tid=0x53`
- matching waker observed `tid=0x4f`
- signal `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- one matching signal per rendered frame

Direct victim wait ~= wait-start -> signal (`w2s`).

Signal -> victim return (`s2e`) is essentially zero.

Therefore the long victim delay is before the waker signal.

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

Stage C total Waiting remains valid. Its old entry-only named wait-reason breakdown is invalid and discarded.

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

Corrected slow Waiting is overwhelmingly Arbitration:

- ConditionVar `17.252 -> 0.469 ms`
- Arbitration `7.440 -> 32.339 ms`
- Sleep `0.996 -> 1.358 ms`
- Synchronization `0.019 -> 0.687 ms`
- IPC `0.023 -> 0.038 ms`
- true None `0`

Host scheduler starvation is closed for the dynamic-waker slowdown.

The separate dynamic-waker CPU growth branch remains open.

## Stage E — RUNTIME COMPLETE

Runtime: `eden_log(20260829-063358).txt`

Stage E direct `WaitForAddress` time reconciles with Stage D corrected Arbitration.

Observed dominant promoted key in that run:

`0x210b05b39c`

Observed secondary key:

`0x2181c09eb4`

The dominant key is repeated short synchronization, not one single ~32 ms wait per rendered frame:

- roughly 8-10 waits/frame
- fast per-wait about `0.5-0.6 ms`
- slow per-wait about `2.7-3.2 ms`

Observed dominant signalers in that run:

- `tid=0x80`
- `tid=0x81`

Representative slow frame 1440:

- observed `0x80`: 527 signals, `w2s ~= 2.371 ms`, `s2e ~= 0.011 ms`
- observed `0x81`: 518 signals, `w2s ~= 3.037 ms`, `s2e ~= 0.011 ms`

Fast `w2s` is about `0.5 ms`.

Signal -> dynamic-waker return remains essentially immediate, so the recursive delay is before the producer signal.

## Stage F — RUNTIME COMPLETE

Runtime: `eden_log(20260829-073615).txt`

Stage F dynamically settled in this run on:

- promoted address observed `0x210b45b39c`
- producer 0 observed TID `0x80`
- producer 1 observed TID `0x81`
- producer cores observed `1` and `2`
- priority `44` for both
- no candidate overflow in stable windows
- no tracking switch after discovery settled

These are runtime observations only.

Pure swap2 windows:

- frames `480, 600, 720, 840, 960`

Transition excluded:

- frame `1080`: 13 swap2 / 107 swap3

Pure swap3 windows:

- frames `1200, 1320, 1440`

### Producer 0 aggregate

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 6.111 ms | 12.185 ms | +6.074 ms |
| corrected Waiting | 5.002 ms | 7.467 ms | +2.465 ms |
| residual | 1.109 ms | 4.719 ms | +3.610 ms |
| estimated guest CPU | 1.005 ms | 4.439 ms | +3.434 ms |
| runnable-unscheduled | 0.324 ms | 0.698 ms | +0.373 ms |
| Arbitration | 4.785 ms | 7.166 ms | +2.381 ms |

### Producer 1 aggregate

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 7.314 ms | 14.415 ms | +7.100 ms |
| corrected Waiting | 6.072 ms | 9.119 ms | +3.047 ms |
| residual | 1.243 ms | 5.296 ms | +4.054 ms |
| estimated guest CPU | 1.121 ms | 5.025 ms | +3.904 ms |
| runnable-unscheduled | 0.348 ms | 0.702 ms | +0.354 ms |
| Arbitration | 5.847 ms | 8.729 ms | +2.881 ms |

Waiting is about 96% Arbitration for both producers in both regimes.

Weighted promoted-key timing across the same windows:

- producer 0 fast `w2s ~0.564 ms`, slow `~3.152 ms`
- producer 1 fast `w2s ~0.543 ms`, slow `~3.045 ms`
- `s2e` remains about `0.01 ms`

Stage F conclusion is mixed:

1. producer guest CPU increases by about `+3.43 / +3.90 ms` per producer interval;
2. producer Arbitration increases by about `+2.38 / +2.88 ms` per producer interval.

Runnable-unscheduled growth is much smaller. Do not collapse the CPU and Arbitration branches.

Stage F CPU caveat remains: `GetCpuTime()` is context-switch accounted, so individual interval tails can cross interval boundaries. Use clean multi-window aggregate trends.

## Stage G — IMPLEMENTED / UBUNTU STATIC COMPLETE

Implementation record:

`DEBUG_HISTORY_20260829_WAKER_STAGE_G_IMPLEMENTED.md`

Branch:

`exp/x1-waker-stage-g-producer-cpu-attribution`

Pre-G branch snapshot:

`4281991be0790584247de71c071e04c4374a6d74`

Stage G goal:

> attribute only the Stage F producer CPU branch to guest PC/LR execution contexts.

### Identity selection

Stage G does not rediscover or hardcode producer identities.

It queries Stage F's currently armed producer pair through a read-only dynamic accessor.

### Scheduler attribution

Exact dc95 hook:

`KScheduler::SwitchThread`

The switched-out selected producer receives the exact scheduler `tick_diff` that exact dc95 adds via:

`KThread::AddCpuTime()`

Guest `PC/LR` is read only after the Stage F selected-producer check succeeds.

Therefore Stage G is not an all-thread PC sampler.

A selected-producer switch-in hook records the slice start for a separate steady-clock wall-duration sanity measurement.

### Aggregation/report

- producer slots: `2`
- fixed PC/LR context slots per producer: `64`
- report cadence: `120` frames
- top contexts by CPU ticks: `4`
- marker: `[X1-WAKERG]`
- no per-switch logging

Primary runtime attribution quantity:

`cpuTicks`

These are exact scheduler/CoreTiming CPU-accounting ticks and therefore share the underlying CPU accounting domain used by Stage F `GetCpuTime()`.

`cpuWall` is a separate switch-in -> switch-out steady-clock sanity value and must not be treated as identical to Stage F `ScaleTicksToNs()` CPU estimates.

### Ubuntu static validation

One-shot workflow:

- workflow `Validate dc95 X1 Waker Stage G`
- run `33242026006`
- job `99072879855`
- attempt `1`
- validation HEAD `40b59fff8728ead7df503db6b7279ef5af297ff5`
- conclusion `success`

Passed:

- exact dc95 HEAD preservation
- retained chain reconstruction through Stage F
- pre-G snapshot
- Stage G transplant
- `git diff --check`
- Stage G transplant/analyzer `py_compile`
- no hardcoded observed TIDs/address
- guarded selected-producer-only guest context read
- no all-thread PC sampling
- scheduler `AddCpuTime` / `SwitchThread` / `SetCurrentThread` call counts preserved
- no Stage-G-added priority/affinity/reschedule/yield/sleep mutation
- no GPU/QueueBuffer/swap/fence mutation
- analyzer synthetic-log smoke
- final exact dc95 HEAD preservation

Temporary Ubuntu workflow was deleted after success.

No Stage G ARM64 build was run.

## Current causal frontier

Measured chain:

GPU command starvation
-> dominant guest submitter / victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dynamically selected producer threads
-> **producer CPU growth + producer Arbitration growth**

Stage G is now ready to measure the producer CPU callsite branch.

Still open in parallel:

1. producer-side Arbitration recursion: after CPU attribution, follow only the dominant producer `WaitForAddress` key/release owner;
2. separate Stage D dynamic-waker CPU-growth branch.

No optimization is justified yet.

## Immediate next action / authorization gate

Current ARM64 authorization: **NONE**.

Do not trigger the persistent workflow until the user supplies a fresh explicit authorization.

The next fresh `ㄱㄱ` after this handoff authorizes exactly one Stage G ARM64 attempt on:

`exp/x1-waker-stage-g-producer-cpu-attribution`

using:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

No retry/rerun is allowed without another fresh authorization, even if that single attempt fails.
