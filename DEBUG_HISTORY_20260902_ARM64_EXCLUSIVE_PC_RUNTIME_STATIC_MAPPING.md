# DEBUG HISTORY — ARM64 Exclusive Guest-PC Runtime + Static Mapping

Date: 2026-09-02 KST

## Scope

Observation/static-analysis only. No behavior change, no baseline change, no persistent-workflow change, and no ARM rerun after the single authorized attempt.

Repository: `npark2860-cyber/Eden-Adreno-Lab`

Branch: `exp/x1-arm64-exclusive-pc-attribution`

Immutable Eden baseline: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current ARM64 authorization after this run: **NONE**.

## Authorized ARM64 run

- workflow run: `33532663563`
- job: `99939361617`
- attempt: `1`
- event: `workflow_dispatch`
- workflow head: `cf592457de3b657549c3e11e8dd41d03a5a47965`
- result: **SUCCESS**
- retry/rerun: none
- one-shot dispatcher: removed immediately after dispatch

Artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9811512280`
- size: `31,447,663` bytes
- SHA-256: `d36a856e8e9905e185bebfe0db8f2aeb2be6e78d76733cf332a0d8c7773b8505`

## Runtime source

User runtime log: `eden_log(20260902-043629).txt`

Confirmed identity:

- Eden `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- Vulkan / Qualcomm Adreno X1-85
- main build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- sdk build ID `B9046C31EB5D31271BE970FE732D38DF49C6AA21`
- main runtime base `0x80e1f000`, size `0x472b000`
- sdk runtime base `0x85bf3000`, size `0xdd9000`

Actual cadence in this run:

- report frames `480..1800`: `swap=2`
- report frames `1920..2400`: `swap=3`

Do not reuse frame IDs from older runs.

## Dominant SDK 32-bit LDXR sites — EXACTLY IDENTIFIED

The two largest `[X1-XEXCLPC]` sites normalize to:

- `sdk+0x131754`
- `sdk+0x13181c`

Exact SDK NSO dynamic-symbol reconstruction proves:

