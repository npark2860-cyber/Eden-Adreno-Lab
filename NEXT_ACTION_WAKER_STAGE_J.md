# NEXT ACTION — Waker Stage J Selected-Producer Caller Depth

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized by this document.

## Stage I result

The exact dumped Nintendo SDK resolves the recurring Stage G endpoints to:

- `nn::os::WaitLightEvent -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`
- `nn::os::ReceiveLightMessageQueue -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`
- `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`

Stage G saved PC is the `ret` immediately following the blocking SVC wrapper. Stage G CPU is still the whole scheduler slice leading to that endpoint, not time spent at the `ret` instruction.

Static reverse-call analysis of the uploaded game `main` finds 73 direct callers of `WaitLightEvent` and 4 direct callers of `ReceiveLightMessageQueue`, so first-level offline caller analysis is not unique enough to identify the selected producer owner.

## Minimal Stage J evidence

Add exactly one extra caller level for the Stage F dynamically selected producer pair only.

At the existing Stage G selected-producer switch-out hook:

1. reuse the already-read saved `Svc::ThreadContext`;
2. read saved `fp` (`x29`);
3. if `fp` is nonzero/aligned and `[fp+8, fp+16)` is a valid application virtual range, read one `u64` from `fp+8`;
4. record `(pc, lr, parent_lr)` with the same scheduler `tick_diff` in a bounded Stage J table;
5. report every 120 rendered frames.

The Nintendo SDK functions identified in Stage I use standard AArch64 frame records, so `[x29+8]` is direct binary-supported caller LR evidence for these contexts.

## Hard limits

Stage J must not:

- rediscover producer TIDs;
- sample non-selected threads;
- hardcode observed TIDs, guest addresses, PC/LR, module bases, or promoted arbiter keys;
- alter priority, affinity, core placement, yield/reschedule, waits/signals, GPU work, QueueBuffer, or cadence;
- add per-switch logging;
- widen Stage G `ContextSlotCount=64`;
- infer that Stage D's independent `latest_pc` and LR histogram form correlated pairs.

The parent-LR read is observation-only and only occurs after Stage F confirms the thread is one of the two dynamically selected producers.

## Runtime decision after Stage J

A. Parent LR collapses the dominant CPU-growth contexts to a small game/module caller family:

> map those parent offsets to exact `main/subsdk0` functions offline, then decide whether another depth is necessary.

B. Parent LR remains inside another generic SDK wrapper but gives a small stable caller family:

> resolve that wrapper offline before adding any further instrumentation.

C. Parent LR is invalid/unavailable for a material fraction of the dominant contexts:

> inspect frame-record assumptions for those specific contexts before considering stack scanning or another mechanism.

D. Parent LR remains too diffuse while 64-slot overflow prevents a dominant family from emerging:

> only then reconsider histogram representation/slot budget.

Do not optimize from Stage I alone.

## ARM64 gate

Current authorization: **NONE**.

Stage J implementation and Ubuntu/static validation do not consume ARM64 authorization.

Any Windows ARM64 Stage J attempt requires a new explicit user authorization. One authorization remains exactly one attempt; failure does not authorize retry/rerun.
