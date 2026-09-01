# NEXT ACTION — ARM64 Exclusive Read / LDXR Runtime Attribution

Updated: 2026-09-01 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_READ_IMPLEMENTED.md`

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-arm64-exclusive-callback-attribution`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent Windows ARM64 workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow trigger remains:

`workflow_dispatch` only.

Current ARM64 authorization:

**NONE**

Do not build/rebuild/rerun Windows ARM64 without a fresh explicit user authorization. One authorization means exactly one attempt; failure does not authorize retry.

## Exclusive-write / STXR runtime — CLOSED

Authorized build/run:

- workflow run `33503843213`
- job `99843127546`
- attempt `1`
- workflow head `fc843a23246e6ee7134b14b3692376b875c5993c`
- result: **SUCCESS**
- retry/rerun: none

Runtime log:

`eden_log(20260901-134628).txt`

Closed findings:

1. STXR contention/retry storm is not the primary owner; heavy-window failure rates remain below about `0.52%`.
2. Per-call STXR callback slowdown is absent; average remains about `112-132 ns`.
3. Direct STXR callback time is only about `3-5%` of selected-producer CPU wall in compared windows.
4. STXR volume strongly tracks producer CPU growth, so exclusive traffic remains a useful workload marker.

Do not reopen STXR retry-storm or per-call STXR slowdown without new evidence.

## Exclusive-read / LDXR implementation — READY

Implementation is complete and statically validated against exact dc95.

Temporary Ubuntu validator run:

`33517281924`

Result:

**SUCCESS**

The temporary validator workflow was removed after success.

The existing `[X1-XEXCL]` record retains STXR fields and appends:

- `readAttempts`
- `readNs`
- `readAvgNs`
- `readMaxNs`
- `readBadSize`
- size splits `rs8`, `rs16`, `rs32`, `rs64`, `rs128`

Measured path:

`EmitExclusiveReadCallTrampoline -> global_monitor->ReadAndMark<T>`

and the 128-bit `Vector` equivalent.

Producer identity is still resolved once per Dynarmic RunThread slice, not per exclusive operation.

No guest atomic semantics, global-monitor behavior, scheduler behavior, GPU behavior, QueueBuffer behavior, or cadence behavior was changed.

## Immediate next action

A fresh explicit Windows ARM64 authorization is required before runtime validation.

If authorized, perform exactly one build/run attempt from the current experiment branch and obtain a runtime log containing the new appended LDXR fields.

Then compare actual cadence windows from that same runtime, not fixed frame IDs copied from older logs.

Primary questions:

1. Does LDXR `ReadAndMark` average time rise materially in slow/swap3 windows?
2. Does LDXR attempt volume rise in proportion to producer CPU wall?
3. What fraction of selected-producer CPU wall is explained by `readNs + callbackNs`?
4. Does combined LDXR+STXR exclusive time become large enough to explain the `gsys::SystemTask` / `EventModuleSubWorker` slowdown, or is exclusive traffic merely a workload marker?

## Stage K semantic owner status — CLOSED

The prior dominant non-common owners are no longer unresolved.

- `main+0x96e2a8 -> main+0x26936d0` = **`gsys::SystemTask` internal work/phase dispatcher**
- `main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker** owner pair
- `main+0x244fc20 -> main+0x2ad6b20` = **`ActorAIGroupMgr::Job`**

Runtime correlation keeps `gsys::SystemTask` and EventModuleSubWorker higher priority than ActorAIGroupMgr::Job.

## Stop condition

Without fresh ARM authorization, stop here.

Do not automatically dispatch Windows ARM64.
Do not create Stage L.
Do not implement behavior-changing optimization from LDXR/STXR suspicion alone.