- function at `sdk+0x131734`, size `0x98`:
  `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- function at `sdk+0x131804`, size `0x68`:
  `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`

Therefore:

- `sdk+0x131754` is the `LDAXR` loop inside `Enter()`
- `sdk+0x13181c` is the `LDAXR` loop inside `Leave()`

Exact SDK exported symbols also map:

- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

PLT/JMPREL/static disassembly closes the path:

`nn::os::LockMutex -> InternalCriticalSectionImplByHorizon::Enter -> sdk+0x131754`

`nn::os::UnlockMutex -> InternalCriticalSectionImplByHorizon::Leave -> sdk+0x13181c`

This is exact static proof, not a name inferred from proximity.

Representative sampled cadence growth:

- frame 1800 / swap2:
  - P0 `sdk+0x131754=2062`, `sdk+0x13181c=1906`
  - P1 `1939`, `2063`
- frame 1920 / swap3:
  - P0 `3586`, `3906`
  - P1 `5212`, `3480`
- frame 2160 / swap3:
  - P0 `7232`, `7184`
  - P1 `5576`, `5469`

Interpretation: synchronization-operation density rises strongly in slow windows. This does **not** prove lock contention as the root cause; prior STXR runtime showed low failure rates and no retry storm.

## gsys::SystemTask slow-emergent LDXR sites — EXACT OWNER CHAIN

Two main-module PCs become much hotter at the swap2 -> swap3 transition:

- `main+0x9715e0`
- `main+0x98245c`

Representative samples:

- frame 1800 / swap2:
  - `main+0x9715e0`: P0 `515`, P1 `353`
  - `main+0x98245c`: P0 `560`, P1 `370`
- frame 1920 / swap3:
  - `main+0x9715e0`: P0 `1994`, P1 `1825`
  - `main+0x98245c`: P0 `1948`, P1 `1784`

At the same cadence transition, already-resolved `gsys::SystemTask` Stage K work ticks jump:

- frame 1800 / swap2:
  - P0 `2,437,847`
  - P1 `2,550,047`
- frame 1920 / swap3:
  - P0 `4,371,820`
  - P1 `4,608,639`

Exact main NSO static call chain:

`gsys::SystemTask main+0x96e2a8`
` -> main+0x96e674: BL main+0x970160`

`main+0x970160` iterates internal child-work objects.

### Branch A

`main+0x970160`
` -> child + 0x42a0`
` -> main+0x970568: BL main+0x9713d0`
` -> main+0x9715e0`

Inside this function:

- `main+0x971428` derives child-work `+0x58`
- `main+0x9715e0` performs `LDXR` / increment / `STXR` retry on that 32-bit shared index/counter
- the index is used with the associated pointer-array area beginning at `+0x60`

### Branch B

`main+0x970160`
` -> child + 0x42a0`
` -> main+0x97065c: BL main+0x981248`
` -> main+0x98245c`

Inside this function:

- the saved pointer derives from child-work `+0xb8`
- `main+0x98245c` performs `LDXR` / increment / `STXR` on that 32-bit progress/index counter

Thus both slow-emergent main LDXR sites are **statically proven descendants of gsys::SystemTask child-work processing**.

## SystemTask subtree also reaches real SDK mutex primitives

Within the same `main+0x970160` subtree:

- `main+0x970e28: BL main+0x2b17270` = `nn::os::LockMutex`
- `main+0x970e5c: BL main+0x2b17280` = `nn::os::UnlockMutex`
- `main+0x970e9c: BL main+0x2b17270`
- `main+0x970ed0: BL main+0x2b17280`
- `main+0x9711a8: BL main+0x2b17270`
- `main+0x9711e8: BL main+0x2b17280`

Therefore SystemTask legitimately contributes to the dominant SDK `InternalCriticalSection Enter/Leave` traffic.

What is **not** yet proven: what fraction of all SDK `Enter/Leave` samples belongs to SystemTask versus EventModuleSubWorker or other callers. The PC sampler collapses all callers to the same SDK hot PC.

## Shared dependency dispatcher correction

Exact disassembly corrects the previously documented LockMutex BL addresses by -4:

- `main+0x86a52c: BL main+0x2b17270` = LockMutex
- `main+0x86a5ec: BL main+0x2b17280` = UnlockMutex
- `main+0x86a674: BL main+0x2b17270`
- `main+0x86a7c0: BL main+0x2b17280`

Older references to `main+0x86a530` / `main+0x86a678` as the BL instruction addresses are off by four bytes and are superseded.

Nearby local LDXR PCs:

- `main+0x86a510`
- `main+0x86a558`
- `main+0x86a65c`
- `main+0x86a698`

These remain relatively flat across the cadence transition, so the increase in SDK critical-section traffic must not be attributed entirely to the shared dependency dispatcher.

## Other hot-site ownership

- `main+0x7d3648` lies in `main+0x7d35b0` and is already connected from `ActorAIGroupMgr::Job`; it is an ActorAI downstream atomic-counter path.
- `main+0xddea3c` is in `main+0xdde8e0`, caller `main+0x7837f0`; exact semantic owner remains unresolved and secondary.
- `main+0x22468ac` / `main+0x224697c` are in a generic/shared function region with many reconstructed function-pointer references; do not assign a unique owner without stronger evidence.

## Current conclusion

The new evidence strengthens the following picture:

1. Slow cadence is accompanied by increased 32-bit exclusive-operation count, not an STXR retry storm.
2. The largest shared exclusive primitive is Nintendo SDK `InternalCriticalSectionImplByHorizon::Enter/Leave`.
3. `gsys::SystemTask` work time rises sharply at the same cadence transition.
4. Two main-module atomic sites that rise strongly with slowdown are directly and statically owned by the SystemTask child-work subtree.
5. That same SystemTask subtree directly calls `nn::os::LockMutex/UnlockMutex`.
6. Therefore SystemTask's slowdown is now connected to increased child-work distribution/progress synchronization, not merely to an opaque owner label.
7. This still does not prove that lock contention is the root cause or that all SDK critical-section traffic belongs to SystemTask.

## Next narrow frontier

If more runtime attribution is needed, the next useful diagnostic is **caller attribution for the dominant SDK `InternalCriticalSection::Enter` / `nn::os::LockMutex` traffic**, limited to the existing two selected producers.

Goal: partition SDK critical-section traffic among SystemTask, EventModuleSubWorker, ActorAIGroupMgr::Job, and other callers.

Do not broaden to all threads. Do not change behavior. Do not build ARM64 without a fresh explicit authorization.
