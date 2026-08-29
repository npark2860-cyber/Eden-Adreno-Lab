# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-e-recursive-arbiter`
- Stage B runtime: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D implementation/build: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_IMPLEMENTED.md`
- Stage D runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_IMPLEMENTED.md`
- Stage E ARM precheck failures: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_ARM_PRECHECK_FAILURE.md`
- Stage E build/runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`

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
- exact dc95 verification: success
- hardened Stage E pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 compile: success
- package/upload: success
- rerun/retry: none

Artifact:

- `Eden-dc95-X1-waker-stage-e`
- id `9708884305`
- size `31,402,413` bytes
- SHA-256 `a07b9d4d02a2617d710e32d3baae8a5b868e00f81b3b4df4e1390ed5f56dab60`
- expires 2026-09-12

Persistent ARM workflow was restored to manual-only `workflow_dispatch` immediately after the approved run was created.

Earlier Stage E ARM attempts `33230457489` and `33230727557` both failed only in workflow pre-configure guards before MSYS2/configure/compile. Their guard issues were corrected and Ubuntu parity run `33230953769` passed before the successful ARM build. Do not rerun them.

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

Dominant submitter waits on one stable per-process gameplay AddressArbiter key:

- victim / submitter: `tid=0x53` in tested runs
- operation: `WaitIfEqual`
- timeout: `-1`
- direct `WaitForAddress` duration reconciles with reason-level Arbitration.
- guest VA relocates between launches, so target address is dynamically latched.

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

Stage C total Waiting remains valid. Its old entry-only named wait-reason breakdown is invalid because exact dc95 commonly assigns the debug reason after `BeginWait`.

## Stage D — RUNTIME COMPLETE

Runtime: `eden_log(20260829-024002).txt`

Measured identity:

- dynamic victim `tid=0x53`
- dynamic waker `tid=0x4f`
- waker switches `0`
- matching signal guest PC stable within the run
- waker priority `44`
- malformed CPU/wait/interval `0`

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

Slow corrected Waiting is overwhelmingly Arbitration. True None is zero in the tested run.

Keep the separate dynamic-waker CPU growth branch open; Stage E/F must not silently merge it into the recursive wait dependency.

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

### Stage E direct-wait reconciliation

Stage E direct `WaitForAddress` time closely reconciles with Stage D corrected Arbitration in both fast and slow gameplay. Therefore the Stage D Arbitration bucket is confirmed as real AddressArbiter time and the Stage E hooks cover essentially all of it.

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

Stable slow windows rise to roughly:

- Stage D Arbitration ~= `31 ms/frame`
- Stage E direct wait ~= `31 ms/frame`

### Dominant recursive key

Dominant slow key:

`0x210b05b39c`

It owns roughly `26 ms/frame` of the ~31 ms/frame slow Arbitration. Secondary key `0x2181c09eb4` contributes roughly another `4-5 ms/frame`.

Structural result:

- this is not one ~32 ms wait per frame;
- the waker repeatedly waits on the same key roughly 8-10 times per frame;
- fast per-wait latency is around `0.5-0.6 ms`;
- slow per-wait latency rises to roughly `2.7-3.2 ms`;
- wait count does not explode; each synchronization handshake becomes much slower.

### Recursive signal owners

For promoted key `0x210b05b39c`, Stage E finds two dominant signalers in the measured run:

- `tid=0x80`
- `tid=0x81`

They split promoted-key signals approximately evenly in slow gameplay.

Representative slow frame 1440:

- `tid=0x80`: 527 signals, `w2s ~= 2.371 ms`, `s2e ~= 0.011 ms`
- `tid=0x81`: 518 signals, `w2s ~= 3.037 ms`, `s2e ~= 0.011 ms`

Representative fast frame 960:

- `tid=0x80`: `w2s ~= 0.518 ms`
- `tid=0x81`: `w2s ~= 0.497 ms`
- signal -> waker return remains only about `0.005-0.007 ms`

Therefore the slow recursive delay occurs before the two producer signals. Once either producer signals the promoted key, `tid=0x4f` returns essentially immediately.

Absolute producer TIDs and promoted guest address are runtime observations only. Stage F must dynamically identify them and must not hardcode `0x80`, `0x81`, or `0x210b05b39c`.

## Current causal frontier — Stage F

Closed dependency so far:

`producer A/B -> promoted AddressArbiter signal -> tid=0x4f -> tid=0x53 -> GPU submit`

The next question is:

> Why do the two dominant promoted-key producer threads take much longer to reach their signals in slow mode?

Stage F scope:

1. dynamically select the top two signaler TIDs for the current Stage E promoted key;
2. use one-window discovery/arming if necessary; no hardcoded observed TIDs;
3. for each selected producer, split signal-to-signal time into:
   - interval
   - corrected total Waiting
   - residual
   - actual guest CPU time using scheduler CPU ticks / CoreTiming clock ticks as in Stage D
   - runnable-unscheduled = max(residual - CPU, 0)
   - corrected wait-reason totals;
4. report only every 120 rendered frames; no per-event flood;
5. keep the Stage D waker CPU branch independent;
6. do not add PC/LR callsite sampling yet unless Stage F proves CPU growth dominates;
7. do not add broad all-thread scheduler tracing.

Decision map:

- producer CPU dominates slow-fast growth -> next step is focused producer CPU callsite attribution;
- producer Waiting dominates -> follow only the dominant corrected wait primitive/release owner;
- runnable-unscheduled dominates -> reopen producer scheduling/core competition only for those dynamically selected producer threads;
- mixed -> keep branches quantified, no premature collapse.

## Actions state / ARM64 authorization

Persistent ARM workflow is manual-only `workflow_dispatch`.

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
