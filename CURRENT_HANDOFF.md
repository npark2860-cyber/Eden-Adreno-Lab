# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-j-caller-depth`
- Stage J branch base: `70d20a1cfdb5437d86bc06c52bd2fe05e3966412`
- latest successful ARM binary remains Stage H, build HEAD `1c8b699ccc51ff7bca28fc57bf654c1e18fbd5f2`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Failure does not authorize retry/rerun. Current authorization: NONE.**

Ubuntu/static validation does not consume ARM64 authorization.

Runtime-observed TIDs, guest addresses, module bases, promoted keys, PC and LR values are observations only and must not be hardcoded.

No broad/all-thread profiling and no behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

## Primary records

- Stage B runtime: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- Stage F runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- Stage G runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- Stage H implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`
- Stage H ARM build: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_BUILD.md`
- Stage H runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- Stage I SDK disassembly: `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- Stage J implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_J_IMPLEMENTED.md`
- next action: `NEXT_ACTION_WAKER_STAGE_J.md`

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current prepared workflow:

`Build dc95 X1 Waker Stage J`

Trigger:

`workflow_dispatch` only.

Expected future artifact if separately authorized and successful:

`Eden-dc95-X1-waker-stage-j`

As of Stage J preparation, Stage J branch Actions history contains only two Ubuntu `push` validation runs. Stage J `workflow_dispatch` / Windows ARM64 run count = **0**.

## Latest successful ARM64 build — Stage H

- workflow: `Build dc95 X1 Waker Stage H`
- run: `33246620972`
- job: `99085091095`
- attempt: 1
- event: `workflow_dispatch`
- build HEAD: `1c8b699ccc51ff7bca28fc57bf654c1e18fbd5f2`
- exact dc95 / A-G reconstruction / H verification / configure / compile / package / upload: success
- retry/rerun/additional ARM attempt: none

Artifact:

- `Eden-dc95-X1-waker-stage-h`
- ID `9713380302`
- size `31,419,464` bytes
- SHA-256 `ff166f3f39c695c1e8e879a7ecbfeca2916028f3318802123bed584775fe4d90`

## Closed historical causal chain

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplicates; blind dedupe rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path = adaptive mapped fast stream/re-stream.
- classic-cache fallback did not break gameplay ceiling.
- QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS; VI ~= 60 Hz.
- raw3->effective2 clamp did not improve upstream frame generation.
- DFPS not root.
- BufferQueue free-slot/backpressure not primary owner.
- GPU worker predominantly waits for command supply.
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint not the missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation closed for dynamic-waker and producer slowdown.

## Stage A-G summary

Measured chain:

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dynamically selected producer threads
-> producer Arbitration growth + producer CPU growth
-> recurring Stage G slice-end PC/LR family plus material overflow.

Stage G exact scheduler `cpuTicks` reconcile almost exactly with Stage F CPU. The saved PC/LR is a scheduler switch-out context, not literal instruction residence time.

Important Stage D caveat: Stage D reports one `latest_pc` plus an independent LR histogram. Stage D PC and LR entries are not correlated pairs.

## Stage H runtime — COMPLETE

Runtime:

`eden_log(20260829-103238).txt`

Loaded modules:

- rtld `0x80758000-0x8075c000`
- main `0x8075c000-0x84e87000`
- subsdk0 `0x84e87000-0x85530000`
- sdk `0x85530000-0x86309000`

Recurring Stage G contexts normalized to:

- `sdk+0x158528 / sdk+0x124a8c`
- `sdk+0x158420 / sdk+0x13178c`
- `sdk+0x158528 / sdk+0x124b40`
- `sdk+0x158528 / sdk+0x127058`

Thus Stage H decision-map case A was selected: one shared Nintendo SDK/runtime family, not visible producer-specific `main` work.

Current-run producer fast->slow reproduced mixed CPU + Arbitration growth:

- P0 CPU `0.864 -> 4.662 ms`, Arbitration `4.780 -> 8.962 ms`
- P1 CPU `1.066 -> 5.144 ms`, Arbitration `6.283 -> 10.894 ms`

Dynamic-waker current-run:

- CPU `5.871 -> 25.840 ms`
- runnable-unscheduled `0.232 -> 0.244 ms`
- Arbitration `5.837 -> 37.739 ms`

Host scheduler starvation remains rejected. Keep producer CPU, producer Arbitration, dynamic-waker CPU, and dynamic-waker Arbitration branches distinct unless direct evidence joins them.

## Stage I SDK semantic mapping — COMPLETE

