# NEXT ACTION — Waker Stage K Work-Target Runtime Gate

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

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized. One authorization always means exactly one ARM attempt, with no implicit retry after failure.

## Existing canonical Stage K Windows ARM64 runtime

The previous Stage K build/runtime remains the only Windows ARM runtime evidence:

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- artifact: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- retry/rerun: none

Primary previous runtime source:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Strict cadence windows remain:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows `840` and `1200` are not primary evidence.

The Res2X capture remains invalid for resolution-sensitivity inference because of abnormal quarter-screen rendering and 19,776 unsupported depth-scaling errors.

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

The Stage K extension now resolves the remaining shared-worker identity through the already-saved guest x26 value rather than another frame walk.

Runtime resolver:

`x26 node -> [node] work object -> [work] vtable -> [vtable+0x10] shim -> [vtable+0x60] work target`

Implementation properties:

- remains inside the existing Stage F selected-producer scope
- reuses the existing Stage G guest-context sample
- reads `x1_stage_g_context.r[26]` exactly once
- adds exactly four work-target `Read64` sites
- Stage K total is six `Read64` / six Stage-K range checks including the existing two grandparent reads
- no new stack depth
- no second context capture
- dynamic `main` range registered from the existing Stage H loader path
- resolved shim/work addresses normalized immediately to offsets
- work-pair histogram stores only normalized `(shim_offset, work_offset)`
- 64 fixed work-pair slots per producer
- top4 every 120 frames
- resolved / other-resolved / overflow / resolver-status accounting retained
- runtime C++ does not hardcode the common shim or any known TOTK component target
- analyzer owns the 41-slot / 36-target semantic map

## Ubuntu static validation — SUCCESS

Full exact-dc95 reconstruction validator:

- workflow: `Validate dc95 X1 Waker Stage K Work Target`
- run: `33350134250`
- job: `99361721220`
- head: `6cc9b75d4446aa55fa18837fe73376f8fb48d5b5`
- attempt: `1`
- result: **SUCCESS**

Analyzer incomplete-cadence regression gate:

- run: `33350373759`
- job: `99362422228`
- head: `e51dc7ec854b1afc7ef46a25f7d749e4c9584f49`
- attempt: `1`
- result: **SUCCESS**

The temporary push validator was removed at:

`09916c69671607f4d6240dc3ea3121e37372b45b`

These were Ubuntu static validation runs, not Windows ARM64 attempts.

## Current decision

The Stage K work-target identity design, implementation, and Ubuntu static validation are complete.

**Do not create Stage L.**

**Do not implement an optimization yet.**

The next useful evidence is a Windows ARM64 runtime capture of the implemented Stage K work-target resolver, but that action is blocked by the authorization rule.

## Immediate next action — BLOCKED ON FRESH ARM64 AUTHORIZATION

Current ARM64 authorization: **NONE**.

Until the user explicitly authorizes one Windows ARM64 attempt:

- do not build or rebuild ARM64;
- do not dispatch the persistent Windows ARM workflow;
- do not rerun any old ARM job;
- do not create a one-shot ARM dispatcher;
- do not change the fixed baseline;
- do not add Stage L or broaden profiling.

If fresh authorization is later given, it permits exactly one Windows ARM64 attempt.

Before that single attempt:

1. verify branch HEAD and source-of-truth documents;
2. verify `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml` remains `workflow_dispatch` only;
3. update that persistent manual workflow only as required to reconstruct the current Stage K work-target implementation;
4. verify no push/pull-request ARM trigger is introduced;
5. dispatch exactly one ARM attempt;
6. do not retry automatically if it fails.

If the build succeeds, the runtime capture should remain Res1X and should collect enough 120-frame windows to cover the strict swap2 and swap3 sets. The analyzer must examine:

- normalized common-shim/work-target pairs;
- ModuleSystem component identities;
- `workResolvedTicks`;
- `workOtherResolvedTicks`;
- `workOverflowTicks`;
- resolver-status coverage;
- equal-window fast/slow visible lower-bound target ticks.

A concrete component owner is acceptable only if coverage is sufficient. Unknown or non-common-shim targets remain evidence and must not be guessed.

`EventModuleSubWorker` remains a separate already-resolved branch and must not be folded into the shared ModuleSystem histogram.

No behavior-changing optimization is justified until this runtime owner attribution is available.
