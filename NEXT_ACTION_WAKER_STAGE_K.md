# NEXT ACTION — Waker Stage K Work-Target Build Repair / Runtime Gate

Updated: 2026-08-31 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_ARM_BUILD_FAILURE.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized. One authorization always means exactly one ARM attempt, with no implicit retry after failure.

## Existing canonical Stage K runtime

The previous successful Stage K build/runtime remains the only Windows ARM runtime evidence:

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- artifact: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- retry/rerun: none

That artifact predates the x26 work-target identity extension.

Primary previous runtime source:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Strict cadence windows remain:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows `840` and `1200` are not primary evidence.

## Offline semantic mapping — CLOSED

Durable classification:

- `main+0x86bc9c` = **EventModuleSubWorker** coordination/execution branch
- `main+0x86a490`, `main+0x86a530`, `main+0x86a678` = shared dependency-worker / ModuleSystem dispatcher branch
- `main+0x2a2d958` = generic indirect message/thread-dispatch frontier

Shared ModuleSystem execution chain:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Static enumeration is complete:

- 41 / 41 ModuleSystem slots mapped
- 36 unique concrete `vtable+0x60` targets
- unnamed slots 17 and 37 remain deliberately unnamed no-op components

Do not create Stage L for more stack depth.

## Work-target identity implementation — COMPLETE

Canonical implementation record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`

Runtime resolver design:

`x26 node -> [node] work object -> [work] vtable -> [vtable+0x10] shim -> [vtable+0x60] work target`

The extension remains bounded to the existing selected producers, reuses the existing Stage G guest-context capture, normalizes runtime addresses before histogram storage, and does not change scheduler behavior.

Compatibility layout currently in the branch:

- full resolver transplant implementation: `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth_impl.py`
- persistent-verifier compatibility wrapper: `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`
- dynamic Stage K main-range registration is emitted through the existing Stage H loader transplant

Relevant compatibility commits before the failed ARM attempt:

- `de634472054d78ad6b3b05dda73791d0dcb58953`
- `e8cf2597ca4028f31d59c49f234812125b3594e1`
- `e1026b6d8cde61f0f4e08e2dcb461b289876b381`

## Non-ARM validation before the latest ARM attempt

Historical Stage K validator restored from the previously successful verifier shape:

- commit: `6aed649e0c303866a141cebd59be314befc4cf13`
- run: `33351875686`
- job: `99366704957`
- attempt: `1`
- result: **SUCCESS**

Validator cleanup:

`5cf098df6b413d1c3ab8b95385bc4845eb6e6d1c`

These validation actions did not consume ARM authorization.

## Latest authorized Windows ARM64 attempt — FAILED

Canonical failure record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_ARM_BUILD_FAILURE.md`

Exactly one authorized ARM attempt was launched:

- persistent workflow run: `33351947642`
- job: `99366911164`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `5fa3b5fb59c5935eb9d48c4d6ea8f0faa52373c7`
- result: **FAILURE**
- artifact: **none**
- retry/rerun: **none**

The one-shot dispatcher was removed afterward at:

`b9252798651bbb64422d6893e7a04ebe1ad3b7d4`

The following steps succeeded before compilation failed:

- fixed baseline verification
- Stage G/H/J/K reconstruction and targeted verification
- Stage K targeted source verification
- MSYS2 CLANGARM64 setup
- ARM64 configure

Compilation then failed in generated:

`src/core/hle/kernel/k_scheduler.cpp`

with two `-Werror,-Wshadow` errors.

Exact conflict in both selected-producer blocks:

```cpp
const u64 x1_stage_k_node = x1_stage_g_context.r[26];

auto x1_stage_k_read_work_targets = &[
    /* conceptually */
];
```

The actual lambda signature declares another parameter named `x1_stage_k_node`, shadowing the outer local. The two reported generated locations were approximately lines `309` and `560`, with the outer declarations immediately preceding them.

This is a generated-source lexical naming defect. No runtime evidence was produced from this attempt.

## Current decision

The semantic work-target design remains valid and the runtime instrumentation remains the desired next evidence source.

However, the current source first needs one **minimal compatibility repair** before another ARM build can be considered.

**Do not create Stage L.**

**Do not implement an optimization yet.**

## Immediate next action — SOURCE FIX, THEN NON-ARM VALIDATION

Current ARM64 authorization: **NONE**.

On continuation, the first source edit should be limited to the compiler shadow defect in:

`tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

Preferred repair:

1. rename the helper lambda parameter `x1_stage_k_node` to a non-conflicting local name such as `x1_stage_k_node_value`;
2. update only references to that helper parameter inside the helper body;
3. leave the outer `const u64 x1_stage_k_node = x1_stage_g_context.r[26];` logic and resolver semantics unchanged;
4. do not change the fixed baseline;
5. do not change persistent ARM workflow triggers;
6. do not broaden selected-producer scope, memory-read count, context capture, histogram shape, or runtime behavior.

Then perform a **non-ARM/static validation** that reconstructs the generated Stage K source and explicitly confirms the `-Wshadow` conflict is gone.

Only after that validation is clean may the project be considered ready for another Windows ARM64 attempt.

## Fresh ARM authorization gate

Even after the source repair and non-ARM validation succeed, current ARM64 authorization remains:

**NONE**

Do not:

- rerun run `33351947642`;
- rerun job `99366911164`;
- dispatch the persistent Windows ARM workflow;
- create a new one-shot ARM dispatcher;

without fresh explicit user authorization.

One fresh authorization permits exactly one new Windows ARM64 attempt. Failure never permits an automatic retry.

## User-test gate after a future successful build

If a future explicitly authorized build succeeds and produces an artifact, that is the point where the user should test.

Use Res1X and collect enough 120-frame windows to cover pure swap2 and swap3 cadence. Analyze:

- normalized common-shim/work-target pairs
- ModuleSystem component identities
- `workResolvedTicks`
- `workOtherResolvedTicks`
- `workOverflowTicks`
- resolver-status coverage
- equal-window fast/slow visible lower-bound target ticks

A concrete component owner is acceptable only if coverage is sufficient. Unknown or non-common-shim targets remain evidence and must not be guessed.

`EventModuleSubWorker` remains a separate already-resolved branch and must not be folded into the shared ModuleSystem histogram.

No behavior-changing optimization is justified until this runtime owner attribution is available.
