# NEXT ACTION — Partition Dominant SDK Critical-Section Callers

Updated: 2026-09-02 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_READ_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_ATTRIBUTION_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`
- this file

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:
`exp/x1-arm64-exclusive-pc-attribution`

Immutable Eden baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent ARM workflow:
`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Persistent trigger:
`workflow_dispatch` only.

Current ARM64 authorization:
**NONE**

No Windows ARM64 build/rebuild/rerun without fresh explicit user authorization. One authorization means exactly one attempt. Failure does not authorize retry.

## Stage K semantic owners — CLOSED

- `main+0x96e2a8 -> main+0x26936d0` = **gsys::SystemTask internal work/phase dispatcher**
- `main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker**
- `main+0x244fc20 -> main+0x2ad6b20` = **ActorAIGroupMgr::Job**

Do not reopen owner mapping merely to add stack depth. Do not create Stage L.

## Exclusive total-cost questions — CLOSED

Prior runtime established:

- no STXR retry storm;
- no dramatic STXR per-call slowdown;
- LDXR `ReadAndMark` contributes about 47% of measured exclusive read+write time;
- combined selected-producer exclusive time increases about 1.32x in slow windows;
- the main amplification is operation-count growth, not single-operation latency growth;
- roughly 94-96% of measured exclusive time is 32-bit traffic.

Do not reopen total LDXR/STXR cost or retry-storm hypotheses without new evidence.

## Exact guest-PC runtime — CLOSED

Authorized build/run:

- run `33532663563`
- job `99939361617`
- attempt `1`
- head `cf592457de3b657549c3e11e8dd41d03a5a47965`
- result **SUCCESS**
- retry/rerun none

Artifact:

- `Eden-dc95-X1-waker-stage-k`
- ID `9811512280`
- size `31,447,663`
- SHA-256 `d36a856e8e9905e185bebfe0db8f2aeb2be6e78d76733cf332a0d8c7773b8505`

Runtime log:
`eden_log(20260902-043629).txt`

Actual cadence in that run:

- frames `480..1800`: `swap=2`
- frames `1920..2400`: `swap=3`

Do not copy cadence-frame IDs from older runs.

## Dominant SDK exclusive sites — EXACTLY CLOSED

Exact SDK build ID:
`B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Dominant sampled LDXR sites:

- `sdk+0x131754` = LDAXR inside **`nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`**
- `sdk+0x13181c` = LDAXR inside **`nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`**

Exact exported SDK entrypoints:

- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

Thus the largest shared 32-bit exclusive traffic is a real Nintendo SDK critical-section lock/unlock path.

This does **not** prove lock contention as root cause. STXR failures remain low.

## gsys::SystemTask exclusive growth — DIRECTLY CONNECTED

Two main-module LDXR sites rise sharply at the swap2 -> swap3 transition:

- `main+0x9715e0`
- `main+0x98245c`

Exact static ownership chain:

`gsys::SystemTask main+0x96e2a8`
` -> main+0x96e674`
` -> main+0x970160`
` -> child-work processing`

`main+0x9715e0` updates a child-work `+0x58` shared index/counter.

`main+0x98245c` updates a child-work `+0xb8` progress/index counter.

Both are therefore statically proven **SystemTask child-work atomic paths**.

At the same cadence transition, SystemTask Stage K work ticks also rise strongly.

The same subtree directly calls `nn::os::LockMutex/UnlockMutex` at multiple sites, so SystemTask definitely contributes to SDK critical-section traffic.

## Correct shared-dispatcher LockMutex addresses

Exact BL instruction addresses are:

- `main+0x86a52c` = LockMutex
- `main+0x86a5ec` = UnlockMutex
- `main+0x86a674` = LockMutex
- `main+0x86a7c0` = UnlockMutex

Older docs that named `main+0x86a530` / `main+0x86a678` as the BL sites are off by four bytes and are superseded.

The shared-dispatcher local LDXR sites remain comparatively flat across the cadence transition, so do not assign all added SDK critical-section traffic to that dispatcher.

## Other observed main sites

- `main+0x7d3648` = ActorAIGroupMgr::Job downstream atomic path.
- `main+0xddea3c` = secondary atomic site; exact semantic owner still unresolved.
- `main+0x22468ac` / `main+0x224697c` = generic/shared region; do not invent a unique owner.

## Current causal frontier

Current strongest evidence chain:

GPU command starvation
-> selected producer CPU growth
-> SystemTask/EventModuleSubWorker dominate relevant producer work
-> 32-bit exclusive-operation count rises in slow windows
-> Nintendo SDK InternalCriticalSection Enter/Leave is the dominant shared exclusive primitive
-> SystemTask child-work atomic/progress sites rise sharply with slow cadence
-> SystemTask subtree directly reaches SDK LockMutex/UnlockMutex
-> **remaining unknown: partition the dominant SDK critical-section traffic by higher-level caller/owner**.

## Immediate next action — OFFLINE DESIGN FIRST

Do not build ARM64 now.

Design and statically validate the narrowest possible caller-attribution layer for the dominant SDK `InternalCriticalSection::Enter` / `nn::os::LockMutex` traffic.

Requirements:

1. selected Stage F producers only;
2. no broad/all-thread profiling;
3. sample rather than log every operation;
4. preserve existing `[X1-XEXCL]` exact totals and `[X1-XEXCLPC]` output;
5. capture enough higher-level guest caller identity to normalize to `main+offset` / module+offset;
6. aggregate bounded top-N caller counts per 120-frame report;
7. no behavior change;
8. Ubuntu/exact-dc95 static validation before any ARM authorization is requested/used.

Primary question to answer with a future authorized runtime:

**What fraction of dominant SDK InternalCriticalSection/LockMutex traffic is attributable to gsys::SystemTask, EventModuleSubWorker, ActorAIGroupMgr::Job, and other callers?**

A promising exact-SDK stack-layout observation is that `nn::os::LockMutex` saves its external LR and `InternalCriticalSectionImplByHorizon::Enter` has a `0x30`-byte frame; at the hot `Enter` LDAXR the external caller LR appears recoverable from the guest stack at current Enter-SP + `0x38`. This must be fully validated before implementation and must not be assumed merely from the offset arithmetic.

## Stop condition

Without fresh ARM authorization, stop after offline caller-attribution implementation/static validation.

Do not auto-dispatch Windows ARM64.
Do not rerun a failed ARM attempt.
Do not create Stage L.
Do not implement a behavior-changing optimization until the dominant SDK lock traffic is partitioned by caller or new evidence makes that unnecessary.
