# NEXT ACTION — Runtime Partition of Dominant SDK Lock Callers

Updated: 2026-09-02 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_BUILD_VERIFIER_FIX.md`
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

No Windows ARM64 build/rebuild/rerun without fresh explicit user authorization. One authorization means exactly one attempt. Failure does not authorize retry.

## Closed facts

### Stage K semantic owners

- `main+0x96e2a8 -> main+0x26936d0` = **gsys::SystemTask internal work/phase dispatcher**
- `main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker**
- `main+0x244fc20 -> main+0x2ad6b20` = **ActorAIGroupMgr::Job**

### Exclusive runtime facts

- no STXR retry storm;
- LDXR `ReadAndMark` is about 47% of measured exclusive read+write time;
- slow amplification is mainly operation-count growth;
- about 94-96% of measured exclusive time is 32-bit traffic.

Exact SDK build ID:
`B9046C31EB5D31271BE970FE732D38DF49C6AA21`

- `sdk+0x131754` = first LDAXR in `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x13181c` = LDAXR in `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`
- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

SystemTask child-work atomics `main+0x9715e0` and `main+0x98245c` rise sharply at the same swap2 -> swap3 transition as SystemTask work ticks. SystemTask also directly reaches SDK LockMutex/UnlockMutex.

Do not assign all SDK lock traffic to SystemTask until caller partition is observed.

## Caller attribution implementation

Runtime tag:
`[X1-XEXCLCALL]`

At exact SDK Enter hot PC `sdk+0x131754`:

`guest SP + 0x38 = saved higher-level nn::os::LockMutex caller LR`

Scope:

- two existing Stage F selected producers only;
- target only the exact Enter LDAXR;
- independent 1/64 sampling;
- one guarded `Read64(SP+0x38)` after target-PC + sample gates;
- bounded top-N caller aggregation;
- existing `[X1-XEXCL]` and `[X1-XEXCLPC]` unchanged;
- guest SP passed from ARM64 `A64JitState::sp`;
- no behavior change.

## First authorized caller ARM attempt — FAILED BEFORE BUILD

Authorized run:

- run `33602356948`
- job `100158688515`
- attempt `1`
- event `workflow_dispatch`
- head `7288400ffe1e378c4657fab473d4d86896d12ded`

Exactly one ARM run was created. The one-shot dispatcher was removed immediately. No retry/rerun occurred.

The run reached the Stage K transplant and successfully applied:

- Stage K;
- exclusive totals;
- exclusive PC attribution;
- exclusive caller attribution.

It then failed at `Verify Stage K before configure`.
Configure and C++ compilation did **not** start.

Failure cause:

The caller transform added the SDK range registration to `deconstructed_rom_directory.cpp` after the pre-Stage-K loader snapshot, violating the persistent verifier's byte-for-byte loader diff.

This was a verifier/snapshot ordering failure, not a caller-code compiler failure.

## Fix — CLOSED OFFLINE

The SDK range registration has been moved to Stage H.

Current ordering:

1. Stage H copies the caller profiler header.
2. Stage H pre-registers both `main` and `sdk` module ranges.
3. pre-Stage-K snapshot therefore already contains the final loader state.
4. caller transform no longer modifies the loader and only verifies the Stage H SDK registration is present.

Persistent ARM workflow remains unchanged.
Baseline remains unchanged.

Exact-dc95 Ubuntu validation after the fix:

- run `33602762070`
- result **SUCCESS**

Validated specifically:

- Stage H main + SDK registrations;
- loader snapshot after Stage H;
- exclusive totals + PC + caller transforms;
- final loader byte-for-byte identical to Stage H snapshot;
- `ReadAndMark` / `DoExclusiveOperation` semantics retained;
- guest-SP propagation retained;
- caller stack range-check retained;
- no behavior-changing scheduler/pacing/GPU tokens.

Temporary validator workflow was removed after success.

## Immediate next action

Current ARM64 authorization:
**NONE**

Stop here until the user gives a **fresh explicit authorization**.

If authorized:

1. perform exactly one Windows ARM64 attempt from `exp/x1-arm64-exclusive-caller-attribution`;
2. do not retry if it fails;
3. confirm Stage K verifier now passes with the Stage-H SDK registration;
4. if build succeeds, run TOTK 1.2.1 and collect `[X1-XEXCLCALL]`, `[X1-XEXCLPC]`, `[X1-XEXCL]`, Stage K, module and cadence records;
5. select swap=2 and swap=3 windows from that same runtime;
6. normalize top caller LRs to `module+offset`;
7. partition dominant SDK Enter traffic among SystemTask, EventModuleSubWorker, ActorAIGroupMgr::Job, and other callers.

Do not reuse the failed run as authorization for another ARM attempt.
Do not create Stage L.
Do not implement a behavior-changing optimization before caller partition is known.
