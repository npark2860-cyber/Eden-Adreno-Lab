# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-31 KST

## Fixed baseline / rules

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Immutable control branch:

`lab/dc95-arm64-baseline`

**Never change the exact Eden baseline without explicit baseline-change approval.**

### ARM64 authorization rule — ABSOLUTE

- no Windows ARM64 build/rebuild/rerun without fresh explicit user authorization;
- one authorization = exactly one ARM attempt;
- failure does not authorize retry/rerun;
- no automatic retry;
- persistent ARM workflow must remain `workflow_dispatch` only;
- current ARM64 authorization: **NONE**.

Ubuntu/static validation and offline NSO analysis do not consume ARM64 authorization.

Runtime TIDs, raw guest addresses, promoted keys, module bases, PC/LR/caller addresses are observations only. Never hardcode them. Durable address knowledge must remain ASLR-normalized `module+offset`.

No broad/all-thread profiling. No behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

Do not create Stage L merely to add stack depth.

Do not implement a behavior-changing optimization before concrete runtime work-target attribution exists.

## Read these records first

- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_ARM_BUILD_FAILURE.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_SHADOW_FIX.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`

Use GitHub documents as source of truth. Do not reconstruct project state from chat guesses.

## Repository state at this handoff

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Source/workflow cleanup HEAD immediately before the final docs-only handoff updates:

`75c9671aa0c5387e3a9b56fc18d4c216980bfdbe`

That commit removed the temporary Ubuntu Stage K shadow validator after its single successful validation run.

Relevant state-changing source commit before that cleanup:

`b22306fa55690e99aac94f521d302caa27893754`

That commit contains only the minimal Stage K helper-parameter shadow repair.

Docs-only commits after cleanup include:

- `f437d5ff6856ed8c87087f2fca591de1e9cb4c7d` — shadow-fix validation record
- `e3fd4a49cfb2548721260402688088028149e921` — advance next action to ARM authorization gate

Verify the actual branch HEAD at the start of the next tab before source work.

No source, workflow, or baseline change is authorized by this handoff itself.

## Persistent Windows ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

No push/pull-request ARM trigger is enabled.

Current ARM64 authorization:

**NONE**

## Previous successful Stage K Windows ARM64 build

This remains the only successful Stage K Windows ARM artifact/runtime base and predates the x26 work-target identity extension.

- workflow run: `33287796384`
- job: `99193953965`
- attempt: `1`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- result: **SUCCESS**
- artifact: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- size: `31,427,618` bytes
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- retry/rerun: none

## Primary previous Stage K runtime source

Res1X log:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Facts:

- `Renderer.resolution_setup: Res1X`
- unsupported BlitScaleHelper depth-scaling errors: `0`
- late Stage K windows: `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- tiny sporadic `parentUnavailable` only

The Res2X capture remains invalid for resolution-sensitivity inference because the visible image showed approximately the upper-left quarter only and the log contained `19,776` unsupported depth-scaling errors.

## Strict cadence windows

Use only pure QueueBuffer cadence windows:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows `840` and `1200` are not primary evidence.

## Known SDK semantics

Exact Stage I mappings:

- `sdk+0x158528` = return after `WaitForAddress`
- `sdk+0x158420` = return after `ArbitrateLock`
- `sdk+0x124a8c / +0x124b40` = `WaitLightEvent`
- `sdk+0x127058` = `ReceiveLightMessageQueue`
- `sdk+0x13178c` = `InternalCriticalSectionImplByHorizon::Enter`
- `sdk+0x127e54` = `LockMutex`

## Stage K semantic mapping — CLOSED

