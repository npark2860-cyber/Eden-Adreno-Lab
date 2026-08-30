# NEXT ACTION — Waker Stage K Offline Grandparent Mapping

Updated: 2026-08-30 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized or required for the immediate next action.

## Stage K Windows ARM64 state — SUCCESS

The post-fix Stage K build succeeded:

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- compile/package/upload: **SUCCESS**
- artifact: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- retry/rerun: none

The one-shot dispatcher was removed at commit:

`112541623742853bdb1c6114959f5bb5317cde89`

Persistent ARM workflow remains `workflow_dispatch` only.

## Runtime capture selection

### Res2X capture — visual/scaling-invalid for performance inference

`eden_log(20260830-025816).txt`

- `Renderer.resolution_setup: Res2X`
- user observed upper-left-quarter-only image
- full-log `BlitScaleHelper` unsupported depth-scaling errors: **19,776**
  - D32_FLOAT: 12,091
  - D16_UNORM: 7,685
- Stage K profiler itself continued to report valid records

Do not use the earlier subjective “2x feels the same speed” observation as GPU-vs-CPU evidence. The scaling path was not proven healthy.

### Res1X capture — primary Stage K runtime source

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

- `Renderer.resolution_setup: Res1X`
- `BlitScaleHelper` unsupported-scaling errors: **0**
- Stage K late-window `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- tiny sporadic `parentUnavailable` only
- no material frame-walk validity collapse

The chat does not contain an explicit textual statement that the Res1X visual output returned to normal, so do not invent that observation.

## Strict cadence windows

Use only pure QueueBuffer cadence windows:

- fast / swap2: `960`, `1080`
- slow / swap3: `1320`, `1440`, `1560`, `1680`

Do not use mixed windows `840` or `1200` as primary evidence.

## Stage K canonical normalized quadruples

Final Res1X module bases normalize the recurring principal families to:

1. `sdk+0x158528 / sdk+0x124a8c / main+0x86a820 / main+0x86a490`
2. `sdk+0x158528 / sdk+0x124b40 / main+0x86be08 / main+0x86bc9c`
3. `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc / main+0x2a2d958`
4. `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54 / main+0x86a530`

The LockMutex family also shows recurring `main+0x86a678`; keep it separate until exact static mapping.

Known semantic chain through Stage J:

- `sdk+0x158528` = return after `WaitForAddress`
- `sdk+0x124a8c / +0x124b40` = `WaitLightEvent`
- `sdk+0x127058` = `ReceiveLightMessageQueue`
- `sdk+0x158420` = return after `ArbitrateLock`
- `sdk+0x13178c` = `InternalCriticalSectionImplByHorizon::Enter`
- `sdk+0x127e54` = `LockMutex`

Stage K's useful result is that these dominant synchronization families now reach concrete `main` grandparent return addresses.

## Immediate next action — NO NEW BUILD

Use the exact dumped TOTK 1.2.1 main NSO already available from Stage I work.

Map these Stage K grandparent offsets offline:

- `main+0x86a490`
- `main+0x86bc9c`
- `main+0x2a2d958`
- `main+0x86a530`
- recurring `main+0x86a678`

For each offset:

1. identify the exact enclosing function / prologue boundary;
2. identify the call instruction whose return address equals the captured grandparent LR;
3. determine whether the caller is a concrete game-work function, generic wrapper, job/callback trampoline, or indirect dispatch frontier;
4. correlate the family with strict swap2 vs swap3 CPU-tick growth;
5. preserve ASLR-normalized `module+offset`, never raw runtime VA.

Do **not** add Stage L merely because a grandparent address exists.

## Decision gate after offline mapping

A. Dominant families converge on a small concrete main-function set with meaningful semantics:

> Stage K is sufficient. Record the owner set and design a narrowly targeted measurement or NCE comparison before any optimization.

B. A dominant grandparent is still a generic wrapper but has a clean frame/caller relationship:

> consider one more bounded depth only for that specific selected-producer family; no arbitrary stack scan.

C. The grandparent lands at indirect/callback/job dispatch boundaries:

> map the registration/job ownership path statically or instrument the specific callback identity; do not globally widen profiling.

D. Overflow, not visible families, owns most slow-cadence growth after strict-window accounting:

> only then reconsider the bounded histogram representation.

No behavior-changing optimization is justified yet.
