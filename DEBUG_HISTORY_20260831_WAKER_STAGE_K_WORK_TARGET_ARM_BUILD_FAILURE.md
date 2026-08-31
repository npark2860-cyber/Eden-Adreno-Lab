# DEBUG HISTORY — Waker Stage K Work-Target ARM64 Build Failure

Updated: 2026-08-31 KST

## Scope

This record closes the first Windows ARM64 build attempt of the Stage K x26 work-target identity extension.

It records only the build result and the exact compiler failure. It does **not** claim any new runtime attribution because no runnable artifact was produced.

Fixed Eden baseline remains immutable:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Persistent workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger remains:

`workflow_dispatch` only.

## Authorized Windows ARM64 attempt — FAILED

A fresh explicit authorization was consumed for exactly one Windows ARM64 attempt.

- workflow run: `33351947642`
- job: `99366911164`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `5fa3b5fb59c5935eb9d48c4d6ea8f0faa52373c7`
- run result: **FAILURE**
- artifact: **none**
- retry/rerun: **none**

The temporary one-shot dispatcher that initiated this single attempt was removed afterward. Current branch HEAD at the time this failure was recorded was:

`b9252798651bbb64422d6893e7a04ebe1ad3b7d4`

Current ARM64 authorization after this failed attempt:

**NONE**

Failure does not authorize a retry or rerun.

## Steps that succeeded before compilation

The workflow successfully completed the reconstruction and pre-build gates, including:

- exact fixed dc95 baseline checkout and verification
- retained diagnostic/transplant chain through Stage K
- Stage G/H/J/K targeted verification
- `Verify Stage K targeted source before configure`
- MSYS2 CLANGARM64 setup
- ARM64 CMake configure

Therefore the failure occurred after the targeted Stage K source verifier and configure stage, during actual C++ compilation.

## Exact compiler failure

File:

`src/core/hle/kernel/k_scheduler.cpp`

Compiler policy:

`-Werror -Wshadow`

Two equivalent errors were emitted in the two selected-producer blocks.

First generated block:

```cpp
const u64 x1_stage_k_node = x1_stage_g_context.r[26];

auto x1_stage_k_read_work_targets = [&](
    u64 x1_stage_k_node,
    X1WakerStageKWorkResolveStatus& x1_stage_k_work_status,
    u64& x1_stage_k_shim_offset,
    u64& x1_stage_k_work_offset) {
    ...
};
```

Compiler location:

- prior outer declaration: approximately line `308`
- lambda parameter shadow: approximately line `309`

Second generated block has the same pattern:

- prior outer declaration: approximately line `559`
- lambda parameter shadow: approximately line `560`

Compiler diagnostic:

`declaration shadows a local variable [-Werror,-Wshadow]`

Build stopped after two errors; package, metadata, and artifact-upload steps were skipped.

## Root cause

The compatibility wrapper:

`tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

extracts the work-target resolver body and emits a local helper lambda named:

`x1_stage_k_read_work_targets`

The helper currently declares its first parameter as:

`u64 x1_stage_k_node`

The helper insertion point is after the generated producer block has already declared:

`const u64 x1_stage_k_node = x1_stage_g_context.r[26];`

Thus the generated helper parameter shadows the already-live outer local variable. This is rejected because warnings are treated as errors.

This is a **generated-source lexical naming defect**, not evidence that the x26 work-target identity model, guest-memory pointer chain, normalized work-pair design, or static semantic mapping is wrong.

## Minimal repair frontier

The next source edit should remain narrowly scoped to this shadowing defect.

Preferred minimal repair:

- rename the helper lambda parameter to a non-conflicting name such as `x1_stage_k_node_value`;
- update only references to that helper parameter inside the helper body;
- do not change resolver semantics, read count, producer scope, histogram layout, persistent workflow trigger, or fixed baseline.

An alternative is moving the helper before the outer `x1_stage_k_node` declaration, but renaming the lambda parameter is the smaller and clearer compatibility repair.

Before any future Windows ARM64 attempt, validate the generated `k_scheduler.cpp` through a non-ARM/static gate and explicitly check that no `-Wshadow` conflict remains.

## Authorization discipline for continuation

Current ARM64 authorization: **NONE**.

The failed run `33351947642` consumed the single authorization that launched it.

Do not:

- rerun run `33351947642`;
- rerun job `99366911164`;
- dispatch another Windows ARM64 build;
- create another one-shot ARM dispatcher;

without a **fresh explicit user authorization**.

One fresh authorization permits exactly one new ARM64 attempt and never an automatic retry.

## Runtime status

No new runnable Stage K x26 work-target artifact exists from this attempt.

Therefore no runtime values for the new fields have been observed yet, including:

- `workResolvedTicks`
- `workOtherResolvedTicks`
- `workOverflowTicks`
- resolver-status coverage
- normalized work-target pair top entries

The previous successful Stage K artifact/run remains valid historical evidence but predates the x26 work-target identity extension.

## Next-tab continuation

Use this record together with:

- `CURRENT_HANDOFF.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`

The first code action after resuming is the **minimal helper-parameter shadow fix**, followed by non-ARM validation. A new Windows ARM64 attempt remains blocked until fresh explicit authorization.

Do not create Stage L. Do not implement a behavior-changing optimization before runtime work-target attribution exists.
