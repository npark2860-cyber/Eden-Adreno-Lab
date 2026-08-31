# NEXT ACTION — Waker Stage K Post-Mapping Narrow Attribution

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

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized. One authorization always means exactly one ARM attempt, with no implicit retry after failure.

## Stage K build/runtime state

Canonical successful Windows ARM64 Stage K build:

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

Primary runtime source remains:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

Use only pure cadence windows for strict comparison:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Do not use mixed frames `840` or `1200` as primary evidence.

The Res2X capture remains invalid for resolution-sensitivity inference because it showed abnormal quarter-screen rendering and 19,776 unsupported depth-scaling errors.

## Offline grandparent mapping — CLOSED

Exact dumped TOTK 1.2.1 main NSO:

`main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`

All addresses below are ASLR-normalized `module+offset`.

| Stage K grandparent | Exact mapping | Durable classification |
|---|---|---|
| `main+0x86a490` | `main+0x86a48c: BL main+0x86a4ac` | shared dependency-worker callback into dispatcher |
| `main+0x86bc9c` | `main+0x86bc98: BL main+0x86bd40` | **EventModuleSubWorker** coordination/execution path |
| `main+0x2a2d958` | `main+0x2a2d954: BLR x8` | generic indirect thread/message-dispatch frontier |
| `main+0x86a530` | `main+0x86a52c: BL main+0x2b17270` | shared dispatcher LockMutex site A |
| `main+0x86a678` | `main+0x86a674: BL main+0x2b17270` | shared dispatcher LockMutex site B |

`main+0x86a490`, `main+0x86a530`, and `main+0x86a678` converge on the same shared dependency-worker scheduler/dispatcher rather than three independent game owners.

The shared concrete worker implementation is reused by:

- `ModuleSystemWorker`
- `NavMeshDepWorker`
- `NavMeshCAStepDepWorker`
- `phive::DepWorker`

## ModuleSystem work execution — CLOSED STATICALLY

Scheduler pointer flow is now exact:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

`main+0x11d1b14` constructs a 41-slot ModuleSystem component list.

Static enumeration is complete:

- 41/41 component slots mapped
- 36 unique concrete `vtable+0x60` targets
- slot names include `System`, `DenguModule`, `Resource`, `RSDB`, `Graphics`, `Actor`, `Physics`, `Event`, `EventModuleWorker`, `EventModuleSubWorker`, `UI`, `Sound`, `GameData`, `Blackboard`, `Camera`, `LOD`, `Rail`, `PlayReport`, and others recorded in the offline semantic-mapping history
- slots 17 and 37 intentionally return an empty component name and execute `main+0x26a7fc0: RET`; keep them as unnamed no-op components and do not invent names

The existing Stage K runtime record does **not** contain the resolved work-object/vtable identity at `main+0x86a988`, so it cannot tell which of the statically enumerated ModuleSystem components owns each expensive shared-worker slice.

## Strict cadence correlation

Current durable slow/fast growth from Stage K Res1X:

- shared DepWorker callback `main+0x86a490`: P0 `2.130x`, P1 `2.164x`
- **EventModuleSubWorker** `main+0x86bc9c`: P0 `5.590x`, P1 `2.961x`
- generic queue/message frontier `main+0x2a2d958`: P0 `1.232x`; P1 approximately `1.179x` from visible slow windows
- shared dispatcher LockMutex `main+0x86a530`: P1 `4.870x`; P0 slow/fast `>3.684x` because the fast frame 960 value is top-4 censored
- `main+0x86a678`: recurring slow-cadence LockMutex subfamily, but no exact strict aggregate because of top-4 censoring

The generic queue-entry family grows far less than the EventModuleSubWorker and shared-dispatch synchronization families.

## Current decision

The requested Stage K offline semantic mapping is complete.

**Do not create Stage L merely to add another stack depth.**

**Do not implement an optimization yet.**

The remaining attribution gap is not stack depth. It is the concrete work-object/component identity executed through the already-known shared dispatcher.

## Immediate next action — DESIGN ONLY, NO ARM ATTEMPT

Until the user gives fresh explicit ARM64 authorization, do not build, rebuild, rerun, dispatch a workflow, or create a one-shot ARM workflow.

If the investigation continues, design only the smallest bounded identity measurement that can answer:

> For the already-selected producer slices that pass through `main+0x86a988`, which normalized ModuleSystem `vtable+0x60` target is actually being executed, and how does its CPU-tick contribution change between strict swap2 and swap3 windows?

Required constraints for that future measurement:

1. reuse the existing selected-producer / promoted-family scope; no all-thread or global profiling;
2. identify the resolved work-object/component target at `main+0x86a988` / `main+0x2af1230 -> vtable+0x60`;
3. store/report only normalized `main+offset` identities, never raw ASLR VAs;
4. keep output bounded and cadence-comparable; do not add arbitrary stack walking;
5. preserve behavior: no priority, affinity, yield, wait/signal, QueueBuffer, GPU, cadence, or synchronization changes;
6. treat the already-resolved `EventModuleSubWorker` branch separately from shared ModuleSystem work-target attribution;
7. one future ARM authorization, if explicitly granted, permits exactly one attempt and no automatic retry.

A targeted NCE comparison can be considered only after the concrete shared-worker target identity is known or if it can answer the same owner question without widening scope.

No behavior-changing optimization is justified yet.