Canonical record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`

Exact durable grandparent classifications:

| Captured grandparent LR | Durable classification |
|---|---|
| `main+0x86a490` | shared dependency-worker callback into dispatcher |
| `main+0x86bc9c` | **EventModuleSubWorker** virtual coordination/execution path |
| `main+0x2a2d958` | generic indirect thread/message-dispatch frontier |
| `main+0x86a530` | shared dispatcher LockMutex site A |
| `main+0x86a678` | shared dispatcher LockMutex site B |

`main+0x86a464` is reused by at least:

- `ModuleSystemWorker`
- `NavMeshDepWorker`
- `NavMeshCAStepDepWorker`
- `phive::DepWorker`

Therefore that shared callback is not a unique gameplay owner.

`main+0x86bc04` resolves through vtable/constructor/registration to concrete owner:

**EventModuleSubWorker**

Exact path:

`EventModuleSubWorker -> main+0x86bc04 -> main+0x86bd40 -> selected-object virtual operation -> nn::os::WaitLightEvent`

Keep EventModuleSubWorker separate from the shared ModuleSystem work-target histogram.

## ModuleSystem work-target static mapping — CLOSED

Exact shared execution pointer flow:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Facts:

- `main+0x11d1b14` constructs a 41-slot ModuleSystem list;
- all 41 slots are statically mapped;
- 36 unique concrete `vtable+0x60` targets;
- slots 17 and 37 deliberately have empty names and execute `main+0x26a7fc0: RET`; keep them unnamed no-op components.

The remaining problem is runtime selection: which concrete ModuleSystem target dominates the expensive shared-worker slices in strict swap2 vs swap3 cadence.

## Previous strict Stage K slow/fast correlation

From the primary Res1X capture:

- shared DepWorker callback `main+0x86a490`: P0 `2.130x`, P1 `2.164x`
- **EventModuleSubWorker** `main+0x86bc9c`: P0 `5.590x`, P1 `2.961x`
- generic queue/message frontier `main+0x2a2d958`: P0 `1.232x`; P1 approximately `1.179x` from visible slow windows
- shared dispatcher LockMutex `main+0x86a530`: P1 `4.870x`; P0 slow/fast `>3.684x` because fast frame 960 is top4-censored
- `main+0x86a678`: recurring slow LockMutex subfamily; exact aggregate unavailable because of top4 censoring

The generic queue-entry family grows much less than EventModuleSubWorker and shared-dispatch synchronization families.

## Stage K x26 work-target identity extension

Design decision:

Use saved guest `x26`, not another stack level.

Runtime resolver:

`x26 node -> [node] work object -> [work] vtable -> [vtable+0x10] shim -> [vtable+0x60] concrete work target`

Existing Stage G context supplies saved x26 through:

`x1_stage_g_context.r[26]`

Instrumentation remains bounded:

- existing selected producers only;
- existing guest-context sample reused;
- no new stack walk;
- no second context capture;
- normalized shim/work offsets stored rather than raw ASLR VAs;
- 64 bounded pair slots per producer;
- top4 every 120 frames;
- resolved / other-resolved / overflow / resolver-status accounting;
- no runtime hardcode of known component targets.

Analyzer owns the static semantic map.

## Compatibility implementation currently in branch

Full resolver transplant implementation:

`tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth_impl.py`

Persistent-verifier compatibility wrapper:

`tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

Stage K main-range registration is emitted through the existing Stage H loader transplant so the Stage K compatibility pass does not change the loader in a way that violates the historical persistent verifier shape.

Relevant compatibility commits:

- `de634472054d78ad6b3b05dda73791d0dcb58953`
- `e8cf2597ca4028f31d59c49f234812125b3594e1`
- `e1026b6d8cde61f0f4e08e2dcb461b289876b381`

Historical Stage K validator restoration:

- commit: `6aed649e0c303866a141cebd59be314befc4cf13`
- validator run: `33351875686`
- job: `99366704957`
- attempt: `1`
- result: **SUCCESS**

Validator cleanup:

`5cf098df6b413d1c3ab8b95385bc4845eb6e6d1c`

## First authorized x26 Windows ARM64 attempt — FAILED

Canonical record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_ARM_BUILD_FAILURE.md`

- persistent workflow run: `33351947642`
- job: `99366911164`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `5fa3b5fb59c5935eb9d48c4d6ea8f0faa52373c7`
- result: **FAILURE**
- artifact: **none**
- retry/rerun: **none**

Actual C++ compilation failed in generated `src/core/hle/kernel/k_scheduler.cpp` under `-Werror,-Wshadow` because the compatibility helper parameter `x1_stage_k_node` shadowed an already-live outer local of the same name.

No new runtime evidence exists from that attempt.

## Work-target shadow repair — COMPLETE

Canonical record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_SHADOW_FIX.md`

