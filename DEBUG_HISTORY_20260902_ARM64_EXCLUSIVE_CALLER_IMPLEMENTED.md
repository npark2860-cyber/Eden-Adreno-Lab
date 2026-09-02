# DEBUG HISTORY — ARM64 Exclusive Critical-Section Caller Attribution Implemented

Updated: 2026-09-02 KST

## Scope

This record documents the observation-only caller-attribution layer added after exact guest-PC runtime showed that the dominant selected-producer 32-bit LDXR traffic comes from Nintendo SDK internal critical sections.

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Experiment branch:
`exp/x1-arm64-exclusive-caller-attribution`

Immutable Eden baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current ARM64 authorization:
**NONE**

No Windows ARM64 build/run was performed in this implementation step.

## Exact prior runtime/static facts

Exact SDK build ID:
`B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Exact dominant SDK sites:

- `sdk+0x131754` = first `LDAXR` inside `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x13181c` = `LDAXR` inside `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`
- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

STXR runtime already rejected retry-storm contention as the principal explanation. The remaining question is which higher-level owners generate the increased SDK critical-section traffic.

## Exact caller-LR stack proof

Exact SDK disassembly proves:

1. `nn::os::LockMutex` saves x29/x30 with a `0x20`-byte frame, placing its external caller LR at `LockMutex-SP + 0x8`.
2. The path into `InternalCriticalSectionImplByHorizon::Enter()` preserves that LR through a tail branch.
3. `Enter()` subtracts `0x30` from SP before reaching its first `LDAXR` at `sdk+0x131754`.

Therefore, at the target `Enter()` LDAXR:

`guest Enter-SP + 0x38 = saved higher-level nn::os::LockMutex caller LR`

This is an exact property of the stated SDK build, not a generic ABI assumption.

## Dynarmic guest-SP transport

No new IR opcode and no x64 backend change were needed.

Exact dc95 ARM64 Dynarmic maintains guest SP in `A64JitState::sp`:

- `A64GetSP` loads from `offsetof(A64JitState, sp)`
- `A64SetSP` stores to the same state field

The existing exclusive-PC diagnostic path already passes the current location descriptor through the ARM64 callback trampoline. The caller layer additionally loads current guest SP from `Xstate` into callback argument X3 before the exclusive-read relocation.

The exclusive-read trampoline preserves X1/X2/X3 while replacing X0 with the UserConfig pointer and tail-branching to the callback function, so the diagnostic guest-SP argument reaches the callback without modifying guest-visible exclusive semantics.

## Runtime scope

New prefix:
`[X1-XEXCLCALL]`

The caller layer is intentionally narrower than the PC layer:

- existing Stage F selected producers only;
- 32-bit exclusive reads only;
- only the exact target `sdk+0x131754` Enter first-LDAXR site;
- independent `1/64` sampling;
- only after the target PC and sample gate pass, perform one guest stack read at `SP+0x38`;
- validate the stack address with `IsValidVirtualAddressRange` before `Read64`;
- bounded `256` caller slots / producer;
- bounded probe count `8`;
- top `12` caller LRs every `120` frames;
- invalid-stack and dropped-sample counters;
- existing exact `[X1-XEXCL]` totals preserved;
- existing `[X1-XEXCLPC]` 1/16 PC sampler preserved independently.

The runtime SDK range is registered dynamically from the loader and the target is represented durably as `sdk+0x131754`; no raw ASLR base is hardcoded.

## Added files

- `src/core/x1_arm64_exclusive_caller_profiler.h`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_caller_attribution.py`
- `tools/adreno_lab/analyze_x1_arm64_exclusive_caller_attribution.py`

The existing Stage K wrapper was minimally extended to chain:

`exclusive totals -> exclusive PC -> exclusive caller`

Persistent ARM workflow was not modified.

## Analyzer behavior

`analyze_x1_arm64_exclusive_caller_attribution.py` parses:

- `[X1-WAKERH]` module ranges
- `[X1-XEXCLCALL]` summaries and ranks

It requires explicit `--fast` and `--slow` report frames from the same runtime instead of carrying stale frame IDs from older runs.

Caller LRs are normalized to durable `module+offset` identities and compared per producer across fast/slow windows.

## Exact-dc95 Ubuntu static validation

Temporary Ubuntu validator was used only for static/transplant validation and was removed afterward.

Validator run history:

1. `33595304786` — fixture failure before caller transform: the synthetic Stage F header lacked the accessor normally added by Stage G.
2. `33595436819` — workflow YAML parse failure in the temporary fixture; no job ran.
3. `33595564876` — **SUCCESS**.

The successful validator confirmed on exact dc95:

- one generic `ReadAndMark<T>` remains;
- one vector `ReadAndMark<Vector>` remains;
- one generic `DoExclusiveOperation<T>` remains;
- one vector `DoExclusiveOperation<Vector>` remains;
- exactly one diagnostic `A64JitState::sp` load is added to exclusive-read emission;
- existing PC sampler remains present exactly once;
- caller target test remains exactly once;
- stack-range validation remains exactly once;
- SDK module-range registration remains exactly once;
- caller profiler constants remain `1/64`, `sdk+0x131754`, and stack offset `+0x38`;
- Python transplants/analyzer compile;
- no priority, affinity, reschedule, yield, sleep, QueueBuffer, swap-interval, or GPU behavior token was added.

The temporary validator workflow was deleted after success.

## Final implementation diff before docs

Compared with base docs/source HEAD `9e60061e6821ea0e4293dd04095c4707bcb1da24`, final implementation diff contains exactly four paths:

- `src/core/x1_arm64_exclusive_caller_profiler.h`
- `tools/adreno_lab/analyze_x1_arm64_exclusive_caller_attribution.py`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_caller_attribution.py`
- `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

No temporary workflow remains.
No persistent ARM workflow diff remains.
No baseline change occurred.

## Next runtime question

A future fresh single ARM authorization should answer only:

**Which higher-level `nn::os::LockMutex` caller LRs account for the dominant SDK Enter traffic, and how does their share change from swap=2 to swap=3?**

Primary owner buckets to test after exact static LR mapping:

- `gsys::SystemTask`
- EventModuleSubWorker
- `ActorAIGroupMgr::Job`
- other callers

Do not interpret the result as lock contention merely from call volume. Existing STXR failure evidence rejects a retry storm.
