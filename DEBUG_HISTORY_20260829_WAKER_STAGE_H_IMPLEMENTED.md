# DEBUG HISTORY — 2026-08-29 Waker Stage H Implemented / Ubuntu Static

## Scope

Stage H normalizes the already-selected Stage G saved guest `PC/LR` contexts to ASLR-safe guest module-relative identities without widening the Stage G hot-path histogram or adding another thread profiler.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage H source branch:

`exp/x1-waker-stage-h-module-callpath-mapping`

Stage H base repository HEAD:

`59cbc61cafe8c1ae7360dc7e04e6f884c7a74512`

Current ARM64 authorization: **NONE**.

No ARM64 build/run was performed during Stage H implementation/static validation.

## Why this shape

Stage G runtime established that:

- aggregate Stage G `cpuTicks` reconcile almost exactly with Stage F CPU;
- a small repeated saved-PC family explains a majority of measured producer CPU growth;
- absolute guest PC/LR values are ASLR-dependent observations and must not be hardcoded;
- the fixed 64-context overflow is material but widening it would increase hot-path instrumentation cost.

Exact dc95 already has the required application module truth in `AppLoader_DeconstructedRomDirectory::Load()`:

- actual module `load_addr`
- actual `next_load_addr`
- module name
- existing `modules.insert_or_assign(load_addr, module)` map

Therefore Stage H does not invent a second module-discovery system.

## Implementation

### 1. Loader-side bounded module-range report

Added transplant:

`tools/adreno_lab/transplant_dc95_waker_stage_h_module_mapping.py`

Target:

`src/core/loader/deconstructed_rom_directory.cpp`

After each existing successful static NSO load and existing module-map insertion, Stage H emits exactly one bounded line per loaded module under the existing focused diagnostic setting:

`[X1-WAKERH] module=<name> base=<guest VA> end=<guest VA> size=<bytes>`

Gate:

`Settings::values.x1_address_arbiter_attribution_log.GetValue()`

Properties:

- uses the exact already-computed `load_addr` / `next_load_addr` values;
- preserves the existing `modules.insert_or_assign(load_addr, module)` behavior;
- no observed TID, promoted address, PC or LR is hardcoded;
- no scheduler hook is added;
- no per-switch logging is added;
- no priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence behavior is changed;
- Stage G `ContextSlotCount=64` is unchanged.

### 2. Offline module+offset join

Added analyzer:

`tools/adreno_lab/analyze_x1_waker_stage_h_module_mapping.py`

It parses:

- `[X1-WAKERH]` module ranges;
- `[X1-WAKERG]` top0..top3 raw saved PC/LR contexts.

For each Stage G reported context it keeps raw addresses for audit and emits canonical identities such as:

- `pc=main+0x... rawPc=0x...`
- `lr=sdk+0x... rawLr=0x...`

The analyzer validates module size/range consistency and rejects overlapping ranges.

Interpretation remains:

> Stage G / H identify scheduler CPU slices ending in a guest execution context. They do not claim the entire slice was spent executing the instruction at the saved PC.

## Ubuntu static validation — SUCCESS

Temporary workflow:

`Validate dc95 X1 Waker Stage H`

- run: `33246317401`
- job: `99084287770`
- attempt: `1`
- validation HEAD: `d39bfa3a814467f3b009202d626d4ee872db73f5`
- runner: `ubuntu-latest`
- conclusion: `success`

Passed:

- exact dc95 HEAD preservation before and after transplant;
- Stage H transplant application to exact dc95;
- `git diff --check`;
- Stage H transplant/analyzer `py_compile`;
- exactly one `[X1-WAKERH]` loader log site;
- existing module-map insertion count preserved;
- existing loader debug-log count preserved;
- scheduler file byte-for-byte unchanged by Stage H;
- no hardcoded observed producer TIDs or Stage G runtime PC/LR values;
- no Stage-H-added behavior mutation tokens;
- synthetic analyzer join resolved `0x1100 -> main+0x100` and `0x2200 -> sdk+0x200` while retaining raw addresses;
- final exact dc95 HEAD preservation.

The temporary Ubuntu workflow was deleted after success.

## Persistent ARM workflow state

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Prepared name:

`Build dc95 X1 Waker Stage H`

Trigger remains:

`workflow_dispatch` only.

It reconstructs the retained chain through Stage G, snapshots Stage H invariants, applies Stage H, verifies the loader/scheduler/Stage G invariants, and only then enters the existing Windows ARM64 configure/build/package path if manually dispatched.

Future artifact name:

`Eden-dc95-X1-waker-stage-h`

The package will include the Stage H analyzer.

No Stage H ARM64 attempt has occurred.

## Net repository scope check

Compared with Stage H base HEAD `59cbc61c...`, the implementation/static state changes only:

1. `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`
2. `tools/adreno_lab/transplant_dc95_waker_stage_h_module_mapping.py`
3. `tools/adreno_lab/analyze_x1_waker_stage_h_module_mapping.py`

plus this documentation and subsequent handoff documents.

No emulator source file is permanently edited in the lab repository; exact dc95 is modified only by the transplant during validation/build.

## Next action

A separate fresh explicit `ㄱㄱ` is required before exactly one Stage H ARM64 attempt.

One ARM authorization = exactly one ARM attempt. No retry/rerun after failure without another fresh authorization.
