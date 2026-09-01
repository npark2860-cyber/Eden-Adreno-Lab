# NEXT ACTION — Waker Stage K Runtime Work-Target Semantic Mapping

Updated: 2026-09-01 KST

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
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_WORK_TARGET_RUNTIME.md`

Use GitHub documents as source of truth. Do not reconstruct state from chat guesses.

## Fixed baseline / branch

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent ARM workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

Current ARM64 authorization:

**NONE**

Do not build/rebuild/rerun Windows ARM64 without a fresh explicit authorization. No ARM build is needed for the immediate next action.

## Latest successful x26 Windows ARM64 build

Run:

`33475954305`

Job:

`99755146485`

Attempt:

`1`

Workflow head SHA:

`94856d2d8517e76fcd39289e2f3a52560736e6b2`

Result:

**SUCCESS**

Artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- ID: `9788853936`
- size: `31,431,536` bytes
- SHA-256: `d782e5f3b575c4c088e4af8be5e86a43b2a3b46b9807c9715a5aac140c55e411`

The temporary one-shot dispatcher was removed after the single authorized attempt.

## Runtime source now available

User runtime log:

`eden_log.txt`

Confirmed from log:

- Eden exact baseline: `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- `Renderer.resolution_setup: Res1X`
- exact main build ID: `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- main runtime range: `0x805d6000..0x84d01000`
- x26 Stage K work-target fields are populated.

Raw runtime VAs are observations only. Use `main+offset` for durable analysis.

## Runtime work-target identity — OBSERVED

The resolver now emits normalized pairs in the form:

`workTopN=<shim_offset>/<work_target_offset>/<ticks>/<count>/<percent>`

Recurring dominant non-common-shim pairs:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x86bc04 -> main+0x2ada93c`
3. `main+0x244fc20 -> main+0x2ad6b20`

Known common ModuleSystem shim also appears:

`main+0x2af1230 -> component vtable+0x60 target`

Observed common-shim examples include `main+0xc1c28c`, `main+0xa5df60`, and `main+0x2adbb54`.

Do not fold the three non-common-shim paths into ModuleSystem without static proof.

## Existing closed semantic anchors

Keep these closed findings intact:

- `main+0x86bc9c` = **EventModuleSubWorker** coordination/execution branch.
- `main+0x86a490`, `main+0x86a530`, `main+0x86a678` = shared dependency-worker / ModuleSystem dispatcher branch.
- `main+0x2a2d958` = generic indirect thread/message-dispatch frontier.
- `main+0x2af1230` = common ModuleSystem shim to component `vtable+0x60`.
- 41 / 41 ModuleSystem slots are statically mapped; 36 unique concrete work targets.

Do not create Stage L.

## Immediate next action — OFFLINE ONLY

Use the exact dumped TOTK 1.2.1 main NSO with build ID:

`9B4E43650501A4D4489B4BBFDB740F26AF3CF85`

Disassemble and reference-trace these three paths:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x86bc04 -> main+0x2ada93c`
3. `main+0x244fc20 -> main+0x2ad6b20`

For each path, determine the strongest durable semantic owner using:

- function code shape;
- callers / xrefs;
- vtable entries;
- constructors/destructors;
- registration tables;
- nearby strings / RTTI-like names where available;
- comparison with already-resolved Stage K anchors.

The current tab had begun trying to extract the exact dumped `main-...nso` from the user-provided dump ZIP. If the archive is not visible in the next tab, re-obtain/re-upload that exact dump. Do not substitute a different game revision or guess from offsets alone.

## Runtime correlation after semantic names are known

Then compare the three mapped owners across the strict cadence windows:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Use both producers and retain:

- `workResolvedTicks`
- `workOtherResolvedTicks`
- `workOverflowTicks`
- resolver-status coverage
- visible top4 lower bounds

Do not claim a sole causal owner from top4 percentages alone because top4 censoring and unresolved/other-resolved buckets remain.

## Stop condition

Stop after semantic mapping + strict slow/fast interpretation unless the user explicitly authorizes a new source experiment.

Do not implement behavior-changing scheduler/GPU/QueueBuffer/wait/signal/priority/affinity/yield changes from this evidence alone.
