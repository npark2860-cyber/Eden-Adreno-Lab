# DEBUG HISTORY — ARM64 Exclusive Caller Build Verifier Failure + Fix

Updated: 2026-09-02 KST

## Scope

This record covers the first authorized Windows ARM64 attempt for the sampled higher-level LockMutex caller attribution experiment and the offline fix performed after that attempt failed before configure/build.

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Experiment branch:
`exp/x1-arm64-exclusive-caller-attribution`

Immutable Eden baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

## Authorized Windows ARM64 attempt

User authorization was consumed exactly once.

Persistent workflow run:
- run: `33602356948`
- job: `100158688515`
- attempt: `1`
- event: `workflow_dispatch`
- build head: `7288400ffe1e378c4657fab473d4d86896d12ded`

The temporary one-shot dispatcher was deleted immediately after exactly one persistent ARM run appeared.

No rerun or retry was performed.

Current Windows ARM64 authorization after this attempt: **NONE**.

## What succeeded

Before failure, the workflow successfully completed:

- exact dc95 checkout verification;
- retained X1 diagnostic reconstruction;
- Stage D;
- Stage E;
- Stage F;
- Stage G + verifier;
- Stage H + verifier;
- Stage J + verifier;
- Stage K transplant;
- chained ARM64 exclusive totals attribution;
- chained exact LDXR PC attribution;
- chained exclusive critical-section caller attribution.

Runtime code was therefore transplanted successfully into the exact dc95 tree before the persistent Stage K verifier ran.

## Failure

The run failed at:
`Verify Stage K before configure`

Configure and C++ build never started.

The failing invariant was the retained Stage K loader snapshot comparison:

`diff -u .x1-stage-k-precheck/loader-pre-k.cpp eden/src/core/loader/deconstructed_rom_directory.cpp`

The caller transform had added after the pre-Stage-K snapshot:

- `#include "core/x1_arm64_exclusive_caller_profiler.h"`
- SDK module registration through `RegisterSdkModuleRange(...)`

This was an observation-only loader change, but it violated the persistent Stage K verifier requirement that the loader be byte-for-byte unchanged by Stage K.

This was **not** a compiler failure and **not** evidence that the caller sampling logic is invalid.

## Offline fix

The SDK range registration was moved earlier to the Stage H module-mapping pass.

Current design:

1. Stage H copies `x1_arm64_exclusive_caller_profiler.h` into the exact dc95 tree.
2. Stage H registers:
   - `main` range for Stage K;
   - `sdk` range for exclusive caller attribution.
3. The pre-Stage-K snapshot therefore already contains the final observation-only loader state.
4. The caller transform no longer modifies the loader. It only asserts that the Stage H SDK registration survived Stage K reconstruction.

No persistent ARM workflow file was modified.
No baseline source behavior was modified.

Net source-script changes after removing transient workflows:

- `tools/adreno_lab/transplant_dc95_waker_stage_h_module_mapping.py`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_caller_attribution.py`

## Exact-dc95 Ubuntu validation

Temporary validator run:
`33602762070`

Result:
**SUCCESS**

Validated:

- exact dc95 baseline checkout;
- Stage H pre-registration of both main and SDK ranges;
- loader snapshot saved immediately after Stage H;
- exclusive totals transform;
- exclusive PC transform;
- exclusive caller transform;
- final loader is byte-for-byte identical to the Stage H snapshot;
- `ReadAndMark<T>` semantics retained;
- `DoExclusiveOperation<T>` semantics retained;
- guest SP propagation retained;
- sampled caller stack range check retained;
- exactly one SDK range registration retained;
- no behavior-changing scheduler/pacing/GPU tokens introduced.

The temporary validator workflow was deleted after success.

## Current state

Caller-attribution implementation is again statically ready for a future single ARM runtime attempt.

Do **not** rerun automatically.
Do **not** treat the failed verifier run as authorization for another ARM attempt.
A fresh explicit user authorization is required before any Windows ARM64 build/rebuild/rerun.

Primary future runtime output remains:
`[X1-XEXCLCALL]`

Primary question remains:
What fraction of dominant SDK InternalCriticalSection / LockMutex traffic comes from SystemTask, EventModuleSubWorker, ActorAIGroupMgr::Job, and other higher-level callers?
