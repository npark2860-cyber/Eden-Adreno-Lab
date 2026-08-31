# NEXT ACTION — Waker Stage K Work-Target Identity Implementation

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

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized. One authorization always means exactly one ARM attempt, with no implicit retry after failure.

## Stage K canonical runtime state

Successful Windows ARM64 Stage K build:

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- artifact: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- retry/rerun: none

Persistent ARM workflow remains `workflow_dispatch` only.

Primary runtime source:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Strict cadence windows remain:

- fast / swap2: `960`, `1080`
- slow / swap3: `1320`, `1440`, `1560`, `1680`

Mixed windows `840` and `1200` are not primary evidence.

The Res2X capture remains invalid for resolution-sensitivity inference because of abnormal quarter-screen rendering and 19,776 unsupported depth-scaling errors.

## Offline grandparent / semantic mapping — CLOSED

Durable Stage K classification:

- `main+0x86bc9c` = **EventModuleSubWorker** coordination/execution branch
- `main+0x86a490`, `main+0x86a530`, `main+0x86a678` = shared dependency-worker / ModuleSystem dispatcher branch
- `main+0x2a2d958` = generic indirect message/thread-dispatch frontier

The shared ModuleSystem execution chain is exact:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Static enumeration is complete:

- 41/41 ModuleSystem slots mapped
- 36 unique concrete `vtable+0x60` targets
- unnamed slots 17 and 37 remain deliberately unnamed no-op components

Do not create Stage L for more stack depth.

## Work-target identity design — COMPLETE

Canonical design record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`

The design resolves the remaining shared-worker identity through the already-saved guest `x26` register rather than another frame walk.

Exact work-dispatch anchor:

```text
main+0x86a97c: LDR x0, [x26]
main+0x86a980: LDR x8, [x0]
main+0x86a984: LDR x8, [x8, #0x10]
main+0x86a988: BLR x8
```

Existing Eden dc95 `ThreadContext` stores `r[0..28]`, so the existing Stage G context sample exposes saved `x26` as `x1_stage_g_context.r[26]`. No second guest-context sample is needed.

Preferred resolver:

`x26 node -> [node] work object -> [work] vtable -> [vtable+0x10] shim target -> [vtable+0x60] work target`

Required properties:

- exactly four additional `Read64` sites inside the already-selected producer scope
- range validation before every read
- no arbitrary stack scan/walk
- no runtime hardcode of `main+0x2af1230` or any component target
- register dynamic `main` range from the existing Stage H loader path
- normalize resolved shim/work targets immediately to `main+offset`
- store/report normalized offsets only
- fixed 64 pair slots per producer
- report every 120 frames
- top 4 pairs plus `resolvedTicks`, `otherResolvedTicks`, `overflowTicks`, and resolver validity accounting
- preserve existing `tick_diff` as the CPU cost attributed to each resolved pair

Offline analysis, not runtime C++, recognizes normalized shim `main+0x2af1230` and maps work offsets against the existing 41-slot / 36-target semantic table.

## Immediate next action — IMPLEMENTATION / STATIC VALIDATION ONLY

The design phase is closed.

If continuing, implement this work-target identity resolver as a **Stage K extension**, not a new Stage L.

Implementation must remain observation-only and may be statically validated without consuming ARM64 authorization.

Implementation scope is limited to:

1. extend the existing Stage K profiler with dynamic `main` range registration and a bounded normalized `(shim_offset, work_offset)` histogram;
2. reuse the existing Stage G context sample and read `x1_stage_g_context.r[26]` only inside the existing Stage F selected-producer guard;
3. add the four validated pointer reads defined by the design record;
4. add resolver status/coverage/overflow accounting;
5. extend the existing offline analyzer to map normalized common-shim pairs to the static ModuleSystem component table;
6. add static checks proving no observed raw/normalized TOTK target address is hardcoded into runtime C++;
7. preserve all existing Stage F/G/J/K profiler scope, output cadence, and behavior invariants.

Do not alter priority, affinity, yield, scheduling behavior, waits/signals, QueueBuffer, GPU work, cadence, synchronization semantics, or the fixed Eden baseline.

Do not retarget or dispatch the Windows ARM workflow during implementation/static validation.

## Runtime gate after implementation

A Windows ARM64 build/run remains blocked until fresh explicit user authorization.

If such authorization is later given:

- one authorization = exactly one ARM attempt;
- no automatic retry/rerun after failure;
- persistent workflow must remain `workflow_dispatch` only;
- the future capture is accepted only if common-shim resolved coverage is sufficient and strict swap2/swap3 component tick comparison is possible.

`EventModuleSubWorker` remains a separate already-resolved branch and must not be merged with the shared ModuleSystem work-target histogram.

No behavior-changing optimization is justified yet.
