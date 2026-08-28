# NEXT ACTION — X1 Address Arbiter Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- current lab branch: `exp/x1-guest-post-wait-attribution`
- experiment cleanup/code anchor: `d9df8d7f594c3030ee518a2bd489a15708ad87b4`

Never change the Eden baseline without explicit baseline-change approval.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Why this is the next boundary

Completed Guest Post Wait runtime `eden_log(20260828-080040).txt` established:

1. dominant submitter remains `tid=0x53`, essentially 100% candidate submits, CPU share ~1-2%;
2. C -> next candidate request window is ~96-99% KThread Waiting in steady reports;
3. `Arbitration` wait is exactly `arbN=120` per 120 rendered frames;
4. exact dc95 maps `Arbitration` reason specifically to AddressArbiter `WaitForAddress`, not mutex/process-wide condition-variable waits;
5. Arbitration time is ~1-2.6 ms/frame in fast windows, then can rise to ~23.8, ~57.5, ~26.8 or ~50.1 ms/frame in slow/transition windows;
6. however stable-slow frame 1320 is dominated by `None` wait (`40.741 ms/frame`) while Arbitration is only `8.615 ms/frame`.

Therefore the next question is deliberately narrow:

> Is the once-per-frame AddressArbiter wait one stable `WaitForAddress` object, and does its actual blocked duration track the fast -> transition -> slow change strongly enough to own a causal part of the slowdown?

Do not claim the entire slowdown is AddressArbiter-owned yet.

## Known profiler defect to bypass

Current `[X1-GUESTWAIT] topSvc*` output is unusable for SVC attribution because exact dc95 does not populate `KThread::StackParameters::current_svc_id`; the existing transplant added no SVC-ID recorder.

Do not repair this by adding a broad all-SVC recorder. Directly instrument `Svc::WaitForAddress` instead.

## Stage A — minimal direct WaitForAddress attribution

Observation-only target:

`src/core/hle/kernel/svc/svc_address_arbiter.cpp`

Track only calls belonging to the dynamic dominant submitter and only while the existing guest-post window is relevant.

Required aggregate fields per 120 rendered frames:

- guest `tid`
- guest address
- `ArbitrationType`
  - `WaitIfLessThan`
  - `DecrementAndWaitIfLessThan`
  - `WaitIfEqual`
- timeout argument
- calls / completed waits
- total blocked duration
- average blocked duration
- max blocked duration
- return status / timeout count if available without changing call semantics

Preferred aggregation key:

`(address, ArbitrationType)`

No per-event line logging.

No generic SVC profiler.

No scheduler tracing.

No new waits/sleeps/locks on the guest path.

## Measurement requirement

Use the same existing post-submit target identity and compare with the existing aggregates in the same 120-frame report cadence.

The new direct aggregate must let us compare, in one runtime:

- fast raw-swap-2 windows
- transition window(s)
- stable slow raw-swap-3 windows

For each phase answer:

- does one address dominate count and duration?
- is it exactly one blocked WaitForAddress per rendered frame?
- which ArbitrationType is used?
- does its duration explain the previously reported Arbitration bucket?
- does its duration expand before/with slowdown?

## Stage B — only if Stage A proves a dominant address

Do not implement in the first pass unless source-only wiring requires no additional runtime cost.

For the single proven dominant address only, instrument `Svc::SignalToAddress` / `KAddressArbiter` wake side to identify:

- signaling guest thread ID
- signal type/count
- signal-to-wake timing needed to identify the producer/waker relationship

Do not trace all SignalToAddress traffic.

## Separate fallback for `None`

If Stage A cleanly explains the AddressArbiter bucket but a frame-1320-like stable-slow window still spends most time in `None`:

- do not broaden to scheduler profiling;
- add a separate minimal source tag only for Waiting paths whose debug reason remains `None` for target `tid=0x53`;
- identify the unclassified `BeginWait` call-site class before any deeper instrumentation.

This fallback is not part of Stage A unless required by static source review.

## Safety invariants

Must not change:

- Eden baseline
- scheduling/priority/core affinity
- KThread wait semantics
- address-arbiter comparison/update semantics
- timeout semantics
- signal/wake semantics
- NVDRV submission behavior
- GPU worker behavior
- BufferQueue/HWC/VI/cadence
- swap interval or frame target
- any previous profiler behavior except minimal read-only integration required for target/window identity

Default OFF for any new setting.

## Build state

Source/runtime design only.

No ARM64 build is authorized.

Before any future ARM64 attempt:

1. prepare source/transplant/workflow changes;
2. statically verify exact dc95 anchors and unchanged behavioral paths;
3. verify persistent workflow remains `workflow_dispatch` only;
4. stop and request fresh explicit authorization for exactly one ARM64 attempt.