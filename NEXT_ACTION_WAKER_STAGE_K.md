# NEXT ACTION — Dynarmic Exclusive Path Parked / NCE Baseline

Updated: 2026-09-02 KST

## Source of truth

Read first:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_RUNTIME_FINAL.md`
3. `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Branch:
`exp/x1-arm64-exclusive-caller-attribution`

Immutable baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent ARM workflow:
`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Trigger:
`workflow_dispatch` only.

Current Windows ARM64 authorization:
**NONE**

## Current decision

The Dynarmic exclusive-attribution track is **documented and parked**.

Do not schedule another ARM build merely to finish semantic names for the remaining caller offsets.

The final caller-attribution runtime has already succeeded and established the useful performance result:

- slow cadence drives selected-producer exclusive operation count to roughly `3.5-3.7x` stable swap2 levels;
- per-callback latency rises only modestly;
- STXR failure remains low enough to reject a retry storm as primary cause;
- dominant shared primitive is Nintendo SDK `InternalCriticalSectionImplByHorizon::Enter/Leave` / `nn::os::LockMutex`;
- `gsys::SystemTask` child-work synchronization is directly proven to participate;
- other slow-emergent LockMutex caller families remain, but caller-table saturation means the current top-N data is not an exhaustive traffic partition.

## Active performance direction

A separate **Windows ARM64 NCE** effort is already being developed outside this branch/tab.

Use this repository's final Dynarmic results as the comparison baseline for NCE.

High-value NCE A/B questions:

1. Does the same TOTK scene remain in the same slow cadence state under NCE?
2. Does removing/bypassing Dynarmic ARM64 exclusive callback handling recover meaningful CPU time/FPS?
3. Does the guest still exhibit the same synchronization-volume growth even when the Dynarmic callback tax is absent?
4. If NCE improves cadence materially, which part of the previous Dynarmic cost disappears?

## If Dynarmic work is resumed later

Resume only for a concrete reason:

- a ready 32-bit ARM64 exclusive fast-path/common-case prototype;
- NCE A/B needs a precise Dynarmic comparison;
- one specific unresolved caller family becomes necessary.

Remaining secondary caller offsets include:

- `main+0x7efd30`
- `main+0x7ef838`
- `main+0x7f028c`
- `main+0x7f07f0`
- `main+0x7f00a8`
- `main+0xa81e20`
- `main+0xa5a360`
- `main+0x9be4b4`
- `main+0x9be380`

Do not reopen broad/all-thread profiling.
Do not create Stage L merely for stack depth.
Do not change scheduler/priority/affinity/yield/wait/signal/GPU/QueueBuffer/cadence behavior as part of attribution.
Do not build Windows ARM64 without fresh explicit authorization.
