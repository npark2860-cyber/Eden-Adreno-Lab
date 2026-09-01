# DEBUG HISTORY — ARM64 Exclusive/STXR Callback Runtime

Updated: 2026-09-01 KST

## Scope

Observation-only runtime validation of selected-producer ARM64 Dynarmic exclusive-write/STXR handling.

Repository branch:

`exp/x1-arm64-exclusive-callback-attribution`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

No scheduler/priority/affinity/yield/wait/signal/GPU/QueueBuffer/cadence behavior was changed.

## Build result

Authorized Windows ARM64 attempt:

- run: `33503843213`
- job: `99843127546`
- attempt: `1`
- event: `workflow_dispatch`
- workflow head: `fc843a23246e6ee7134b14b3692376b875c5993c`
- result: **SUCCESS**
- rerun/retry: none

The temporary one-shot dispatcher was removed after the single authorized dispatch.

Current branch HEAD after dispatcher removal before this runtime documentation commit:

`86b2d9a01a42c1058fbd30fc268e63639a0e2465`

Current ARM64 authorization after this completed attempt:

**NONE**

## Runtime identity

User runtime log:

`eden_log(20260901-134628).txt`

Confirmed:

- Eden: `HEAD-dc95cd09ee-HEAD`
- TOTK: `1.2.1`
- title ID: `0100F2C0115B6000`
- CPU backend: Dynarmic
- Vulkan
- GPU: Qualcomm Adreno X1-85
- driver: `512.863.0`
- exact main build ID: `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- runtime main base in this run: `0x8053c000`
- runtime main size: `0x472b000`

Durable address knowledge remains ASLR-normalized `main+offset` only.

## Instrumentation semantics

`[X1-XEXCL]` records selected producer exclusive-write operations at the Dynarmic ARM64 `DoExclusiveOperation(...)` result point.

Per 120-frame window it records:

- attempts
- success
- fail
- cumulative callback time (`callbackNs`)
- average callback time (`callbackAvgNs`)
- maximum callback time
- size split for 8/16/32/64/128-bit exclusive writes

This captures final STXR/exclusive-write result handling, including monitor-level failures that do not necessarily descend into the concrete `MemoryWriteExclusive*` callback.

It does **not** measure the exclusive-read/LDXR `ReadAndMark(...)` path.

## Key runtime observations

### Frame 480

Producer 0:

- attempts `177,723`
- fail `112`
- failure rate `0.063%`
- callback time `21.333 ms`
- callback average `120 ns`

Producer 1:

- attempts `152,195`
- fail `121`
- failure rate `0.080%`
- callback time `18.174 ms`
- callback average `119 ns`

### Frame 720 — swap2 region

Producer 0:

- attempts `224,705`
- fail `583`
- failure rate `0.259%`
- callback time `27.302 ms`
- callback average `121 ns`
- producer CPU wall `661.601 ms`
- measured STXR callback share of producer CPU wall: `4.13%`

Producer 1:

- attempts `230,187`
- fail `472`
- failure rate `0.205%`
- callback time `28.579 ms`
- callback average `124 ns`
- producer CPU wall `662.974 ms`
- measured STXR callback share: `4.31%`

### Frame 840

Producer 0:

- attempts `265,233`
- fail `1,060`
- failure rate `0.400%`
- callback time `35.209 ms`
- callback average `132 ns`
- producer CPU wall `714.931 ms`
- measured STXR callback share: `4.92%`

Producer 1:

- attempts `274,068`
- fail `933`
- failure rate `0.340%`
- callback time `35.503 ms`
- callback average `129 ns`
- producer CPU wall `732.113 ms`
- measured STXR callback share: `4.85%`

### Frame 960

Producer 0:

- attempts `587,330`
- fail `2,435`
- failure rate `0.415%`
- callback time `69.758 ms`
- callback average `118 ns`
- producer CPU wall `2,394.147 ms`
- measured STXR callback share: `2.91%`

Producer 1:

- attempts `727,576`
- fail `1,412`
- failure rate `0.194%`
- callback time `82.004 ms`
- callback average `112 ns`
- producer CPU wall `2,410.243 ms`
- measured STXR callback share: `3.40%`

### Frame 1080

Producer 0:

- attempts `812,590`
- fail `4,157`
- failure rate `0.512%`
- callback time `96.530 ms`
- callback average `118 ns`
- producer CPU wall `2,493.829 ms`
- measured STXR callback share: `3.87%`

Producer 1:

- attempts `659,360`
- fail `1,836`
- failure rate `0.278%`
- callback time `83.974 ms`
- callback average `127 ns`
- producer CPU wall `2,307.745 ms`
- measured STXR callback share: `3.64%`

### Frame 1200 — swap3 observed at endpoint and from frame 1101

Producer 0:

- attempts `850,963`
- fail `3,889`
- failure rate `0.457%`
- callback time `99.204 ms`
- callback average `116 ns`
- producer CPU wall `2,482.943 ms`
- measured STXR callback share: `4.00%`

Producer 1:

- attempts `659,781`
- fail `1,949`
- failure rate `0.295%`
- callback time `82.208 ms`
- callback average `124 ns`
- producer CPU wall `2,243.910 ms`
- measured STXR callback share: `3.66%`

## Main interpretation

### 1. STXR retry/contention storm — REJECTED as primary explanation

Failure rate remains below about `0.52%` in the observed heavy windows.

There is no orders-of-magnitude failure explosion and no evidence of a retry storm sufficient to explain the producer CPU growth.

Most failures are in the 32-bit exclusive-write class; 64-bit failures are negligible.

### 2. Per-call STXR callback slowdown — REJECTED

`callbackAvgNs` stays approximately `112-132 ns` across light and heavy windows.

The heavy phase does not make one STXR callback intrinsically slower.

### 3. Direct measured STXR callback time — material but not dominant

Measured callback time is roughly `3-5%` of selected-producer CPU wall in the compared windows.

That is too small to directly explain the roughly multi-fold producer CPU expansion by itself.

Therefore the measured exclusive-write callback body is not the missing dominant CPU owner.

### 4. Exclusive-write operation volume tracks producer CPU growth strongly

From frame 720 to 1080:

Producer 0:

- attempts: `224,705 -> 812,590` = `3.62x`
- CPU wall: `661.601 -> 2,493.829 ms` = `3.77x`

Producer 1:

- attempts: `230,187 -> 659,360` = `2.86x`
- CPU wall: `662.974 -> 2,307.745 ms` = `3.48x`

Thus exclusive-write frequency rises with the same producer CPU expansion, even though contention and per-call callback cost do not.

This makes the exclusive path a strong **workload marker/component**, but does not prove the measured STXR callback is causal.

## Important remaining blind spot

The current experiment intentionally measured only the exclusive-write/STXR side.

Dynarmic ARM64 has a dedicated exclusive-read trampoline:

`EmitExclusiveReadCallTrampoline(...)`

which executes:

`global_monitor->ReadAndMark<T>(...)`

This LDXR/exclusive-read side is not included in `callbackNs` above.

Therefore this runtime result closes only:

- STXR retry storm
- STXR per-call slowdown
- direct STXR callback body as dominant owner

It does **not** close the total LDXR/STXR exclusive sequence, `ReadAndMark`, or other guest work surrounding the atomics.

## Cadence note for this run

Do not blindly reuse the exact fast/slow frame numbers from the previous x26 log.

In this runtime:

- swap2 is explicitly observed around frame 720/744 and earlier;
- swap3 is explicitly observed by frame 1101 and at frames 1199/1200.

The log ends around frame 1200 and does not provide the previous run's frame 1320/1440/1560 windows.

Interpret this run by its actual cadence evidence rather than importing frame labels from another run.

## Next experimental frontier

If a new Windows ARM64 experiment is explicitly authorized, the minimal next observation should be:

**selected-producer exclusive-read/LDXR `ReadAndMark` attribution**

using the existing `EmitExclusiveReadCallTrampoline(...)` path.

Record, at minimum, for the same two selected producers and same 120-frame windows:

- exclusive-read attempts by size
- cumulative `ReadAndMark` time
- average/max `ReadAndMark` time

Then correlate `LDXR + STXR` measured time against producer CPU wall and actual swap2/swap3 cadence.

Do not change guest atomic semantics, global-monitor behavior, CPU accuracy settings, scheduler behavior, GPU behavior, or cadence as part of that observation.

Current ARM64 authorization remains:

**NONE**
