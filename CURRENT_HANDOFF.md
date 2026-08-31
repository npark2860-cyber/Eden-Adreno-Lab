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

Runtime TIDs, guest addresses, promoted keys, module bases, PC/LR/caller/target addresses are observations only. Never hardcode them. Durable address knowledge must remain ASLR-normalized `module+offset`.

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
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`
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

First Stage K Windows ARM64 attempt failed before the scope fix:

- run `33254495504`
- job `99105748612`
- attempt `1`
- build/source HEAD `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- artifact: none
- retry/rerun: none

Root cause was the deterministic lexical-scope defect:

```diff
- auto& x1_stage_k_memory = x1_stage_j_memory;
+ auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
```

Fix commit:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

Scope-fix Ubuntu regression gate succeeded:

- run `33279373418`
- job `99171791300`
- validation HEAD `3f0843208512d2878f8f02a8c7938216bf5ecf21`

Post-fix Windows ARM64 attempt succeeded under a fresh one-attempt authorization:

- workflow `Build dc95 X1 Waker Stage K`
- run `33287796384`
- job `99193953965`
- attempt `1`
- event `workflow_dispatch`
- build/source HEAD `25701cc1305a85c47debbbf42af1e646c8822e5b`
- exact dc95 checkout + reconstruction + build/package/upload: **SUCCESS**
- retry/rerun/additional ARM attempt: none

One-shot dispatcher:

- creation/dispatch commit `25701cc1305a85c47debbbf42af1e646c8822e5b`
- removal commit `112541623742853bdb1c6114959f5bb5317cde89`

Canonical artifact:

- `Eden-dc95-X1-waker-stage-k`
- artifact ID `9725325607`
- SHA-256 `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`

## Stage K runtime sources

### Res2X — invalid for resolution-sensitivity inference

Log:

`eden_log(20260830-025816).txt`

SHA-256:

`89784845234bd896149c61b9a856ab3b8b720b6588d6a9bb6a38b34a5755d2cf`

User observed approximately upper-left-quarter-only rendering.

Unsupported depth-scaling errors:

- D32_FLOAT `12,091`
- D16_UNORM `7,685`
- total **19,776**

Do not use the earlier subjective “2x feels similar” observation as CPU-vs-GPU evidence.

### Res1X — primary Stage K runtime source

Log:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Facts:

- `Renderer.resolution_setup: Res1X`
- unsupported scaling errors `0`
- late Stage K `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- tiny sporadic `parentUnavailable` only
- no material Stage K frame-walk validity collapse

The chat contains no explicit textual statement that visible Res1X rendering returned to normal. Do not invent that visual observation.

Strict primary cadence windows:

- fast / pure swap2: `960`, `1080`
- slow / pure swap3: `1320`, `1440`, `1560`, `1680`

Mixed `840`, `1200` are not primary evidence.

## Exact SDK semantics through Stage J

- `sdk+0x158528` = return after `WaitForAddress`
- `sdk+0x158420` = return after `ArbitrateLock`
- `sdk+0x124a8c / +0x124b40` = `WaitLightEvent`
- `sdk+0x127058` = `ReceiveLightMessageQueue`
- `sdk+0x13178c` = `InternalCriticalSectionImplByHorizon::Enter`
- `sdk+0x127e54` = `LockMutex`

## Stage K offline semantic mapping — COMPLETE

Canonical record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`

Record commit:

`ade4a399c69de100a9e249c3def1841f90069359`

Exact dumped TOTK 1.2.1 main image:

`main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`

Exact five-grandparent mapping:

| Captured grandparent | Exact LR-producing instruction | Durable classification |
|---|---|---|
| `main+0x86a490` | `main+0x86a48c: BL main+0x86a4ac` | shared dependency-worker callback into dispatcher |
| `main+0x86bc9c` | `main+0x86bc98: BL main+0x86bd40` | **EventModuleSubWorker** coordination/execution branch |
| `main+0x2a2d958` | `main+0x2a2d954: BLR x8` | generic indirect message/thread-dispatch frontier |
| `main+0x86a530` | `main+0x86a52c: BL main+0x2b17270` | shared dispatcher LockMutex site A |
| `main+0x86a678` | `main+0x86a674: BL main+0x2b17270` | shared dispatcher LockMutex site B |

`main+0x86a490`, `main+0x86a530`, and `main+0x86a678` converge on shared dependency-worker infrastructure reused by:

- `ModuleSystemWorker`
- `NavMeshDepWorker`
- `NavMeshCAStepDepWorker`
- `phive::DepWorker`

`main+0x86bc9c` has a concrete semantic owner: **EventModuleSubWorker**.

`main+0x2a2d958` is generic and is not a final owner.

## ModuleSystem work-target map — COMPLETE STATICALLY

Exact path:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Static result:

