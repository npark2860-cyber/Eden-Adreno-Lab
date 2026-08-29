# NEXT ACTION — Waker Stage J Selected-Producer Caller Depth

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-j-caller-depth`

Current ARM64 authorization: **NONE**.

## Stage I result — COMPLETE

Exact dumped Nintendo SDK analysis resolved the recurring Stage G endpoints to:

- `nn::os::WaitLightEvent -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`
- `nn::os::ReceiveLightMessageQueue -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`
- `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`

Stage G saved PC is the `ret` immediately after the blocking SVC wrapper. Its CPU ticks are the complete active guest slice leading to that blocker, not instruction-residency time at the `ret`.

Static reverse-call analysis found 73 direct `main` call sites to `WaitLightEvent` and 4 to `ReceiveLightMessageQueue`, so offline first-level caller analysis is not unique enough.

## Stage J implementation/static — COMPLETE

Stage J adds exactly one extra caller level to the Stage F dynamically selected producer pair only.

At the existing Stage G selected-producer switch-out block it:

1. reuses the saved `Svc::ThreadContext`;
2. reads saved `fp` (`x29`);
3. validates the standard AArch64 frame-record parent-LR slot `[fp+8, fp+16)`;
4. performs exactly one `ApplicationMemory().Read64()` when valid;
5. records `(pc, lr, parent_lr)` with the same scheduler `tick_diff`;
6. reports a fixed 64-slot/top-4 table every 120 frames.

No new scheduler hook, thread discovery, broad sampling, per-switch logging, behavior mutation, or Stage G slot widening is added.

Ubuntu validation:

- attempt 1: run `33249591877`, job `99092859932` — failed only because the transplant self-check scanned its own forbidden-literal list;
- self-check corrected;
- attempt 2: run `33249656888`, job `99093038064` — **SUCCESS** on full exact-dc95 A-H reconstruction;
- temporary validator deleted after success.

## Persistent Stage J ARM workflow — PREPARED, NOT RUN

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Name:

`Build dc95 X1 Waker Stage J`

Trigger:

`workflow_dispatch` only.

Expected artifact:

`Eden-dc95-X1-waker-stage-j`

Current Stage J branch Actions history contains only the two Ubuntu `push` validation runs above. Stage J `workflow_dispatch` / Windows ARM64 run count is **0**.

## Immediate next action — ARM gate

A fresh explicit user authorization is required before exactly one Stage J Windows ARM64 attempt.

A fresh `ㄱㄱ` received after this ready state means:

> dispatch exactly one `Build dc95 X1 Waker Stage J` ARM64 attempt on `exp/x1-waker-stage-j-caller-depth`.

One authorization = exactly one attempt. Failure does not authorize retry/rerun.

Before dispatch, re-verify:

- current branch HEAD;
- persistent workflow remains `workflow_dispatch` only;
- Stage J `workflow_dispatch` run count is still 0.

After a successful build, runtime capture should use the same TOTK 1.2.1 conditions and collect enough clean swap2 and swap3 120-frame windows. Analyze `[X1-WAKERJ]` together with Stage H module ranges and Stage F/G cadence.

## Runtime decision after Stage J

A. Parent LR collapses dominant CPU-growth contexts to a small `main/subsdk0` family:

> resolve those parent offsets offline before any optimization.

B. Parent LR remains inside a generic SDK wrapper but forms a small stable family:

> resolve that wrapper offline before adding further depth.

C. Parent LR is invalid/unavailable for a material fraction:

> inspect frame-record assumptions for those contexts before considering any broader stack method.

D. Parent LR remains diffuse and overflow blocks a dominant family:

> only then reconsider histogram representation/slot budget.

No optimization is justified yet.
