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

Runtime TIDs, guest addresses, promoted keys, module bases, PC/LR/caller addresses are observations only. Never hardcode them. Durable address knowledge must remain ASLR-normalized `module+offset`.

No broad/all-thread profiling. No behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

No optimization is justified yet.

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
- `NEXT_ACTION_WAKER_STAGE_K.md`

Do not reconstruct project state from chat guesses when these documents can be checked.

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

No push-triggered ARM build is enabled.

Current ARM64 authorization: **NONE**.

## Stage K Windows ARM64 build history

### First attempt — FAILED before scope fix

- run: `33254495504`
- job: `99105748612`
- attempt: `1`
- build/source HEAD: `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- C++ build: **FAILED**
- artifact: none
- retry/rerun: none

Root cause was the deterministic Stage K lexical-scope defect:

```diff
- auto& x1_stage_k_memory = x1_stage_j_memory;
+ auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
```

Fix commit:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

The earlier enum-name mismatch theory is rejected.

Scope-fix Ubuntu regression gate:

- run: `33279373418`
- job: `99171791300`
- validation HEAD: `3f0843208512d2878f8f02a8c7938216bf5ecf21`
- result: **SUCCESS**

Temporary validator cleanup:

`404a14af5a607762bd121dd98190d63c5c4466c0`

### Post-fix Windows ARM64 attempt — SUCCESS

A fresh explicit authorization was consumed for exactly one attempt.

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- exact dc95 checkout: success
- A-J reconstruction: success
- Stage K apply / verification: success
- configure/build/package/upload: **SUCCESS**
- retry/rerun/additional ARM attempt: none

One-shot dispatcher lifecycle:

- creation/dispatch commit: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- removal commit: `112541623742853bdb1c6114959f5bb5317cde89`

Canonical artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- size: `31,427,618` bytes
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`

The Stage K compile blocker is closed.

## Stage K runtime captures

### Res2X — abnormal rendering; not valid resolution-sensitivity evidence

Log:

`eden_log(20260830-025816).txt`

SHA-256:

`89784845234bd896149c61b9a856ab3b8b720b6588d6a9bb6a38b34a5755d2cf`

Environment included TOTK 1.2.1, Windows 11 25H2 build 26220.9223, Adreno X1-85 driver 512.863.0, Vulkan 1.3.295, Dynarmic, Res2X, FSR.

User observation:

- visible image showed approximately the upper-left quarter only.

Full-log unsupported depth scaling:

- D32_FLOAT: `12,091`
- D16_UNORM: `7,685`
- total: **19,776**

Do not use the earlier subjective “2x feels similar” observation as CPU-vs-GPU evidence. The intended 2x rendering path was not proven healthy.

### Res1X — primary Stage K runtime source

Log:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Facts:

