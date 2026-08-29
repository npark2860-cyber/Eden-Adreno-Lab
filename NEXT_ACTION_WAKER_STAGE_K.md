# NEXT ACTION — Waker Stage K Dynamic Grandparent Attribution

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_BUILD.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized by this document.

## Stage J result

Stage J parent-LR capture is valid for essentially all selected-producer CPU ticks and exactly reconciles with Stage G/F accounting.

Dominant canonical triples:

- `sdk+0x158528 / sdk+0x124a8c / main+0x86a820`
- `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54`
- `sdk+0x158528 / sdk+0x124b40 / main+0x86be08`
- `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc`

Exact semantics:

- WaitLightEvent -> WaitForAddress
- ReceiveLightMessageQueue -> WaitForAddress
- LockMutex -> InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock

Visible top-four triples explain about `61%` / `54%` of producer 0 / producer 1 CPU growth; overflow remains material but does not prevent dominant-family identification.

The producer CPU-growth and producer Arbitration-growth branches both remain, and dynamic-waker CPU/Arbitration remains separate.

## Offline reverse-call exhaustion after Stage J

Exact dumped game/SDK images were inspected before proposing any new runtime instrumentation.

### WaitLightEvent parent A

`main+0x86a820` lies in the stripped function beginning around `main+0x86a4ac`.

Direct callers of that function: only 2.

- one from a wrapper around `main+0x86a464`, which has no direct BL caller;
- one from a function around `main+0x7edaf8`, which has 14 direct BL callers.

Static analysis cannot tell which dynamic path owns each selected-producer slice.

### WaitLightEvent parent B

`main+0x86be08` lies in the stripped function beginning around `main+0x86bd40`.

It has exactly one direct caller, `main+0x86bc98`, in a function beginning around `main+0x86bc04`.

No direct BL caller to `main+0x86bc04` was found, so the next owner is likely reached indirectly/callback-style; do not guess it.

### ReceiveLightMessageQueue parent

`main+0x2a904cc` lies in a stripped function beginning around `main+0x2a90478`.

Direct BL callers: 0.

Static analysis cannot recover the dynamic callback owner.

### Critical-section parent

`sdk+0x127e54` is `nn::os::LockMutex`.

The corresponding main import/PLT target has 6,201 direct BL call sites. Static reverse-call analysis is exhausted for this branch.

## Smallest remaining evidence

If the user chooses to continue, Stage K should add exactly one more frame-pointer caller level to the already-selected Stage F producer pair.

At the same existing Stage G/J selected-producer switch-out point:

1. reuse the current saved `fp`;
2. Stage J already obtains `parent_lr = [fp+8]`;
3. validate and read `parent_fp = [fp]`;
4. if `parent_fp` is nonzero/aligned, monotonic/sane, and `[parent_fp+8, parent_fp+16)` is a valid application virtual range, read exactly one `grandparent_lr = [parent_fp+8]`;
5. attribute the same exact scheduler `tick_diff` to `(pc, lr, parent_lr, grandparent_lr)` in a bounded fixed table;
6. report only every 120 frames.

This is one additional frame-record level, not stack scanning.

Before implementation, verify from the exact dumped binaries that the relevant Stage J parent functions preserve standard AArch64 frame records. The known SDK LockMutex and the visible main parent functions do so in the inspected paths, but the transplant/static validator must enforce the memory-read safety shape rather than assume runtime addresses.

## Hard limits

Stage K must not:

- hardcode Stage J observed PC/LR/parent addresses or producer TIDs;
- filter by observed absolute addresses;
- rediscover threads;
- sample non-selected threads;
- walk an arbitrary-length stack;
- add per-switch logging;
- widen Stage G/J 64-slot tables merely because overflow is nonzero;
- alter priority, affinity, core placement, yield/reschedule, waits/signals, GPU work, QueueBuffer, frame cadence, or A/B behavior.

Any second frame-record read must be range-validated and observation-only.

## Decision after Stage K runtime

A. Grandparent LR collapses the dominant families to a small stable `main/subsdk0` owner set:

> map exact module offsets offline and determine whether the CPU-growth branch can finally be assigned to concrete game work.

B. A major family still lands in generic SDK code:

> resolve that wrapper offline first; do not automatically add another depth.

C. Grandparent frame validity degrades materially for a specific family:

> stop frame walking and inspect that family's exact frame/prologue/unwind semantics; do not introduce broad stack scanning.

D. Grandparent is stable but overflow still contains most unexplained CPU growth:

> only then reconsider bounded histogram representation for the selected producers.

Do not optimize merely from synchronization function names.

## ARM64 gate

Current authorization: **NONE**.

Stage K implementation and Ubuntu/static validation would not consume ARM64 authorization.

A Windows ARM64 Stage K attempt would require a new explicit user authorization, one attempt only. Failure would not authorize retry/rerun.