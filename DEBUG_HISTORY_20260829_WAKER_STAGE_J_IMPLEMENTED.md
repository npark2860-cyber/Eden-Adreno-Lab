# DEBUG HISTORY — 2026-08-29 Waker Stage J Implemented / Ubuntu Static

## Scope

Stage J adds exactly one caller-depth level to the already-selected Stage F producer pair, after Stage I resolved the dominant Stage G slice-end contexts to Nintendo SDK synchronization functions but offline reverse-call analysis remained non-unique.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage J branch:

`exp/x1-waker-stage-j-caller-depth`

Branch base:

`70d20a1cfdb5437d86bc06c52bd2fe05e3966412`

Current ARM64 authorization: **NONE**.

No Windows ARM64 build/rebuild/rerun was performed during Stage J implementation/static validation.

## Stage I basis

Exact dumped Nintendo SDK binary analysis resolved the recurring Stage G contexts to:

- `nn::os::WaitLightEvent -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`
- `nn::os::ReceiveLightMessageQueue -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`
- `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`

The Stage G saved PC is the `ret` immediately after the blocking SVC wrapper. Stage G's scheduler `tick_diff` still measures the entire active guest CPU slice leading to that blocker, not time spent at the `ret` itself.

Static reverse-call inspection of the exact uploaded game image found:

- 73 direct `main` call sites to `nn::os::WaitLightEvent`;
- 4 direct `main` call sites to `nn::os::ReceiveLightMessageQueue`.

Therefore first-level offline caller evidence cannot uniquely identify the selected producer owner.

The relevant SDK functions preserve the standard AArch64 frame record (`x29/x30`), and exact dc95 `Svc::ThreadContext` exposes saved `fp`. Exact dc95 application memory provides virtual-range validation and `Read64`.

## Implementation

Files:

- `src/core/x1_waker_stage_j_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_j_caller_depth.py`
- `tools/adreno_lab/analyze_x1_waker_stage_j_caller_depth.py`

### Selected-producer-only parent LR sampling

Stage J does not add a new scheduler hook and does not rediscover threads.

It extends the existing Stage G switch-out block only after Stage F's dynamic selector:

`GetTrackedProducerIndex(cur_thread->GetThreadId()) >= 0`

For those two selected producers only:

1. reuse the saved `Svc::ThreadContext` already read by Stage G;
2. read saved `fp` (`x29`);
3. reject zero, unaligned, or overflowed frame pointers;
4. form the guest slot at `fp + 8`;
5. validate the 8-byte application virtual range;
6. perform exactly one `ApplicationMemory().Read64()` at that slot;
7. record `(pc, lr, parent_lr)` with the same exact scheduler `tick_diff`.

Parent-read status is retained separately:

- valid;
- zero fp;
- unaligned/overflow fp;
- invalid guest range;
- zero parent LR.

### Bounded report

Marker:

`[X1-WAKERJ]`

Shape:

- 2 producers;
- fixed 64 context slots per producer;
- top 4 triples by CPU ticks;
- 120-frame report cadence;
- no per-switch logging.

The Stage J key is the exact triple:

`PC / LR / parent-LR`

The offline analyzer joins all three raw addresses against the Stage H module ranges and retains raw values for audit.

Stage G's 64-slot table is unchanged.

## Safety / scope invariants

Stage J does not:

- hardcode observed producer TIDs, promoted arbiter keys, guest PC/LR values, or module bases;
- sample non-selected threads;
- alter Stage F producer selection;
- alter Stage G PC/LR accounting;
- alter Stage H loader mapping;
- change priority, affinity, core placement, yield/reschedule behavior, waits/signals, GPU work, QueueBuffer, or cadence;
- add stack scanning or arbitrary guest-memory walking.

Only one validated 64-bit guest memory read site is added, after dynamic producer selection.

## Ubuntu static validation attempt 1 — FAILED SELF-CHECK ONLY

Temporary workflow:

`Validate dc95 X1 Waker Stage J`

- run: `33249591877`
- job: `99092859932`
- head: `8c0330cc5abc64aa748b949441ec8451877c39fa`
- event: `push`
- runner: `ubuntu-latest`
- conclusion: `failure`

Before the failure, exact dc95 checkout and the retained diagnostic chain through Stage H all reconstructed successfully.

The failure occurred in the Stage J transplant's own static hardcode guard:

`RuntimeError: Stage J must not hardcode runtime observation 0x80`

Root cause was not a runtime hardcode in generated emulator code. The self-check incorrectly scanned the transplant source itself, including the literal forbidden-value list used by the guard. The check was corrected to inspect only the Stage J profiler and generated C++ insertion block.

No ARM64 runner was involved and no ARM retry rule was consumed.

## Ubuntu static validation attempt 2 — SUCCESS

After the self-check correction:

- run: `33249656888`
- job: `99093038064`
- head: `4e2d7fb33d5fb368923711e446d9b85b2db3aac2`
- event: `push`
- runner: `ubuntu-latest`
- conclusion: `success`

Validated on the full exact-dc95 reconstruction through Stage H:

- exact dc95 source SHA preservation;
- Stage J transplant applies cleanly;
- `git diff --check`;
- transplant/analyzer `py_compile`;
- exact `Svc::ThreadContext` saved `fp` availability;
- exact application-memory virtual-range validation availability;
- exact `Read64` availability;
- exactly one `[X1-WAKERJ]` log site;
- exactly one Stage J guest `Read64` site;
- exactly one saved-fp use site;
- exactly one Stage J scheduler RecordCpuSlice call;
- Stage F header unchanged;
- Stage G header unchanged;
- Stage H loader unchanged;
- Stage J read is after Stage F selected-producer guard;
- no runtime-observation hardcodes;
- no behavior-changing scheduler/rasterizer additions;
- synthetic analyzer mapped `PC=sdk+0x100`, `LR=sdk+0x200`, `parent=main+0x500` correctly.

The temporary validation workflow was deleted after success.

## Persistent ARM workflow — PREPARED, NOT DISPATCHED

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Prepared name:

`Build dc95 X1 Waker Stage J`

Trigger remains exactly:

`workflow_dispatch` only.

Prepared artifact name:

`Eden-dc95-X1-waker-stage-j`

The workflow reconstructs the retained chain through Stage H, snapshots pre-Stage-J invariants, applies Stage J, verifies the selected-producer/fp/one-read safety shape, then enters the existing Windows ARM64 configure/build/package path only if manually dispatched.

As of Stage J preparation, branch run history contains only the two Ubuntu `push` validation runs above. Stage J `workflow_dispatch` ARM run count is **0**.

## Conclusion

Stage J implementation and static validation are complete.

The next runtime evidence, if separately authorized and built, will identify one parent caller level above the known SDK synchronization functions for only the two dynamically selected producer threads.

No optimization conclusion is justified yet.

## ARM64 gate

Current authorization: **NONE**.

A fresh explicit user authorization is required for exactly one Stage J Windows ARM64 attempt. Failure would not authorize a retry/rerun.
