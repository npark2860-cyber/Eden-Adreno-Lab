# NEXT ACTION — X1 Address Arbiter Signal Owner (Stage B)

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- branch: `exp/x1-address-arbiter-attribution`
- corrected Stage A source: `0d09c314b1aec644624996f1ca800a10e93c9fa4`
- corrected ARM64 build HEAD: `ead9a3954f9420334db5a3eef3635dd44d2eb4bd`

Never change the Eden baseline without explicit baseline-change approval.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Stage A is complete

Corrected runtime:

`eden_log(20260828-102127).txt`

Direct `Svc::WaitForAddress` attribution proves one stable gameplay key:

- target guest thread: `tid=0x53`
- guest address: **`0x210adbc120`**
- arbitration type: **`WaitIfEqual`** (`type=2`)
- timeout: **`-1`**
- post-warmup active slots: `1`
- post-warmup overflow: `0`
- timeout completions: `0`
- other-result completions: `0`

The key remains unchanged across fast swap2, transition, and stable swap3 windows.

Representative direct wait averages:

- frame 840: `1.027 ms`, swap2 `120/120`
- frame 960: `3.601 ms`, swap2 `111/120`
- frame 1080: `61.725 ms`, swap3 `73/120`
- frame 1200: `45.593 ms`, swap3 `120/120`
- frame 1320: `41.227 ms`, swap3 `120/120`
- frame 1440: `40.159 ms`, swap3 `120/120`

Direct WaitForAddress duration reconciles essentially exactly with the existing reason-level Arbitration bucket (correlation approximately `0.999999`).

Therefore the blocked synchronization object/key is known. Do not spend another experiment re-proving Stage A.

Full record:

`DEBUG_HISTORY_20260828_ADDRESS_ARBITER_CORRECTED.md`

## Exact next causal question

> Which guest thread signals `0x210adbc120`, and does delayed signaling explain the long `WaitIfEqual` duration on `tid=0x53`?

Exact dc95 wake path:

`Svc::SignalToAddress`
-> current process `SignalAddressArbiter`
-> `KAddressArbiter` wake handling.

## Stage B — exact-address signal attribution only

Instrument only `Svc::SignalToAddress` calls where:

`address == 0x210adbc120`

Required aggregate fields per 120 rendered frames:

- signaling guest thread ID
- `SignalType`
- count argument / effective signaled count if readily available
- cheap/read-only address value if it materially helps interpret signal semantics
- total calls by signaling thread/type
- signal timestamp distribution or enough timing information to connect signal occurrence to the target wait completion

Preferred first goal:

- determine whether one guest thread is the dominant/sole waker;
- determine whether there is approximately one relevant signal per rendered frame;
- determine whether long target waits end immediately after that signal;
- identify whether waker timing itself shifts from fast to slow regime.

## Correlation requirement

Keep the existing target `tid=0x53` and exact address fixed.

Compare the signal-side aggregate with the existing direct wait reports in the same 120-frame cadence:

- fast raw-swap-2 windows
- transition windows
- stable raw-swap-3 windows

The result must answer whether the long wait is caused by a late producer/waker versus some other AddressArbiter semantic condition.

## Scope constraints

Do **not**:

- trace all `SignalToAddress` traffic;
- add a generic SVC profiler;
- add broad scheduler tracing;
- add per-event logging flood;
- add waits/sleeps/locks;
- alter address values;
- alter `WaitIfEqual` comparison semantics;
- alter `SignalToAddress` type/count semantics;
- alter thread priority/core affinity;
- alter NVDRV/GPU/BufferQueue/HWC/VI/cadence/swap policy.

Observation-only, default OFF or gated by the existing Address Arbiter diagnostic control.

## Separate `None` fallback

Do not chase `None` now.

The corrected Stage A runtime cleanly identifies the entire Arbitration bucket. `None` remains a separate wait class and should only be revisited if a future controlled runtime demonstrates a stable-slow window where the proven AddressArbiter wait is small while `None` dominates.

## Build state

Stage B source has not been implemented or ARM64-built.

Current ARM64 authorization: **NONE**.

Before any Stage B ARM64 attempt:

1. implement only exact-address signal attribution;
2. statically verify exact dc95 signal/wait call counts and unchanged semantics;
3. verify persistent workflow remains `workflow_dispatch` only;
4. verify branch diff contains only intended Stage B instrumentation/workflow/docs changes;
5. request fresh explicit authorization for exactly one ARM64 attempt;
6. no automatic retry on failure.