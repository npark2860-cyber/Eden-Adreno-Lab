# DEBUG HISTORY — 2026-09-01 ARM64 Exclusive Read / LDXR Attribution Implemented

Updated: 2026-09-01 KST

## Scope

Observation-only implementation and Ubuntu/static validation.

No Windows ARM64 build/run was dispatched by this step.

Exact immutable Eden baseline remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch:

`exp/x1-arm64-exclusive-callback-attribution`

## Why this experiment exists

The preceding runtime experiment closed the measured STXR side as a primary dominant owner:

- STXR failure/retry rates stayed below about 0.52%;
- STXR callback average stayed about 112-132 ns;
- directly measured STXR callback time was only about 3-5% of selected-producer CPU wall;
- STXR volume still tracked producer CPU growth strongly.

The unmeasured half was exclusive-read / LDXR:

`EmitExclusiveReadCallTrampoline -> global_monitor->ReadAndMark<T>`

## Implementation

The existing profiler now retains the previous STXR fields and appends LDXR fields to the same `[X1-XEXCL]` 120-frame record.

New appended fields:

- `readAttempts`
- `readNs`
- `readAvgNs`
- `readMaxNs`
- `readBadSize`
- `rs8=<attempts>/<ns>`
- `rs16=<attempts>/<ns>`
- `rs32=<attempts>/<ns>`
- `rs64=<attempts>/<ns>`
- `rs128=<attempts>/<ns>`

Producer identity remains resolved once per `ArmDynarmic64::RunThread` slice using the existing Stage F selected-producer accessor. No producer lookup is added to each LDXR/STXR operation.

Dynarmic A64 receives no-op-by-default observation hooks for exclusive reads and writes. The ARM64 backend times only the existing `ReadAndMark<T/Vector>` and `DoExclusiveOperation<T/Vector>` calls for already-selected producers.

Guest-visible exclusive semantics are unchanged.

## Analyzer

`tools/adreno_lab/analyze_x1_arm64_exclusive_attribution.py` now accepts both:

- old STXR-only `[X1-XEXCL]` records;
- new combined LDXR+STXR records.

It reports LDXR and STXR attempts/window, average callback time, total callback time/window, and STXR failure rate.

## Exact dc95 static validation

Temporary validator run:

`33517281924`

Result:

**SUCCESS**

Validated on exact dc95 files:

- generic `ReadAndMark<T>` remains exactly once;
- 128-bit `ReadAndMark<Vector>` remains exactly once;
- generic `DoExclusiveOperation<T>` remains exactly once;
- 128-bit `DoExclusiveOperation<Vector>` remains exactly once;
- generic and 128-bit read observation hooks are each installed exactly once;
- generic and 128-bit write observation hooks remain exactly once;
- `RunThread` still contains exactly one `ClearExclusiveState()` and one `m_jit->Run()`;
- selected producer identity is resolved exactly once per RunThread;
- no scheduler/priority/affinity/yield/wait/signal/GPU/QueueBuffer/cadence behavior-changing token was introduced.

The temporary validator workflow was deleted immediately after success.

## Stop condition

Implementation is ready for one Windows ARM64 runtime experiment, but current Windows ARM64 authorization is **NONE**.

Do not dispatch, rebuild, rerun, or retry without a fresh explicit user authorization.
