# NEXT ACTION — Waker Stage I SDK Semantic Mapping

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_BUILD.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-h-module-callpath-mapping`

Never change the exact Eden baseline without explicit approval.

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is needed for the immediate Stage I action.

## Stage H runtime result

Runtime:

`eden_log(20260829-103238).txt`

Stage H selected decision-map case A.

All recurring Stage G top contexts normalize to the same loaded `sdk` module:

- `sdk+0x158528 / sdk+0x124a8c`
- `sdk+0x158420 / sdk+0x13178c`
- `sdk+0x158528 / sdk+0x124b40`
- `sdk+0x158528 / sdk+0x127058`

The separate Stage D dynamic-waker path also repeatedly reports:

- PC `sdk+0x158528`
- LR `sdk+0x124b40`
- LR `sdk+0x124a8c`
- occasional `sdk+0x13178c`
- occasional `sdk+0x13f364`

Therefore the observed producer and waker CPU branches share a Nintendo SDK/runtime path family. This is direct module/caller evidence, but it does not yet establish the exact operation or causal owner.

Keep distinct:

1. producer CPU growth;
2. producer Arbitration growth;
3. dynamic-waker CPU growth;
4. dynamic-waker Arbitration growth.

Do not optimize yet.

## Immediate Stage I action — no new build

Obtain the exact runtime `sdk` NSO using Eden's existing dump path.

The current Stage H log shows:

- sdk build ID: `B9046C31EB5D31271BE970FE732D38DF49C6AA21`
- sdk runtime range: `0x85530000-0x86309000`

Exact dc95 source already supports:

- setting: `Debugging.dump_nso`
- UI: `Dump Decompressed NSOs`

Exact dc95 `PatchManager::PatchNSO()` writes the decompressed flat image under the configured Dump Root:

`<Dump Root>/<title-id>/nso/<name>-<build-id>.nso`

Expected file for this game/runtime:

`sdk-B9046C31EB5D31271BE970FE732D38DF49C6AA21.nso`

Enable `Dump Decompressed NSOs`, boot TOTK once far enough for the SDK to load, then collect only that SDK dump. No gameplay capture is required for the dump itself.

After confirming the file exists, the setting can be turned back off.

## Offline analysis target

Parse the dumped flat NSO image and inspect AArch64 code/function boundaries around these module-relative offsets:

Primary endpoints:

- `0x158528`
- `0x158420`

Producer/waker LR family:

- `0x124a8c`
- `0x124b40`
- `0x127058`
- `0x13178c`
- `0x13f364`

Required output:

1. exact instructions around each offset;
2. containing function boundaries where recoverable;
3. direct branch/call targets around the LR sites;
4. whether `0x158528` / `0x158420` are generic SDK scheduler/synchronization endpoints, SVC wrappers, lock/condvar/arbitration helpers, or another runtime subsystem;
5. whether the LR family converges on one caller function or multiple distinct SDK operations;
6. any dynamic symbol / MOD0 / unwind / exception-frame evidence usable to recover names or boundaries;
7. exact evidence chain only — no guessed symbol name without binary support.

## Decision after SDK disassembly

A. `sdk+0x158528` / `sdk+0x158420` resolve to a recognizable synchronization primitive and LR sites identify a small caller set:

> trace the caller semantics first; no new runtime instrumentation yet.

B. endpoints are generic veneers/SVC wrappers but LR sites resolve the caller functions sufficiently:

> follow LR caller functions offline before adding depth.

C. endpoints and LR sites remain semantically opaque after binary analysis:

> only then design the smallest selected-producer-only extra caller-depth evidence.

D. the fixed 64-slot overflow still hides a distinct dominant normalized SDK family after semantic mapping:

> only then redesign the histogram/slot budget.

## ARM64 gate

Current authorization: **NONE**.

Dumping the existing runtime NSO is not an ARM64 build attempt.

Any future Stage I/Stage J ARM64 build requires a new explicit authorization. One authorization remains exactly one attempt with no automatic retry/rerun.
