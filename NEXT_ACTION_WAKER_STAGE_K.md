# NEXT ACTION — Runtime Partition of Dominant SDK Lock Callers

Updated: 2026-09-02 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_IMPLEMENTED.md`
- this file

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:
`exp/x1-arm64-exclusive-caller-attribution`

Immutable Eden baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent Windows ARM64 workflow:
`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Persistent trigger:
`workflow_dispatch` only.

Current ARM64 authorization:
**NONE**

No Windows ARM64 build/rebuild/rerun without fresh explicit user authorization. One authorization means exactly one attempt; failure does not authorize retry.

## Closed facts

### Stage K semantic owners

- `main+0x96e2a8 -> main+0x26936d0` = **gsys::SystemTask internal work/phase dispatcher**
- `main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker**
- `main+0x244fc20 -> main+0x2ad6b20` = **ActorAIGroupMgr::Job**

### Exclusive total cost

- no STXR retry storm;
- LDXR `ReadAndMark` is roughly 47% of measured exclusive read+write time;
- slow amplification is mainly operation-count growth;
- roughly 94-96% of measured exclusive time is 32-bit traffic.

### Exact guest-PC ownership

Exact SDK build ID:
`B9046C31EB5D31271BE970FE732D38DF49C6AA21`

- `sdk+0x131754` = first LDAXR in `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x13181c` = LDAXR in `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`
- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

SystemTask child-work atomics `main+0x9715e0` and `main+0x98245c` rise sharply at the same swap2 -> swap3 transition as SystemTask work ticks. SystemTask also directly reaches SDK LockMutex/UnlockMutex.

Do not claim all SDK lock traffic belongs to SystemTask until caller partition is observed.

## Caller attribution — IMPLEMENTED / STATICALLY VALIDATED

New branch layer:
`[X1-XEXCLCALL]`

Exact stack proof for the stated SDK build:

At the first Enter LDAXR `sdk+0x131754`:

`guest SP + 0x38 = saved higher-level nn::os::LockMutex caller LR`

Implementation scope:

- existing two Stage F selected producers only;
- target only `sdk+0x131754`;
- independent `1/64` sampling;
- one guarded guest `Read64(SP+0x38)` only after target-PC + sample gates;
- bounded 256-slot caller table, probe limit 8, top 12;
- report every 120 frames;
- dynamic SDK module range, no raw ASLR base;
- existing `[X1-XEXCL]` totals unchanged;
- existing `[X1-XEXCLPC]` 1/16 PC samples unchanged;
- no IR/opcode/x64-backend modification;
- guest SP passed from exact ARM64 `A64JitState::sp`.

Successful exact-dc95 Ubuntu validator:

- run `33595564876`
- result: **SUCCESS**

The first two temporary validator attempts were fixture/YAML failures, not caller-transform failures. The temporary validator workflow has been removed.

Final implementation diff before documentation is exactly four paths:

- `src/core/x1_arm64_exclusive_caller_profiler.h`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_caller_attribution.py`
- `tools/adreno_lab/analyze_x1_arm64_exclusive_caller_attribution.py`
- minimal chain extension in `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

Persistent ARM workflow unchanged.
Baseline unchanged.

## Immediate next action

Current ARM64 authorization:
**NONE**

Stop until the user gives a fresh explicit authorization.

If authorized:

1. perform exactly one Windows ARM64 build/run attempt from `exp/x1-arm64-exclusive-caller-attribution`;
2. do not retry if it fails;
3. collect a runtime log containing `[X1-XEXCLCALL]`, `[X1-XEXCLPC]`, `[X1-XEXCL]`, `[X1-WAKERH]`, Stage K, and cadence records;
4. choose swap=2 / swap=3 report windows from that same run, not old frame IDs;
5. run `analyze_x1_arm64_exclusive_caller_attribution.py` with explicit `--fast` and `--slow` report frames;
6. normalize top caller LRs to durable `module+offset`;
7. disassemble/map dominant `main+offset` caller LRs with the exact TOTK 1.2.1 main NSO;
8. partition SDK `InternalCriticalSection::Enter` traffic among SystemTask, EventModuleSubWorker, ActorAIGroupMgr::Job, and other callers;
9. compare caller share/count changes across cadence.

## Decision after runtime

If one caller family explains most of the slow-added SDK Enter traffic, descend only into that owner and identify why it invokes more critical sections.

If traffic is broadly distributed across unrelated callers, treat the ARM64 Dynarmic callback/global-monitor cost as a shared amplification tax rather than inventing one game-side owner.

Do not implement a behavior-changing optimization before this partition is known.
Do not create Stage L.
