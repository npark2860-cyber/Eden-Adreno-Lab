# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-31 KST

## Fixed baseline / rules

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Immutable control branch:

`lab/dc95-arm64-baseline`

Current experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Failure does not authorize retry/rerun. Current authorization: NONE.**

Ubuntu/static validation and offline NSO analysis do not consume ARM64 authorization.

Runtime TIDs, raw guest addresses, promoted keys, module bases, PC/LR/caller addresses are observations only. Never hardcode them. Durable address knowledge must remain ASLR-normalized `module+offset`.

No broad/all-thread profiling. No behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

No optimization is justified yet.

Do not create Stage L merely to add stack depth.

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
- `NEXT_ACTION_WAKER_STAGE_K.md`

Use GitHub documents as source of truth rather than reconstructing state from chat guesses.

## Persistent Windows ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

No push-triggered ARM build is enabled.

Current ARM64 authorization: **NONE**.

The work-target implementation has **not** been Windows ARM64 built or run yet.

## Previous Stage K Windows ARM64 build history

### Pre-scope-fix attempt — FAILED

- run: `33254495504`
- job: `99105748612`
- attempt: `1`
- build/source HEAD: `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- C++ build: **FAILED**
- artifact: none
- retry/rerun: none

Root cause was the Stage K lexical-scope defect fixed by:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

The earlier enum-name mismatch theory is rejected.

Scope-fix Ubuntu regression gate:

- run: `33279373418`
- job: `99171791300`
- validation HEAD: `3f0843208512d2878f8f02a8c7938216bf5ecf21`
- result: **SUCCESS**

Temporary validator cleanup:

`404a14af5a607762bd121dd98190d63c5c4466c0`

### Previous Stage K Windows ARM64 attempt — SUCCESS

A fresh explicit authorization was consumed for exactly one attempt.

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- compile/package/upload: **SUCCESS**
- retry/rerun/additional ARM attempt: none

One-shot dispatcher lifecycle:

- creation/dispatch commit: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- removal commit: `112541623742853bdb1c6114959f5bb5317cde89`

Canonical artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- size: `31,427,618` bytes
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`

This previous artifact predates the newly implemented x26 work-target identity extension.

## Previous Stage K runtime captures

### Res2X — invalid for resolution-sensitivity inference

Log:

`eden_log(20260830-025816).txt`

SHA-256:

`89784845234bd896149c61b9a856ab3b8b720b6588d6a9bb6a38b34a5755d2cf`

User observation:

- visible image showed approximately the upper-left quarter only.

Unsupported depth scaling:

- D32_FLOAT: `12,091`
- D16_UNORM: `7,685`
- total: **19,776**

Do not use subjective Res2X speed as CPU-vs-GPU evidence.

### Res1X — primary previous Stage K runtime source

Log:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Facts:

- `Renderer.resolution_setup: Res1X`
- unsupported BlitScaleHelper depth-scaling errors: `0`
- late Stage K windows: `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- tiny sporadic `parentUnavailable` only

The chat contains no explicit textual statement that visible Res1X rendering returned to normal. Do not invent that observation.

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

## Stage K grandparent semantic mapping — COMPLETE

Canonical record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`

Record commit:

`ade4a399c69de100a9e249c3def1841f90069359`

Exact dumped TOTK 1.2.1 main image:

`main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`

Exact mapping:

| Captured grandparent LR | Exact enclosing function | LR-producing instruction | Durable classification |
|---|---|---|---|
| `main+0x86a490` | `main+0x86a464` | `main+0x86a48c: BL main+0x86a4ac` | shared dependency-worker callback into dispatcher |
| `main+0x86bc9c` | `main+0x86bc04` | `main+0x86bc98: BL main+0x86bd40` | **EventModuleSubWorker** virtual coordination/execution path |
| `main+0x2a2d958` | `main+0x2a2d8a0` | `main+0x2a2d954: BLR x8` | generic indirect thread/message-dispatch frontier |
| `main+0x86a530` | `main+0x86a4ac` | `main+0x86a52c: BL main+0x2b17270` | shared dispatcher LockMutex site A |
| `main+0x86a678` | `main+0x86a4ac` | `main+0x86a674: BL main+0x2b17270` | shared dispatcher LockMutex site B |