- 41/41 ModuleSystem component slots mapped
- 36 unique concrete `vtable+0x60` targets
- component identities include `System`, `DenguModule`, `Resource`, `RSDB`, `Graphics`, `Actor`, `Physics`, `Event`, `EventModuleWorker`, `EventModuleSubWorker`, `UI`, `Sound`, `GameData`, `Blackboard`, `Camera`, `LOD`, `Rail`, `PlayReport`, and the complete table in the semantic-mapping record
- slots 17 and 37 intentionally return empty names and execute `main+0x26a7fc0: RET`; keep them unnamed no-op components

Existing Stage K runtime data does not identify which of these component targets is active in each expensive shared-worker slice.

## Strict Stage K slow/fast semantic correlation

- shared DepWorker `main+0x86a490`: P0 `2.130x`, P1 `2.164x`
- **EventModuleSubWorker** `main+0x86bc9c`: P0 `5.590x`, P1 `2.961x`
- generic message frontier `main+0x2a2d958`: P0 `1.232x`; P1 approximately `1.179x` from visible slow windows
- shared LockMutex `main+0x86a530`: P1 `4.870x`; P0 slow/fast `>3.684x` because fast frame 960 is top-4 censored
- `main+0x86a678`: recurring slow LockMutex subfamily; no exact strict aggregate due top-4 censoring

Generic queue-entry growth is much smaller than EventModuleSubWorker and shared-dispatch synchronization growth.

## Work-target identity design — COMPLETE

Canonical record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`

Design commit:

`f9a4e1cebea3b4d180dbc186b2afd7e4303a777c`

The remaining shared-worker identity can be measured without another stack frame.

Exact dispatcher anchor:

```text
main+0x86a97c: LDR x0, [x26]
main+0x86a980: LDR x8, [x0]
main+0x86a984: LDR x8, [x8, #0x10]
main+0x86a988: BLR x8
```

Exact dc95 guest `ThreadContext` already stores registers `r[0..28]`. The existing Stage G context sample therefore exposes saved `x26` as `x1_stage_g_context.r[26]`; no second context capture is needed.

Preferred Stage K resolver:

`x26 node -> work object -> vtable -> vtable+0x10 shim -> vtable+0x60 work target`

Design constraints:

- exactly four added selected-producer `Read64` sites
- validate each pointer/read range and arithmetic
- no new stack walking
- dynamically register the `main` module range from the existing Stage H loader path
- normalize shim/work targets immediately to `main+offset`
- runtime must not hardcode `main+0x2af1230` or any of the 36 component offsets
- fixed 64 normalized `(shim_offset, work_offset)` slots per producer
- 120-frame report cadence
- top 4 pairs plus `resolvedTicks`, `otherResolvedTicks`, `overflowTicks`, resolver status accounting
- offline analyzer identifies normalized common shim `main+0x2af1230` and maps work offsets to the static 41-slot table

This is an extension of Stage K, **not Stage L**.

## Current causal frontier

Measured chain:

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two selected producer threads
-> producer CPU growth + Arbitration growth
-> exact SDK blocker semantics
-> Stage J parent
-> Stage K grandparent
-> offline semantic mapping
-> **EventModuleSubWorker concrete branch + shared dependency-worker / ModuleSystem branch**
-> 41 statically mapped ModuleSystem slots / 36 work targets
-> **remaining question: which normalized work target owns the expensive shared-worker slice at runtime?**

The measurement needed to answer that question is now designed.

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
- host scheduler starvation is closed as primary owner.

## Immediate next action — IMPLEMENTATION / STATIC VALIDATION ONLY

Current ARM64 authorization: **NONE**.

Do not build, rebuild, rerun, dispatch the persistent workflow, or create a one-shot ARM workflow.

`NEXT_ACTION_WAKER_STAGE_K.md` defines the next action as implementation of the already-designed x26 work-target resolver inside Stage K, followed only by static/Ubuntu validation.

Implementation may alter the Stage K observation code and analyzer only within the exact design constraints above. It must not add Stage L, broaden thread scope, add arbitrary stack depth, or change emulation behavior.

A later Windows ARM64 attempt still requires fresh explicit authorization. One authorization = exactly one attempt; failure does not authorize retry.

`EventModuleSubWorker` remains a separate already-resolved branch and must not be conflated with the shared ModuleSystem target histogram.

## New-tab startup instruction

On a fresh tab:

1. use GitHub documents as source of truth;
2. verify branch `exp/x1-waker-stage-k-grandparent-depth` and actual HEAD;
3. verify persistent workflow remains `Build dc95 X1 Waker Stage K` / `workflow_dispatch` only;
4. verify ARM64 authorization is **NONE**;
5. read `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`, `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`, and `NEXT_ACTION_WAKER_STAGE_K.md`;
6. treat five-grandparent semantic mapping and the x26 measurement design as closed;
7. do not create Stage L;
8. if continuing without new ARM authorization, perform only the Stage K x26 work-target resolver implementation/static validation; do not run ARM64.
