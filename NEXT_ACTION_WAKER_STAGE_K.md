# NEXT ACTION — Waker Stage K Work-Target ARM Build Gate

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
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_SHADOW_FIX.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized. One authorization always means exactly one ARM attempt, with no implicit retry after failure.

## Existing canonical Stage K runtime

The previous successful Stage K build/runtime remains the only Windows ARM runtime evidence and predates the x26 work-target identity extension.

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- artifact: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`

Primary previous runtime source:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Strict cadence windows remain:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows `840` and `1200` are not primary evidence.

## Closed semantic mapping

Durable Stage K classification:

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

## Work-target identity implementation

Runtime resolver:

`x26 node -> [node] work object -> [work] vtable -> [vtable+0x10] shim -> [vtable+0x60] work target`

The extension remains bounded to the existing selected producers, reuses the existing Stage G guest-context capture, normalizes runtime addresses before histogram storage, and does not change scheduler behavior.

Compatibility layout:

- full resolver implementation: `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth_impl.py`
- persistent-verifier compatibility wrapper: `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

## Previous ARM failure — CLOSED AS A STATIC SOURCE DEFECT

The first authorized ARM attempt of the x26 extension failed:

- run: `33351947642`
- job: `99366911164`
- attempt: `1`
- build/source HEAD: `5fa3b5fb59c5935eb9d48c4d6ea8f0faa52373c7`
- result: **FAILURE**
- artifact: none
- retry/rerun: none

Failure category:

`-Werror,-Wshadow`

The compatibility helper used parameter name `x1_stage_k_node`, shadowing an already-live outer local of the same name.

## Minimal shadow repair — COMPLETE

Repair commit:

`b22306fa55690e99aac94f521d302caa27893754`

Only the helper parameter was renamed to `x1_stage_k_node_value`, and only its three helper-body references were updated.

Unchanged:

- saved-x26 source
- resolver pointer chain
- selected-producer scope
- context capture count
- read/range-check counts
- histogram shape
- runtime behavior
- baseline
- persistent ARM workflow trigger

## Non-ARM/static regression validation — SUCCESS

Temporary Ubuntu validator:

- workflow: `Validate dc95 X1 Waker Stage K`
- run: `33392096685`
- job: `99487889955`
- head SHA: `72e32bbbfd4454f2fdbd9465fb5bf1b0be5ba557`
- attempt: `1`
- runner: `ubuntu-latest`
- result: **SUCCESS**

The validator reconstructed exact dc95 through Stage K and explicitly confirmed the generated source no longer contains the conflicting helper parameter spelling.

Temporary validator cleanup:

`75c9671aa0c5387e3a9b56fc18d4c216980bfdbe`

No persistent automatic Ubuntu validator remains.

Canonical repair record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_SHADOW_FIX.md`

## Immediate next action — ARM AUTHORIZATION GATE

Current ARM64 authorization:

**NONE**

The source repair and required non-ARM/static validation are complete. Stop here unless the user gives a fresh explicit Windows ARM64 build authorization.

Do not:

- rerun run `33351947642`;
- rerun job `99366911164`;
- dispatch the persistent Windows ARM workflow;
- create a one-shot ARM dispatcher;

without fresh explicit authorization.

One fresh authorization permits exactly one new Windows ARM64 attempt. Failure never permits an automatic retry.

Before any future authorized attempt, verify:

1. branch is still `exp/x1-waker-stage-k-grandparent-depth`;
2. fixed baseline is still `dc95cd09eea9749250fe31a3072684d341d19417`;
3. `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml` is still named `Build dc95 X1 Waker Stage K`;
4. its trigger is still `workflow_dispatch` only;
5. the build includes the repaired wrapper commit `b22306fa55690e99aac94f521d302caa27893754` or a descendant containing exactly that repair.

## User-test gate after a future successful build

If a future explicitly authorized build succeeds and produces an artifact, use Res1X and collect enough 120-frame windows to cover pure swap2 and swap3 cadence.

Analyze:

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
