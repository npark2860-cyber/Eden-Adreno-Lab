# NEXT ACTION — ARM64 Exclusive Read / LDXR Attribution

Updated: 2026-09-01 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_PAIR_PARTIAL_MAPPING.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`

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

## Latest exclusive-write experiment — CLOSED

Authorized build/run:

- workflow run `33503843213`
- job `99843127546`
- attempt `1`
- workflow head `fc843a23246e6ee7134b14b3692376b875c5993c`
- result: **SUCCESS**
- retry/rerun: none

Runtime log:

`eden_log(20260901-134628).txt`

Exact runtime identity:

- Eden `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- Qualcomm Adreno X1-85
- main NSO build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`

## Runtime conclusion

`[X1-XEXCL]` measured selected-producer exclusive-write/STXR operations at Dynarmic ARM64 `DoExclusiveOperation(...)`.

Closed findings:

1. **STXR contention/retry storm is not the primary owner.**
   - heavy-window failure rates stay below approximately `0.52%`.

2. **Per-call STXR callback slowdown is not present.**
   - `callbackAvgNs` remains approximately `112-132 ns` across light and heavy windows.

3. **Direct measured STXR callback time is not dominant.**
   - approximately `3-5%` of selected-producer CPU wall in compared windows.

4. **Exclusive-write volume strongly follows producer CPU growth.**
   - frame 720 -> 1080 producer 0: attempts `3.62x`, CPU wall `3.77x`.
   - frame 720 -> 1080 producer 1: attempts `2.86x`, CPU wall `3.48x`.

Therefore the exclusive path is a strong workload marker/component, but the measured STXR callback body itself is not the missing dominant CPU owner.

Do not reopen STXR retry storm or per-call callback slowdown without new evidence.

## Immediate next experimental frontier

The current experiment did **not** measure the exclusive-read/LDXR side.

Dynarmic ARM64 already has the dedicated path:

`EmitExclusiveReadCallTrampoline(...)`

which executes:

`global_monitor->ReadAndMark<T>(...)`

If a fresh Windows ARM64 attempt is explicitly authorized, the next minimal experiment is:

**selected-producer exclusive-read / LDXR `ReadAndMark` attribution**

Use the same two Stage F selected producers and the same 120-frame reporting boundary.

Record only observation data:

- exclusive-read attempts
- size split (8/16/32/64/128 where applicable)
- cumulative `ReadAndMark` time
- average `ReadAndMark` time
- maximum `ReadAndMark` time

Correlate the result against:

- `[X1-XEXCL]` STXR time/attempts
- `[X1-WAKERG]` producer CPU wall/ticks
- actual `[X1-CADENCE]` swap2/swap3 evidence in that runtime

Do not assume fixed frame numbers from an older runtime. The latest log is swap2 around frame 720/744 and swap3 by frame 1101 and at 1199/1200.

## Implementation constraints

Observation only.

Do not change:

- guest atomic/exclusive semantics
- global-monitor behavior
- CPU accuracy or unsafe options
- scheduler priority/affinity/yield/reschedule
- waits/signals
- GPU behavior
- QueueBuffer behavior
- cadence/frame pacing
- immutable Eden baseline

Do not broaden to all threads.

Resolve selected producer identity once per Dynarmic run slice, as in the STXR experiment; do not perform expensive producer lookup inside every exclusive-read operation.

No new Stage L is needed.

## Parallel offline semantic work still open

The prior Stage K semantic frontier remains valid and independent of the exclusive experiment.

Unresolved non-common work-object owners:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x244fc20 -> main+0x2ad6b20`

Known owner already closed:

`main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker** owner pair.

The exact NSO for offline naming remains:

`main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`

Do not infer semantic names without the exact binary evidence.

## Stop condition

Without fresh ARM authorization, stop after static design/implementation validation or offline NSO analysis.

Do not dispatch a Windows ARM64 build automatically.
