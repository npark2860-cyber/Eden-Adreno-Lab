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
- Stage G ARM precheck failure: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_ARM_PRECHECK_FAILURE.md`
- Stage G build/runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- next action: `NEXT_ACTION_WAKER_STAGE_H.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current workflow name:

`Build dc95 X1 Waker Stage G`

Trigger:

`workflow_dispatch` only.

Do not trigger it without a fresh explicit ARM64 authorization.

## Latest successful ARM64 build — Stage G SUCCESS

A first Stage G ARM attempt failed in pre-configure verification because a Git-Bash `/tmp/...` snapshot path was not visible to native Windows Python. It did not reach MSYS2/configure/compile. That attempt is recorded separately and was not rerun.

After the workflow precheck was fixed to a workspace-relative path, a fresh authorization was used for exactly one new attempt:

- workflow: `Build dc95 X1 Waker Stage G`
- run: `33244399213`
- job: `99079231424`
- attempt: `1`
- event: `workflow_dispatch`
- build HEAD: `573ba79f2a0a0ba534993d314e113d2f9fb7d1c5`
- exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- exact dc95 verification: success
- retained Stage A-F reconstruction: success
- Stage G transplant: success
- Stage G pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 compile: success
- package/upload: success
- conclusion: success
- retry/rerun: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-g`
- artifact id: `9712697731`
- size: `31,416,415` bytes
- SHA-256: `38ccf37cc28cb5123b5c4018117b4f53a651bc0e77488955dddaf9093c98a7a1`

Current ARM64 authorization: **NONE**.

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

Runtime-observed TIDs, guest addresses, PC and LR values are observations only and must not be hardcoded.

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

Signal -> dynamic-waker return remains essentially immediate, so the recursive delay is before the producer signal.

## Stage F — RUNTIME COMPLETE

Runtime: `eden_log(20260829-073615).txt`

Stage F previously established the producer-side mixed branch:

Producer 0 stable slow-fast:

- inter-signal `+6.074 ms`
- corrected Waiting `+2.465 ms`
- residual `+3.610 ms`
- estimated guest CPU `+3.434 ms`
- runnable-unscheduled `+0.373 ms`
- Arbitration `+2.381 ms`

Producer 1 stable slow-fast:

- inter-signal `+7.100 ms`
- corrected Waiting `+3.047 ms`
- residual `+4.054 ms`
- estimated guest CPU `+3.904 ms`
- runnable-unscheduled `+0.354 ms`
- Arbitration `+2.881 ms`

Waiting is about 96% Arbitration for both producers in both regimes.

Do not collapse the CPU and Arbitration branches.

## Stage G — RUNTIME COMPLETE

Runtime:

`eden_log(20260829-093642).txt`

Stage G goal:

> attribute only the Stage F producer CPU branch to saved guest PC/LR contexts at scheduler switch-out.

### Stable runtime windows

Raw QueueBuffer cadence:

- frame 120: 109 swap2 / 11 swap3 — startup mixed
- frame 240: 120 swap2 — pure, but Stage F/G not armed yet
- frame 360: 94 swap2 / 26 swap3 — mixed/load transition
- frames `480, 600, 720, 840`: pure swap2
- frame `960`: 44 swap2 / 76 swap3 — transition/hitch, excluded
- frames `1080, 1200, 1320`: pure swap3

Stage F dynamically settled in this run on observed:

- promoted key `0x210b65b39c`
- producer 0 `tid=0x80`
- producer 1 `tid=0x81`
- cores `1 / 2`
- priority `44 / 44`
- candidate overflow `0`
- tracking switch `0`

These are observations only.

### Stage F trend reproduced in the Stage G run

Producer 0 interval-weighted stable comparison:

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 6.001 ms | 11.525 ms | +5.524 ms |
| corrected Waiting | 5.017 ms | 7.171 ms | +2.153 ms |
| residual | 0.984 ms | 4.354 ms | +3.369 ms |
| Stage F CPU | 0.922 ms | 4.096 ms | +3.173 ms |
| runnable-unscheduled | 0.257 ms | 0.628 ms | +0.371 ms |
| Arbitration | 4.833 ms | 6.864 ms | +2.031 ms |

Producer 1:

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 7.402 ms | 13.833 ms | +6.431 ms |
| corrected Waiting | 6.185 ms | 8.912 ms | +2.727 ms |
| residual | 1.216 ms | 4.921 ms | +3.705 ms |
| Stage F CPU | 1.089 ms | 4.679 ms | +3.589 ms |
| runnable-unscheduled | 0.357 ms | 0.678 ms | +0.321 ms |
| Arbitration | 5.981 ms | 8.572 ms | +2.592 ms |

The mixed CPU + Arbitration conclusion reproduces cleanly.

### Stage G CPU reconciliation

Stage G scheduler `cpuTicks` per producer interval vs Stage F CPU:

| producer | Stage G swap2 | Stage F swap2 | Stage G swap3 | Stage F swap3 |
|---|---:|---:|---:|---:|
| 0 | 0.92233 ms | 0.92206 ms | 4.09551 ms | 4.09553 ms |
| 1 | 1.08955 ms | 1.08929 ms | 4.67808 ms | 4.67864 ms |

This reconciliation is effectively exact at the aggregate level.

Stage G sanity in armed stable windows:

- `unknownN=0`
- `identitySwitch=0`
- `missingStart=0`
- `malStart=0`
- `malTicks=0`
- `clockMismatch=0`
- priority/core metadata stable

Instrumentation-mismatch decision-map case C is closed.

### Recurring saved guest contexts

Interpretation guard:

Stage G assigns a completed scheduler slice's exact `tick_diff` to the saved guest `PC/LR` at switch-out. It measures a slice-end execution context, not literal time spent executing the instruction at that PC.

The dominant reported exact context family uses only two observed saved PCs:

- `0x85f12528`
- `0x85f12420`

Dominant observed LR values include:

- `0x85edea8c`
- `0x85edeb40`
- `0x85eeb78c`
- `0x85ee1058`

Producer 0 slow-fast CPU growth attribution:

- `0x85f12420 / 0x85eeb78c`: `+0.755 ms/interval` ~= 23.8%
- `0x85f12528 / 0x85edea8c`: `+0.686 ms/interval` ~= 21.6%
- `0x85f12528 / 0x85edeb40`: `+0.446 ms/interval` ~= 14.1%
- `0x85f12528 / 0x85ee1058`: `+0.055 ms/interval` ~= 1.7%
- fixed-table overflow: `+1.154 ms/interval` ~= 36.4%

Producer 1:

- `0x85f12528 / 0x85edea8c`: `+0.836 ms/interval` ~= 23.3%
- `0x85f12420 / 0x85eeb78c`: `+0.809 ms/interval` ~= 22.5%
- `0x85f12528 / 0x85edeb40`: `+0.219 ms/interval` ~= 6.1%
- `0x85f12528 / 0x85ee1058`: `+0.067 ms/interval` ~= 1.9%
- fixed-table overflow: `+1.575 ms/interval` ~= 43.9%

The four reported exact contexts explain about `61% / 54%` of producer 0 / producer 1 CPU growth. The fixed 64-context overflow is material in slow mode and must remain an explicit caveat.

Do not claim one exact PC/LR pair owns the entire producer CPU branch.

### Cross-branch observation

The same observed saved-PC family also appears in the separate Stage D dynamic-waker reports. Stage D repeatedly reports waker saved `pc=0x85f12528` with dominant observed LRs `0x85edeb40` and `0x85edea8c`; one slow window reports `pc=0x85f12420`.

Therefore the Stage G dominant saved endpoints may be a shared guest runtime/synchronization path rather than producer-specific game work.

Do not merge the producer CPU and Stage D waker CPU branches without module/call-path evidence.

### Stage E timing in the same run

Promoted-key wait-start -> producer signal across stable windows:

- observed producer 0: about `0.477 -> 3.124 ms`
- observed producer 1: about `0.522 -> 2.952 ms`
- signal -> waker return remains about `0.01 ms`

The delay remains before producer signal.

## Current causal frontier

Measured chain:

GPU command starvation
-> dominant guest submitter / victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dynamically selected producer threads
-> producer Arbitration growth + producer CPU growth
-> Stage G CPU growth resolves to a small recurring saved-PC family plus material long-tail overflow
-> the same main saved-PC family is also observed at the separate dynamic waker

The next question is not yet optimization. It is:

> what ASLR-safe guest module/caller path do these repeated saved PC/LR contexts represent?

Still open in parallel:

1. producer-side Arbitration recursion remains open;
2. Stage D dynamic-waker CPU growth remains separately open.

No optimization is justified yet.

## Exact dc95 source path for the next mapping step

Exact dc95 already tracks loaded NSO module bases and names.

`AppLoader_DeconstructedRomDirectory::Load()` stores the existing module map as `base -> module name` while loading `rtld`, `main`, `subsdk*`, `sdk`.

`AppLoader_DeconstructedRomDirectory::ReadNSOModules()` exposes it.

`AppLoader_NCA::ReadNSOModules()` forwards it.

This existing loader map should be reused for ASLR-safe `module+offset` normalization. Do not build a second broad module discovery system.

## Immediate next action / authorization gate

Next action document:

`NEXT_ACTION_WAKER_STAGE_H.md`

Stage H goal:

> map only the already-selected Stage G saved PC/LR contexts to ASLR-safe guest `module+offset` call paths using the existing exact-dc95 NSO module map.

Do not widen the Stage G 64-slot histogram yet. First map the repeated dominant family.

Current ARM64 authorization: **NONE**.

A fresh `ㄱㄱ` at this point authorizes **Stage H implementation + Ubuntu/static validation only**.

It does **not** authorize an ARM64 build.

After Stage H implementation/static validation is reported, a separate fresh `ㄱㄱ` is required for exactly one ARM64 attempt. Failure never authorizes retry/rerun.