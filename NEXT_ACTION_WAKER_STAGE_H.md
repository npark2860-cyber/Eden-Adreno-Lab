# NEXT ACTION — Waker Stage H Guest Module / Call-Path Mapping

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_ARM_PRECHECK_FAILURE.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-g-producer-cpu-attribution`

Never change the exact Eden baseline without explicit approval.

## Stage G runtime result now fixed

Successful Stage G ARM64 build:

- run `33244399213`
- job `99079231424`
- attempt `1`
- build HEAD `573ba79f2a0a0ba534993d314e113d2f9fb7d1c5`
- artifact `Eden-dc95-X1-waker-stage-g`
- artifact id `9712697731`
- size `31,416,415` bytes
- SHA-256 `38ccf37cc28cb5123b5c4018117b4f53a651bc0e77488955dddaf9093c98a7a1`
- conclusion `success`
- retry/rerun none

Runtime:

`eden_log(20260829-093642).txt`

Clean stable windows:

- pure swap2: `480, 600, 720, 840`
- transition excluded: `960` = 44 swap2 / 76 swap3
- pure swap3: `1080, 1200, 1320`

Stage G `cpuTicks/interval` reconciles almost exactly with Stage F `cpuAvg`:

- producer 0: `0.92233 -> 4.09551 ms` vs Stage F `0.92206 -> 4.09553 ms`
- producer 1: `1.08955 -> 4.67808 ms` vs Stage F `1.08929 -> 4.67864 ms`

All material Stage G sanity counters are zero in armed stable windows.

Recurring observed saved PCs:

- `0x85f12528`
- `0x85f12420`

Recurring dominant observed LR values include:

- `0x85edea8c`
- `0x85edeb40`
- `0x85eeb78c`
- `0x85ee1058`

These are runtime observations only. **Do not hardcode them.**

The four reported exact PC/LR contexts explain about `61% / 54%` of producer 0 / producer 1 CPU growth, while the fixed 64-context overflow explains another about `36% / 44%` of growth.

The same main saved PC/LR family also appears in the separate Stage D dynamic-waker reports. Therefore the endpoint may be a shared guest runtime/synchronization path rather than a producer-specific work function.

## Why Stage H is next

Stage G decision-map case C is rejected because CPU accounting reconciles.

The CPU growth is not uniformly diffuse: a small saved-PC family is repeatedly dominant. But the absolute PCs are ASLR-dependent and cannot be interpreted as stable identities across launches.

Before any optimization or wider profiler, normalize the observed contexts to guest module-relative paths.

## Exact dc95 source path already available

Exact dc95 application loading already tracks NSO module bases:

`src/core/loader/deconstructed_rom_directory.cpp`

`AppLoader_DeconstructedRomDirectory::Load()`:

- static module order: `rtld`, `main`, `subsdk0..9`, `sdk`
- each actual load has `load_addr`
- after load it stores `modules.insert_or_assign(load_addr, module)`

`AppLoader_DeconstructedRomDirectory::ReadNSOModules()` exposes the base->name map.

`src/core/loader/nca.cpp`

`AppLoader_NCA::ReadNSOModules()` forwards to that loader map.

This existing map is the preferred ASLR source of truth. Do not invent a second module discovery system.

## Stage H design constraints

Goal:

> normalize only Stage G selected-producer saved PC/LR contexts to `module+offset`, so the repeated CPU-slice endpoint family can be mapped to the exact guest runtime/work path.

Must preserve:

- exact dc95 baseline
- Stage F dynamic producer identities
- no hardcoded observed TIDs
- no hardcoded observed promoted address
- no hardcoded observed PC/LR values
- no all-thread PC profiler
- no per-switch logging
- no priority/affinity/yield/reschedule mutation
- no waits/signals/GPU/QueueBuffer/cadence behavior change
- Stage F and Stage G reporting behavior except for the smallest necessary Stage H mapping data

Preferred implementation shape:

1. reuse existing loader NSO module map once per application load or focused profiler initialization;
2. expose immutable module base/name data to the focused diagnostic path;
3. resolve only already-selected Stage G contexts;
4. report module name/index + offset for top contexts, or emit one small one-time module-range report that the analyzer can join to Stage G raw PC/LR;
5. keep runtime output bounded and fixed;
6. keep absolute raw PC/LR available for audit but make module-relative identity canonical for cross-run comparison.

Do not increase `ContextSlotCount=64` yet. The overflow is material but widening the hot-path lookup would increase instrumentation cost. First map the dominant repeated family using existing data.

## Interpretation guard

Stage G attaches a completed scheduler slice's exact CPU ticks to the saved guest PC/LR at switch-out.

Therefore Stage H should call this a **slice-end execution context / call path**, not "time spent executing this PC".

If the mapped PC is a common SVC/runtime synchronization endpoint, use LR/module offsets to identify callers before following deeper guest work.

## Implementation authorization semantics

Current ARM64 authorization: **NONE**.

A fresh `ㄱㄱ` while this file is the current next action means:

> implement Stage H guest module/call-path mapping and run Ubuntu/static validation only.

That `ㄱㄱ` does **not** authorize an ARM64 build.

After Stage H implementation/static validation is reported, a separate fresh `ㄱㄱ` is required for exactly one ARM64 attempt.

One ARM authorization = exactly one ARM attempt. Failure does not authorize retry or rerun.

## Stage H runtime decision map

A. Dominant contexts normalize to one shared runtime/synchronization module and a small caller set:

> follow those caller offsets/source semantics; keep producer CPU and producer Arbitration branches separate until direct evidence joins them.

B. Dominant contexts normalize to producer-specific game module work paths:

> map the exact module offsets to guest work semantics before considering optimization.

C. Module mapping reveals that current top contexts are only generic scheduler/SVC endpoints and LR is insufficient:

> add the smallest selected-producer-only caller-depth evidence needed; do not broaden to all threads.

D. Existing 64-slot overflow hides the dominant normalized family even after module mapping:

> then and only then redesign the fixed histogram representation or slot budget.

No optimization is justified yet.