Relevant imported targets:

- `main+0x2b17270` = `nn::os::LockMutex`
- `main+0x2b17280` = `nn::os::UnlockMutex`
- `main+0x2b17b50` = `nn::os::WaitLightEvent`
- `main+0x2b17c50` = `nn::os::SignalLightEvent`
- `main+0x2b183d0` = `nn::os::ReceiveLightMessageQueue`

## Shared dependency-worker result

`main+0x86a464` is a concrete virtual callback reached from common light-message loop `main+0x2a90478`.

The same implementation is reused by:

- `ModuleSystemWorker`
- `NavMeshDepWorker`
- `NavMeshCAStepDepWorker`
- `phive::DepWorker`

Therefore the shared callback itself is not a unique gameplay owner.

`main+0x86a4ac` is the synchronization-heavy dispatcher. Important sites:

- `main+0x86a52c` -> LockMutex
- `main+0x86a674` -> LockMutex
- `main+0x86a81c` -> WaitLightEvent
- `main+0x86a988` -> queued work-object virtual execution

Thus `main+0x86a490`, `main+0x86a530`, and `main+0x86a678` are observations inside the same shared dependency-worker infrastructure.

## EventModuleSubWorker result

`main+0x86bc04` resolves through vtable/constructor/registration to:

**`EventModuleSubWorker`**

Exact path:

`EventModuleSubWorker -> main+0x86bc04 -> main+0x86bd40 -> selected-object virtual operation -> nn::os::WaitLightEvent`

This remains a concrete separate branch.

## ModuleSystem work-target static mapping — COMPLETE

Exact pointer flow:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Facts:

- `main+0x11d1b14` constructs a 41-slot ModuleSystem list
- all 41 slots mapped
- 36 unique concrete `vtable+0x60` targets
- component identities include `System`, `DenguModule`, `Resource`, `RSDB`, `Graphics`, `Actor`, `Physics`, `Event`, `EventModuleWorker`, `EventModuleSubWorker`, `UI`, `Sound`, `GameData`, `Blackboard`, `Camera`, `LOD`, `Rail`, `PlayReport`, and the other entries recorded in the semantic-mapping history
- slots 17 and 37 deliberately have empty names and execute `main+0x26a7fc0: RET`; keep them unnamed no-op components

## Previous strict Stage K slow/fast correlation

From the previous Res1X capture:

- shared DepWorker callback `main+0x86a490`: P0 `2.130x`, P1 `2.164x`
- **EventModuleSubWorker** `main+0x86bc9c`: P0 `5.590x`, P1 `2.961x`
- generic queue/message frontier `main+0x2a2d958`: P0 `1.232x`; P1 approximately `1.179x` from visible slow windows
- shared dispatcher LockMutex `main+0x86a530`: P1 `4.870x`; P0 slow/fast `>3.684x` because fast frame 960 is top4-censored
- `main+0x86a678`: recurring slow LockMutex subfamily; exact aggregate unavailable because of top4 censoring

The generic queue-entry family grows much less than EventModuleSubWorker and shared-dispatch synchronization families.

## Stage K work-target identity design — COMPLETE