Exact uploaded dump set included `sdk-B9046C31EB5D31271BE970FE732D38DF49C6AA21.nso` plus exact `main`, `rtld`, and `subsdk0` images.

Recovered exact SDK symbols/instructions:

### `sdk+0x158528`

Immediately after `svc #0x34` -> exact dc95 `WaitForAddress`.

### `sdk+0x158420`

Immediately after `svc #0x1a` -> exact dc95 `ArbitrateLock`.

### LR caller functions

- `sdk+0x124a8c` and `sdk+0x124b40` are inside `nn::os::WaitLightEvent(nn::os::LightEventType*)`, calling `WaitForAddress(WaitIfEqual, value=1, timeout=-1)`.
- `sdk+0x127058` is inside `nn::os::ReceiveLightMessageQueue(...)`, also calling `WaitForAddress(WaitIfEqual, value=1, timeout=-1)`.
- `sdk+0x13178c` is inside `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`, following `ArbitrateLock`.
- Stage D occasional `sdk+0x13f364` is in `nn::sf::hipc::SendSyncRequest(...)`, but must not be paired with Stage D PC because Stage D PC/LR are independent observations.

### Per-slice key result

The visible CPU-growth branch is not explained by simply issuing more waits.

Examples fast->slow CPU/slice:

- P0 WaitLightEvent `0.228 -> 0.742 ms` (`3.25x`)
- P0 critical section `0.073 -> 0.492 ms` (`6.78x`)
- P1 WaitLightEvent `0.223 -> 0.650 ms` (`2.92x`)
- P1 critical section `0.079 -> 0.430 ms` (`5.48x`)

WaitLightEvent slice counts fall or remain similar while active CPU/slice rises strongly. Therefore two parallel slow effects remain:

1. longer kernel Arbitration waiting;
2. longer active guest CPU slices before reaching the synchronization blocker.

The exact active instruction owner inside those longer slices is still open.

Static reverse-call inspection found 73 direct `main` call sites to `WaitLightEvent` and 4 to `ReceiveLightMessageQueue`; first-level offline reverse mapping is not unique enough.

## Stage J — IMPLEMENTED / UBUNTU STATIC COMPLETE

Branch:

`exp/x1-waker-stage-j-caller-depth`

Goal:

> obtain exactly one caller level above the known SDK synchronization function for only the two Stage F dynamically selected producers.

Implementation files:

- `src/core/x1_waker_stage_j_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_j_caller_depth.py`
- `tools/adreno_lab/analyze_x1_waker_stage_j_caller_depth.py`

The relevant SDK functions preserve standard AArch64 frame records. At the existing Stage G selected-producer switch-out block Stage J:

- reuses saved `fp` (`x29`);
- validates guest `[fp+8, fp+16)`;
- performs exactly one `ApplicationMemory().Read64()` when valid;
- records `(pc, lr, parent_lr)` with the same exact scheduler `tick_diff`;
- uses 2 producers, fixed 64 slots, top 4, 120-frame cadence.

No new scheduler hook, thread discovery, broad sampling, Stage G slot widening, per-switch logging, or behavior mutation.

### Ubuntu validation history

Attempt 1:

- run `33249591877`
- job `99092859932`
- failed only because the transplant's own hardcode self-check scanned the literal forbidden-value list containing `0x80`.
- exact dc95 and retained A-H reconstruction had already succeeded.

Self-check was fixed to inspect generated insertion/profiler code rather than its own literal guard list.

Attempt 2:

- run `33249656888`
- job `99093038064`
- event `push`
- result **SUCCESS**.

Passed full exact-dc95 A-H reconstruction, one-read/fp/selected-producer guard checks, unchanged F/G/H invariants, no behavior mutation, no observation hardcodes, and synthetic module+offset triple normalization.

Temporary validator deleted after success.

## Current causal frontier

GPU starvation
-> submitter/waker chain
-> repeated producer-side SDK synchronization
-> exact SDK blockers identified
-> active CPU slices leading to blocker become much longer in slow cadence
-> Stage J is statically ready to recover one parent caller level for only the selected producers.

No optimization is justified yet.

## Immediate next action — fresh ARM authorization required

Read:

`NEXT_ACTION_WAKER_STAGE_J.md`

Current ARM64 authorization: **NONE**.

Do not dispatch/build/rebuild/rerun until the user gives a new explicit authorization.

A fresh `ㄱㄱ` after this ready state authorizes exactly one Stage J Windows ARM64 attempt. Before dispatch, verify branch HEAD, persistent `workflow_dispatch`-only trigger, and Stage J ARM run count still 0.
