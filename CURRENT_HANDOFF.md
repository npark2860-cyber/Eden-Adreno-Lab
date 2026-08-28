# CURRENT HANDOFF — Eden Adreno X1 Address Arbiter Signal Owner

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-address-arbiter-attribution`
- corrected AddressArbiter profiler source commit: `0d09c314b1aec644624996f1ca800a10e93c9fa4`
- corrected ARM64 build HEAD: `ead9a3954f9420334db5a3eef3635dd44d2eb4bd`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Corrected Address Arbiter build

- run `33160735717`
- job `98814297150`
- attempt `1`
- build HEAD `ead9a3954f9420334db5a3eef3635dd44d2eb4bd`
- conclusion `success`
- artifact `Eden-dc95-X1-address-arbiter-attribution`
- artifact id `9682219626`
- size `31,374,714` bytes
- SHA-256 `f7c28710ec6da63534cb40c285a7b3e03ba8ae4e848cd3144dfc1b5407cb750e`

No rerun was performed.

Persistent workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

must remain `workflow_dispatch` only.

## Closed / retained causal facts

### Draw / texture / alias

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication.
- blind alias dedupe / required outside-RP CopyImage removal remains rejected.

### Uniform

- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant gameplay Uniform path is mapped adaptive fast stream.
- tracked payload fingerprint is about 97.65% same payload.
- blind reuse is invalid because lifetime/in-flight/descriptor identity still matter.
- wholesale classic-cache fallback A/B did not break the gameplay ceiling.

### Cadence / swap / DFPS

- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; raw swap3 ~= nominal 20-FPS opportunity.
- VI ~= 60 Hz.
- raw swap interval originates from guest QueueBuffer input.
- raw3->effective2 HWC clamp did not increase upstream frame generation.
- DFPS ON/OFF can both remain ~20-FPS class.
- cadence/swap3 are downstream symptoms, not the root frame-production cause.

### BufferQueue

Slow gameplay:

- Queue -> Dequeue ~0.16 ms
- Dequeue total ~0.05 ms
- free-slot wait ~0.001 ms
- Dequeue END -> next Queue ~45-47 ms

Conclusion: BufferQueue free-slot/backpressure is closed as primary owner.

### Frame Build / GPU worker

- slow gameplay is roughly 48-55 ms/frame while measured RasterizerVulkan scopes explain only a minority;
- GPU worker spends most slow wall time in `PopWait/queueWait`;
- DmaPusher active work is material but does not own the missing interval;
- `PushCommand` is tiny and synchronous `blockWait=0`.

Conclusion: GPU worker is starved waiting for upstream command supply.

### GPU Submit / NVDRV / guest submitter

- long inter-submit gap exists before NVDRV handler entry;
- handler body / SubmitGPFIFOImpl / locks / copy/read/fence/syncpoint are tiny;
- dominant guest submitter = `tid=0x53`, essentially 100% candidate submits;
- priority 30, current/active core 1;
- CPU share remains about 1-2% in slow gameplay;
- NVDRV IPC dispatch remains roughly 0.02-0.03 ms/request.

Conclusion: missing C -> next-submit interval is not CPU-bound guest work and not Windows ARM64 nvservices dispatch latency.

### Guest Post Wait

- C -> next candidate interval is generally 96-99% KThread `Waiting`;
- `Arbitration` reason maps specifically to AddressArbiter `WaitForAddress`;
- `arbN ~= 120` per 120 rendered frames in steady gameplay;
- reason classification timing is valid;
- sampled `current_svc_id` is not populated in exact dc95, so old `topSvc0=0x0` output is unusable.

## Address Arbiter Stage A — COMPLETE

Corrected runtime:

`eden_log(20260828-102127).txt`

Environment:

- exact dc95 / TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- raw swap3->effective2 clamp OFF
- Address Arbiter / Guest Post Wait / NVDRV IPC Dispatch / Guest Submit / GPU Submit / GPU Command / Frame Build / Dequeue / Cadence ON

The corrected startup-warmup design worked. Post-warmup direct reports have:

- exactly one active `(address,type)` slot;
- `overflow=0` in every report;
- no target-thread switch;
- no alternate gameplay key.

Proven gameplay key:

- guest address: **`0x210adbc120`**
- operation: **`WaitIfEqual`** (`ArbitrationType=2`)
- timeout: **`-1`**
- result: successful wake completions; timeout count `0`, other-result count `0`
- caller/target: dominant submitter `tid=0x53`

Calls may appear as 119/120/121 because a synchronous wait can cross the 120-frame reporting boundary. Completed waits remain approximately one per rendered frame and the key does not change.

### Direct timing owns the Arbitration bucket

Representative direct `WaitForAddress` totals versus `[X1-GUESTWAIT] Arbitration` totals:

- frame 240: `1800.106 ms` vs `1799.392 ms`
- frame 840: `123.243 ms` vs `122.700 ms`
- frame 1080: `7406.971 ms` vs `7392.920 ms`
- frame 1440: `4819.116 ms` vs `4818.364 ms`

Across all post-warmup reports the correlation is approximately `0.999999`; largest observed mismatch is about `0.117 ms/frame`.

Therefore:

> The observed reason-level Arbitration bucket is effectively the synchronous duration of one stable `WaitForAddress(0x210adbc120, WaitIfEqual, timeout=-1)` operation on `tid=0x53`.

### Fast -> slow relationship

Representative direct wait averages:

- frame 840: `1.027 ms`, raw swap2 `120/120`
- frame 960: `3.601 ms`, mostly swap2 (`111/120`)
- frame 1080: `61.725 ms`, transition with swap3 majority (`73/120`)
- frame 1200: `45.593 ms`, raw swap3 `120/120`
- frame 1320: `41.227 ms`, raw swap3 `120/120`
- frame 1440: `40.159 ms`, raw swap3 `120/120`

Frame 360 is another transient: direct wait `37.227 ms` with mixed cadence (`94x swap2 / 26x swap3`).

The same exact wait key persists from fast through transition into stable slow state. Its duration expands strongly before/with the raw-swap-3 regime.

## Exact dc95 interpretation

Path:

`Svc::WaitForAddress`
-> `WaitAddressArbiter`
-> `KAddressArbiter::WaitIfEqual`
-> `BeginWait`
-> wait reason `Arbitration`.

`WaitIfEqual` blocks when the 32-bit value at the supplied guest address equals the expected value. The observed timeout is `-1`; runtime has no timeout completions.

Wake side:

`Svc::SignalToAddress`
-> `SignalAddressArbiter`.

Thus the blocked synchronization object/key is identified, but the producer/waker is not.

## Correct current causal statement

> The dominant GPU submitter is delayed by a stable once-per-frame guest AddressArbiter wait at `0x210adbc120`, using `WaitIfEqual` with indefinite timeout. The direct duration of this one wait explains essentially the entire Arbitration bucket and expands from low single-/teens-ms in fast windows to roughly 40-62 ms in the slow regime. The remaining causal question is which guest producer thread signals this address late and why.

Do **not** say the final root cause is solved until the signal/waker owner is identified.

## Current next action — Stage B

Read:

- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_CORRECTED.md`
- `NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md`

Instrument only the wake side for exact address `0x210adbc120`:

- signaling guest thread ID
- signal type/count
- cheap/read-only relevant value if useful
- signal timing
- enough correlation to connect the signal to completion of target `tid=0x53`'s `WaitIfEqual`

Do not trace all `SignalToAddress` calls.

Do not add scheduler tracing.

Do not add a generic all-SVC profiler.

Do not change wait/signal semantics.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.