Canonical design record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`

Design decision:

Use saved guest `x26`, not another stack level.

Exact work-dispatch anchor:

```text
main+0x86a97c: LDR x0, [x26]
main+0x86a980: LDR x8, [x0]
main+0x86a984: LDR x8, [x8, #0x10]
main+0x86a988: BLR x8
```

Exact dc95 `ThreadContext` stores `r[0..28]`, so existing Stage G context exposes saved x26 as `x1_stage_g_context.r[26]`.

## Stage K work-target identity implementation — COMPLETE / STATIC-VALIDATED

Canonical implementation record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`

Implementation commits:

- profiler: `fb91aee04fecf2a9c171163f37e58e577f24fcb9`
- x26 resolver transplant: `7419259d7dd7053033542f3a199481aa31353e76`
- analyzer mapping: `59170e90d97dc6a9676232cfba24744008ef8ce4`
- analyzer incomplete-cadence guard: `c02e0a138aa1d17f44626c4300900fcb875c6869`

Implemented resolver:

`x26 node -> [node] work object -> [work] vtable -> [vtable+0x10] shim -> [vtable+0x60] concrete work target`

Hard limits:

- existing selected producers only
- existing guest-context sample reused
- saved x26 read once
- four additional work-target `Read64` sites
- total Stage K reads: six, including two existing grandparent reads
- six Stage K range validations
- no new stack walk
- no second context capture
- dynamic `main` range registered from existing Stage H loader path
- normalization before histogram storage
- normalized `(shim_offset, work_offset)` keys only
- 64 pair slots per producer
- top4 per 120 frames
- resolved / other-resolved / overflow / resolver-status accounting
- no runtime hardcode of common shim or component targets

Analyzer owns the known common-shim and 41-slot / 36-target semantic table.

## Ubuntu validation of work-target implementation — SUCCESS

Full exact-dc95 reconstruction validator:

- workflow: `Validate dc95 X1 Waker Stage K Work Target`
- run: `33350134250`
- job: `99361721220`
- head SHA: `6cc9b75d4446aa55fa18837fe73376f8fb48d5b5`
- attempt: `1`
- result: **SUCCESS**

Focused analyzer regression gate after incomplete-cadence correction:

- run: `33350373759`
- job: `99362422228`
- head SHA: `e51dc7ec854b1afc7ef46a25f7d749e4c9584f49`
- attempt: `1`
- result: **SUCCESS**

The temporary push validator was removed at:

`09916c69671607f4d6240dc3ea3121e37372b45b`

No validator rerun was used.

These Ubuntu runs are not Windows ARM64 attempts and do not consume ARM authorization.

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

## Current causal frontier

Measured chain:

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
-> **runtime work-target identity resolver now implemented but not yet Windows ARM64 observed**.

The remaining question is which concrete ModuleSystem work target owns the expensive shared-worker slices under strict swap2 vs swap3 cadence.

## Immediate next action — BLOCKED ON ARM64 AUTHORIZATION

Current ARM64 authorization: **NONE**.

Implementation and Ubuntu static validation are complete.

Do not build, rebuild, rerun, dispatch the persistent Windows ARM workflow, or create a one-shot ARM workflow until fresh explicit authorization is given.

If authorization is later given:

1. verify current branch/HEAD and this handoff;
2. verify persistent workflow remains `workflow_dispatch` only;
3. update the persistent manual Stage K workflow only as needed to reconstruct the current work-target implementation;
4. dispatch exactly one Windows ARM64 attempt;
5. no automatic retry/rerun after failure;
6. if build succeeds, use Res1X runtime and collect strict 120-frame swap2/swap3 windows;
7. analyze normalized work pairs, ModuleSystem identity, resolved/other/overflow coverage, and visible lower-bound CPU tick growth;
8. keep EventModuleSubWorker separate from the shared ModuleSystem histogram.

Do not create Stage L and do not implement a behavior-changing optimization before this runtime attribution exists.

## New-tab startup instruction

On a fresh tab:

1. use GitHub documents as source of truth;
2. verify branch `exp/x1-waker-stage-k-grandparent-depth` and actual HEAD;
3. verify `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml` remains `Build dc95 X1 Waker Stage K` / `workflow_dispatch` only;
4. verify ARM64 authorization is **NONE**;
5. read `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`, `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`, `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`, and `NEXT_ACTION_WAKER_STAGE_K.md`;
6. treat five-grandparent semantic mapping and x26 work-target implementation as closed;
7. do not create Stage L;
8. without fresh ARM authorization, do not perform a Windows ARM build/run.