- `Renderer.resolution_setup: Res1X`
- unsupported `BlitScaleHelper` depth-scaling errors: `0`
- no material Stage K frame-walk validity collapse
- late windows: `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- tiny sporadic `parentUnavailable` only

The chat contains no explicit textual statement that visible Res1X rendering returned to normal. Do not invent that visual observation.

## Strict cadence windows

Use only pure QueueBuffer cadence windows from the Res1X capture:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows `840` and `1200` are not primary evidence.

## Known SDK semantics through Stage J

Exact Stage I mappings remain authoritative:

- `sdk+0x158528` = return after `WaitForAddress`
- `sdk+0x158420` = return after `ArbitrateLock`
- `sdk+0x124a8c / +0x124b40` = `WaitLightEvent`
- `sdk+0x127058` = `ReceiveLightMessageQueue`
- `sdk+0x13178c` = `InternalCriticalSectionImplByHorizon::Enter`
- `sdk+0x127e54` = `LockMutex`

Stage J parents were:

- `main+0x86a820`
- `main+0x86be08`
- `main+0x2a904cc`
- `sdk+0x127e54`

## Stage K runtime grandparent families

Canonical normalized recurring families:

1. `sdk+0x158528 / sdk+0x124a8c / main+0x86a820 / main+0x86a490`
2. `sdk+0x158528 / sdk+0x124b40 / main+0x86be08 / main+0x86bc9c`
3. `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc / main+0x2a2d958`
4. `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54 / main+0x86a530`

Additional recurring LockMutex grandparent:

- `main+0x86a678`

The offline semantic mapping of these five offsets is now complete.

## Stage K offline semantic mapping — COMPLETE

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

Relevant imports:

- `main+0x2b17270` = `nn::os::LockMutex`
- `main+0x2b17280` = `nn::os::UnlockMutex`
- `main+0x2b17b50` = `nn::os::WaitLightEvent`
- `main+0x2b17c50` = `nn::os::SignalLightEvent`
- `main+0x2b183d0` = `nn::os::ReceiveLightMessageQueue`

## Shared dependency-worker result

`main+0x86a464` is a concrete virtual callback reached from common light-message loop `main+0x2a90478`.

For message value `1`, it enters `main+0x86a4ac` and later signals its light event.

The same worker implementation is reused by:

- `ModuleSystemWorker`
- `NavMeshDepWorker`
- `NavMeshCAStepDepWorker`
- `phive::DepWorker`

Therefore `main+0x86a464` is shared dependency-worker infrastructure, not a unique gameplay owner.

`main+0x86a4ac` is the synchronization-heavy dispatcher. Exact relevant sites include:

- `main+0x86a52c` -> `nn::os::LockMutex`
- `main+0x86a674` -> the same `nn::os::LockMutex`
- `main+0x86a81c` -> `nn::os::WaitLightEvent`
- `main+0x86a988` -> queued work-object virtual execution

Thus `main+0x86a490`, `main+0x86a530`, and `main+0x86a678` are three observations inside one shared dependency-worker scheduler/dispatcher path, not three independent owners.

## EventModuleSubWorker result

`main+0x86bc04` resolves through vtable/constructor/registration to:

**`EventModuleSubWorker`**

Exact semantic path:

`EventModuleSubWorker -> main+0x86bc04 -> main+0x86bd40 -> selected-object virtual operation -> nn::os::WaitLightEvent`

This is a concrete semantic owner for `main+0x86bc9c`.

## Generic message-loop result

`main+0x2a2d954` is exactly `BLR x8`.

The runtime path reaches common virtual method `main+0x2a90478`, which receives from a light-message queue and dispatches the concrete callback through the next virtual slot.

Therefore `main+0x2a2d958` is a generic indirect thread/message-dispatch frontier, not final game work.

## ModuleSystem work-target mapping — COMPLETE STATICALLY

Exact pointer flow:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

For ModuleSystem components:

- every `vtable+0x10` reached at `main+0x86a988` resolves to common shim `main+0x2af1230`;
- the shim performs gating and dispatches to component-specific `vtable+0x60`;
- `main+0x11d1b14` constructs a 41-slot component list;
- all 41 slots were mapped;
- there are 36 unique concrete `vtable+0x60` targets.

Mapped identities include:

`System`, `DenguModule`, `Resource`, `RSDB`, `Graphics`, `Ltk`, `Visualize`, `Controller`, `Rumble`, `Actor`, `Transceiver`, `Banc`, `Scene`, `AS`, `AI`, `Physics`, `ProgramHotReloadModule`, `Event`, `EventModuleWorker`, `EventModuleSubWorker`, `UI`, `Effect`, `Sound`, `XLink`, `Reaction`, `Terrain`, `ECppModule`, `SpyLog`, `GameData`, `Blackboard`, `LuaModule`, `Tool`, `Camera`, `REC`, `LOD`, `Bake`, `Rail`, and `PlayReport`.

Slots 17 and 37 deliberately return an empty name and execute `main+0x26a7fc0: RET`. Keep them as unnamed no-op components; do not invent identities.

The complete 41-slot table is in `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`.

The remaining runtime ambiguity is narrow: the existing Stage K record does not contain the resolved work-object/component identity at `main+0x86a988`, so it cannot determine which one of the statically enumerated component targets owns each expensive shared-worker slice.

## Strict Stage K slow/fast correlation after semantic mapping

- shared DepWorker callback `main+0x86a490`: P0 `2.130x`, P1 `2.164x`
- **EventModuleSubWorker** `main+0x86bc9c`: P0 `5.590x`, P1 `2.961x`
- generic ReceiveLightMessageQueue/message frontier `main+0x2a2d958`: P0 `1.232x`; P1 approximately `1.179x` from visible slow windows because frame 1560 is top-4 censored
- shared dispatcher LockMutex `main+0x86a530`: P1 `4.870x`; P0 slow/fast `>3.684x` because frame 960 is top-4 censored
- `main+0x86a678`: recurring slow LockMutex subfamily, exact aggregate unavailable because of top-4 censoring

The generic queue-entry family grows much less than the EventModuleSubWorker and shared-dispatch synchronization families.

## Current causal frontier

Measured chain is now:

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
-> shared branch reaches 41 statically-known ModuleSystem slots / 36 unique work targets.

Slow cadence still has both longer active guest CPU slices before blocker and longer kernel Arbitration.

The remaining shared-branch owner question is **which already-enumerated ModuleSystem work target is active in the expensive runtime slice**, not “what is the next stack frame?”

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

## Stage K decision

The requested offline grandparent semantic mapping is **complete**.

Do **not** create Stage L merely to add depth.

Do **not** implement a behavior-changing optimization from the current evidence.

The useful next attribution, if later explicitly approved for runtime, is a narrowly bounded identity measurement of the resolved ModuleSystem work target at:

`main+0x86a988 / main+0x2af1230 -> component vtable+0x60`

It must remain scoped to the already-selected producer/family, report normalized `main+offset` identities only, preserve strict swap2/swap3 comparability, and avoid arbitrary stack widening.

`EventModuleSubWorker` is already a concrete separate branch and should not be conflated with the shared ModuleSystem work-target ambiguity.

## Immediate next action — NO ARM ATTEMPT

Current ARM64 authorization: **NONE**.

Do not build, rebuild, rerun, dispatch the persistent workflow, or create a one-shot ARM workflow.

`NEXT_ACTION_WAKER_STAGE_K.md` now defines the next step as **design only** for the smallest work-target identity measurement. No implementation or runtime attempt is authorized by this handoff.

## New-tab startup instruction

On a fresh tab:

1. use GitHub documents as source of truth, not reconstructed chat context;
2. verify branch `exp/x1-waker-stage-k-grandparent-depth` and actual HEAD;
3. verify persistent workflow is still `Build dc95 X1 Waker Stage K` / `workflow_dispatch` only;
4. verify ARM64 authorization is **NONE**;
5. read `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md`, `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`, and `NEXT_ACTION_WAKER_STAGE_K.md`;
6. treat the five-offset offline grandparent mapping as closed;
7. do not create Stage L for stack depth;
8. if continuing without new authorization, only refine the bounded work-target identity measurement design; do not run ARM64.
