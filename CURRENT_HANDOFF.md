# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-h-module-callpath-mapping`
- Stage H base repository HEAD: `59cbc61cafe8c1ae7360dc7e04e6f884c7a74512`

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
- Stage H implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`
- next action: `NEXT_ACTION_WAKER_STAGE_H.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

Runtime-observed TIDs, guest addresses, PC and LR values are observations only and must not be hardcoded.

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current prepared workflow name:

`Build dc95 X1 Waker Stage H`

Trigger:

`workflow_dispatch` only.

Future artifact:

`Eden-dc95-X1-waker-stage-h`

Do not trigger it without a fresh explicit ARM64 authorization.

## Latest successful ARM64 build — Stage G SUCCESS

A first Stage G ARM attempt failed in pre-configure verification because a Git-Bash `/tmp/...` snapshot path was not visible to native Windows Python. It did not reach MSYS2/configure/compile and was not rerun.

After the workflow precheck was fixed, a fresh authorization was used for exactly one new attempt:

- workflow: `Build dc95 X1 Waker Stage G`
- run: `33244399213`
- job: `99079231424`
- attempt: `1`
- event: `workflow_dispatch`
- build HEAD: `573ba79f2a0a0ba534993d314e113d2f9fb7d1c5`
- exact dc95 verification: success
- retained Stage A-F reconstruction: success
- Stage G transplant/pre-configure verification: success
- MSYS2 / configure / ARM64 compile / package / upload: success
- conclusion: success
- retry/rerun: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-g`
- artifact id: `9712697731`
- size: `31,416,415` bytes
- SHA-256: `38ccf37cc28cb5123b5c4018117b4f53a651bc0e77488955dddaf9093c98a7a1`

No Stage H ARM64 attempt has occurred.

## Closed historical chain

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is adaptive mapped fast stream/re-stream.
- classic-cache fallback did not break the gameplay ceiling.
- QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- raw3->effective2 clamp did not improve upstream frame generation.
- DFPS is not root cause.
- BufferQueue free-slot/backpressure is closed as primary owner.
- GPU worker is predominantly waiting for command supply.
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint are not the missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation is closed as primary owner for both Stage D dynamic-waker and Stage F producer slowdown.

## Stage A / B — COMPLETE

Stage A observed dominant submitter/victim `tid=0x53` and one stable per-process gameplay `WaitForAddress / WaitIfEqual / timeout=-1` key. Guest VA relocates between launches; dynamic latching is mandatory.

Stage B observed matching waker `tid=0x4f`, `SignalAndIncrementIfEqual`, value `1`, count `-1`, one matching signal per rendered frame. Victim wait ~= wait-start -> signal (`w2s`), while signal -> victim return (`s2e`) is essentially zero. The long delay is before the waker signal.

## Stage C — RUNTIME COMPLETE

Runtime: `eden_log(20260828-173023).txt`

- stable fast inter-signal `33.722 ms`, Waiting `27.708 ms`, residual `6.014 ms`
- stable slow inter-signal `55.022 ms`, Waiting `34.183 ms`, residual `20.839 ms`

Stage C total Waiting remains valid. Its old entry-only named reason breakdown is invalid and discarded.

## Stage D — RUNTIME COMPLETE

Runtime: `eden_log(20260829-024002).txt`

Stable slow-fast:

- inter-signal `+23.518 ms`
- corrected Waiting `+9.190 ms`
- residual `+14.327 ms`
- estimated dynamic-waker CPU `+14.276 ms`
- runnable-unscheduled only `+0.068 ms`

Corrected slow Waiting is overwhelmingly Arbitration (`7.440 -> 32.339 ms`). Host scheduler starvation is closed for the waker. The separate dynamic-waker CPU growth branch remains open.

## Stage E — RUNTIME COMPLETE

Runtime: `eden_log(20260829-063358).txt`

Direct `WaitForAddress` timing reconciles with Stage D corrected Arbitration. The promoted key is repeated short synchronization, roughly 8-10 waits/frame: fast about `0.5-0.6 ms` each, slow about `2.7-3.2 ms` each.

Observed dominant signalers were `0x80 / 0x81`. Signal -> dynamic-waker return remains ~immediate, so the recursive delay is before producer signal.

## Stage F — RUNTIME COMPLETE

Runtime: `eden_log(20260829-073615).txt`

Producer 0 stable slow-fast:

- inter-signal `+6.074 ms`
- corrected Waiting `+2.465 ms`
- residual `+3.610 ms`
- estimated guest CPU `+3.434 ms`
- runnable-unscheduled `+0.373 ms`
- Arbitration `+2.381 ms`

Producer 1:

- inter-signal `+7.100 ms`
- corrected Waiting `+3.047 ms`
- residual `+4.054 ms`
- estimated guest CPU `+3.904 ms`
- runnable-unscheduled `+0.354 ms`
- Arbitration `+2.881 ms`

Waiting is about 96% Arbitration. Keep CPU and Arbitration branches separate.

## Stage G — RUNTIME COMPLETE

Runtime: `eden_log(20260829-093642).txt`

Clean comparison windows:

- pure swap2: frames `480, 600, 720, 840`
- frame `960` transition excluded
- pure swap3: frames `1080, 1200, 1320`

Stage G scheduler `cpuTicks` per producer interval reconcile almost exactly with Stage F CPU:

| producer | Stage G swap2 | Stage F swap2 | Stage G swap3 | Stage F swap3 |
|---|---:|---:|---:|---:|
| 0 | 0.92233 ms | 0.92206 ms | 4.09551 ms | 4.09553 ms |
| 1 | 1.08955 ms | 1.08929 ms | 4.67808 ms | 4.67864 ms |

Stable sanity counters are clean:

- `unknownN=0`
- `identitySwitch=0`
- `missingStart=0`
- `malStart=0`
- `malTicks=0`
- `clockMismatch=0`

Therefore instrumentation mismatch is closed.

Stage G assigns each completed scheduler slice's exact `tick_diff` to the saved guest PC/LR at switch-out. This is a **slice-end execution context**, not literal time spent executing that one instruction.

Recurring observed saved PCs:

- `0x85f12528`
- `0x85f12420`

Dominant observed LR family includes:

- `0x85edea8c`
- `0x85edeb40`
- `0x85eeb78c`
- `0x85ee1058`

Four reported exact PC/LR contexts explain about `61% / 54%` of producer 0 / 1 CPU growth. Fixed 64-context overflow explains another material `36% / 44%` of slow-fast growth. Do not claim one PC/LR pair owns the whole branch.

The same saved-PC family also appears in the separate Stage D dynamic-waker reports, suggesting a shared runtime/synchronization endpoint is possible. Do not merge branches without module/caller evidence.

## Stage H — IMPLEMENTED / UBUNTU STATIC COMPLETE

Implementation record:

`DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`

Branch:

`exp/x1-waker-stage-h-module-callpath-mapping`

Goal:

> normalize only the already-selected Stage G saved PC/LR contexts to ASLR-safe guest `module+offset` identities.

### Implementation shape

Stage H reuses exact dc95's existing static NSO load truth in `AppLoader_DeconstructedRomDirectory::Load()`.

After each existing successful module load and `modules.insert_or_assign(load_addr, module)`, the transplant emits one bounded loader line under the existing address-arbiter diagnostic setting:

`[X1-WAKERH] module=<name> base=<guest VA> end=<guest VA> size=<bytes>`

No second module discovery system is created.

Offline analyzer:

`tools/adreno_lab/analyze_x1_waker_stage_h_module_mapping.py`

It joins Stage H ranges to Stage G top contexts and emits canonical identities such as `main+0x...` / `sdk+0x...`, retaining raw PC/LR for audit.

Stage H does **not**:

- add a scheduler hook;
- alter Stage G hot-path PC/LR sampling;
- widen `ContextSlotCount=64`;
- hardcode observed TIDs, promoted address, PC or LR;
- add per-switch logging;
- mutate priority/affinity/yield/reschedule/waits/signals/GPU/QueueBuffer/cadence.

### Ubuntu static validation

- workflow: `Validate dc95 X1 Waker Stage H`
- run: `33246317401`
- job: `99084287770`
- attempt: `1`
- validation HEAD: `d39bfa3a814467f3b009202d626d4ee872db73f5`
- runner: `ubuntu-latest`
- conclusion: `success`

Passed:

- exact dc95 HEAD preserved;
- transplant applies cleanly;
- `git diff --check`;
- transplant/analyzer `py_compile`;
- one bounded `[X1-WAKERH]` log site;
- existing module-map insertion/debug behavior preserved;
- scheduler byte-for-byte unchanged by Stage H;
- no hardcoded runtime observations;
- no behavior-mutation tokens;
- synthetic module+offset analyzer join with raw-address audit preservation.

Temporary Ubuntu workflow was deleted after success.

## Current causal frontier

Measured chain:

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dynamically selected producer threads
-> producer Arbitration growth + producer CPU growth
-> Stage G resolves CPU growth to a small recurring saved-PC family plus material overflow
-> Stage H is ready to normalize that family to ASLR-safe module/caller identities

Still open in parallel:

1. producer-side Arbitration recursion;
2. separate Stage D dynamic-waker CPU growth.

No optimization is justified yet.

## Immediate next action / authorization gate

Current ARM64 authorization: **NONE**.

Stage H implementation/static is complete. No Stage H ARM64 attempt has occurred.

A fresh `ㄱㄱ` after this handoff authorizes exactly **one** Stage H ARM64 attempt using:

- branch `exp/x1-waker-stage-h-module-callpath-mapping`
- workflow `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

The workflow is `workflow_dispatch` only.

No retry/rerun/second attempt is allowed without another fresh explicit authorization, even if the single attempt fails.