Repair commit:

`b22306fa55690e99aac94f521d302caa27893754`

Minimal repair:

- rename helper parameter `x1_stage_k_node` -> `x1_stage_k_node_value`;
- update only the three helper-body references to that parameter;
- preserve outer saved-x26 logic and all resolver semantics/invariants.

No selected-producer scope, read count, context capture, histogram layout, baseline, persistent ARM workflow, or runtime behavior was changed.

### Ubuntu/static regression validation — SUCCESS

- workflow: `Validate dc95 X1 Waker Stage K`
- run: `33392096685`
- job: `99487889955`
- head SHA: `72e32bbbfd4454f2fdbd9465fb5bf1b0be5ba557`
- attempt: `1`
- runner: `ubuntu-latest`
- result: **SUCCESS**

The validation reconstructed exact dc95 through Stage K and explicitly confirmed the generated helper no longer uses the conflicting parameter spelling.

Temporary validator cleanup:

`75c9671aa0c5387e3a9b56fc18d4c216980bfdbe`

No persistent automatic Ubuntu validator remains.

This closes the deterministic shadow blocker only at the static/generated-source level. It is not Windows ARM64 compile/runtime proof.

## Current causal frontier

Measured chain remains:

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two selected producer threads
-> producer CPU growth + producer Arbitration growth
-> exact Nintendo SDK blocker semantics
-> Stage J main/LockMutex parent
-> Stage K concrete main grandparent
-> offline semantic resolution
-> **EventModuleSubWorker concrete branch + shared dependency-worker / ModuleSystem dispatcher branch**
-> 41 statically-known ModuleSystem slots / 36 unique work targets
-> x26 runtime work-target resolver implemented
-> helper `-Wshadow` source defect repaired and Ubuntu-static validated
-> **current gate: fresh Windows ARM64 authorization**
-> runtime work-target identity still unobserved.

## Immediate next action

Current ARM64 authorization:

**NONE**

The source repair and required non-ARM/static validation are complete.

Stop at the ARM authorization gate.

Do not rerun run `33351947642` or job `99366911164` and do not dispatch a new Windows ARM64 attempt without fresh explicit user authorization.

One future fresh authorization permits exactly one new ARM attempt. No automatic retry.

Before any future authorized attempt, verify:

1. branch remains `exp/x1-waker-stage-k-grandparent-depth`;
2. fixed baseline remains `dc95cd09eea9749250fe31a3072684d341d19417`;
3. persistent workflow remains `Build dc95 X1 Waker Stage K` / `workflow_dispatch` only;
4. build source contains repair commit `b22306fa55690e99aac94f521d302caa27893754` or its exact descendant repair.

If a future build succeeds and produces an artifact, the project reaches the **user-test gate**: user runs Res1X and supplies a new Stage K log containing the work-target pair fields.

Then analyze:

- normalized common-shim/work-target pairs;
- ModuleSystem component identities;
- `workResolvedTicks`;
- `workOtherResolvedTicks`;
- `workOverflowTicks`;
- resolver-status coverage;
- strict equal-window swap2 vs swap3 visible lower-bound target ticks.

## Closed historical findings — do not reopen without new evidence

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
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint are not the missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation is closed as primary owner for dynamic-waker and selected-producer slowdowns.

## New-tab startup instruction

On a fresh tab:

1. use GitHub documents as source of truth;
2. verify branch `exp/x1-waker-stage-k-grandparent-depth` and actual HEAD;
3. verify fixed baseline is still `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`;
4. verify `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml` remains `Build dc95 X1 Waker Stage K` / `workflow_dispatch` only;
5. verify ARM64 authorization is **NONE**;
6. read `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_SHADOW_FIX.md` and `NEXT_ACTION_WAKER_STAGE_K.md` before any source/build action;
7. treat five-grandparent semantic mapping, EventModuleSubWorker attribution, ModuleSystem 41-slot static mapping, and x26 work-target design as closed;
8. treat the helper shadow repair and Ubuntu-static validation as complete;
9. without fresh ARM authorization, do not perform a Windows ARM build/rerun;
10. do not create Stage L;
11. do not implement a behavior-changing optimization before runtime work-target attribution.
