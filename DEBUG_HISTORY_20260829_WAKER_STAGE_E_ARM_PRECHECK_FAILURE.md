# DEBUG HISTORY — Stage E ARM64 Pre-Configure Validation Failure

Date: 2026-08-29 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-waker-stage-e-recursive-arbiter`

## Authorized attempt

Fresh user approval authorized exactly one Stage E ARM64 attempt.

The one authorized run was:

- workflow: `Build dc95 X1 Waker Stage E`
- run: `33230457489`
- job: `99042246285`
- attempt: `1`
- event: `push`
- build HEAD: `0bab539c886a0c7b18be7ebe41476e81b7127a75`

No rerun or retry occurred.

Current ARM64 authorization after this run: **NONE**.

## What passed

Before the failure, the Windows ARM runner successfully completed:

- checkout of Adreno Lab
- checkout of Eden CI workflow
- checkout of exact Eden dc95
- exact dc95 HEAD verification
- retained non-scheduler patch application
- retained X1 diagnostic chain reconstruction
- focused Stage A through C reconstruction
- Stage D application
- Stage E application

The Stage E transplant itself printed success:

`Transplanted exact dc95 X1 waker Stage E recursive AddressArbiter attribution`

## Failure point

The run failed at:

`Verify Stage E before configure`

Therefore all later steps were skipped:

- MSYS2 CLANGARM64 setup
- CMake configure
- ARM64 C++ compile
- package
- analyzers/metadata packaging
- artifact upload

No Stage E ARM64 binary/artifact was produced by this attempt.

## Exact cause

The ARM workflow contained an incorrect static guard:

`grep -q 'TopSlotCount = 4' eden/src/core/x1_waker_stage_e_profiler.h`

The actual validated Stage E source intentionally defines separate constants:

- `TopWaitCount = 4`
- `TopSignalCount = 4`

There is no `TopSlotCount` symbol.

Thus the workflow exited with code 1 even though the Stage E source/transplant was valid. This is a workflow validation typo, not a C++ compile failure or runtime failure.

The earlier Ubuntu Stage E static run `33230000239` succeeded because it did not contain this incorrect `TopSlotCount` guard.

## Correction

The persistent ARM workflow was already restored to manual-only after the run was created.

The guard was then corrected, still manual-only, to verify:

- `TopWaitCount = 4`
- `TopSignalCount = 4`

Correction commit:

`ece657ebcfb19f8e15ce1a73874f9ab980b0919f`

No ARM64 run was triggered by this correction.

## Next action

A new Stage E ARM64 attempt requires a **fresh explicit user authorization**.

Do not treat the previous approval as reusable even though compilation never began; the approved workflow attempt was created and executed once.

On the next authorized attempt:

1. use the corrected manual-only Stage E workflow;
2. run exactly once;
3. do not retry on failure;
4. if successful, package `Eden-dc95-X1-waker-stage-e` and proceed to the controlled TOTK runtime test.
