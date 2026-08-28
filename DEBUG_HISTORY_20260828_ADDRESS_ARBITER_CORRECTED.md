# DEBUG HISTORY — 2026-08-28 Corrected Address Arbiter Stage A

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- experiment branch: `exp/x1-address-arbiter-attribution`
- corrected profiler source commit: `0d09c314b1aec644624996f1ca800a10e93c9fa4`
- corrected build trigger/build HEAD: `ead9a3954f9420334db5a3eef3635dd44d2eb4bd`

The Eden baseline remains immutable.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Corrected ARM64 build

Approved single attempt:

- run `33160735717`
- job `98814297150`
- attempt `1`
- build HEAD `ead9a3954f9420334db5a3eef3635dd44d2eb4bd`
- conclusion `success`
- artifact `Eden-dc95-X1-address-arbiter-attribution`
- artifact id `9682219626`
- artifact size `31,374,714` bytes
- SHA-256 `f7c28710ec6da63534cb40c285a7b3e03ba8ae4e848cd3144dfc1b5407cb750e`

No rerun was performed.

## Runtime

Log:

`eden_log(20260828-102127).txt`

Environment:

- exact dc95 / TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- raw swap3->effective2 clamp OFF
- Address Arbiter / Guest Post Wait / NVDRV IPC Dispatch / Guest Submit / GPU Submit / GPU Command / Frame Build / Dequeue / Cadence ON
- Descriptor Ring was also ON; prior sampled DBUF data was inert and nothing in this runtime indicates it owns the measured wait.

## Stage A corrected direct result

The startup-slot correction worked.

Frame 120 is intentionally warmup-only for direct address collection. From frame 240 onward every direct AddressArbiter report collapses to one key:

- guest address: `0x210adbc120`
- arbitration type: `WaitIfEqual` (`equal`, type 2)
- timeout: `-1`
- active slots: `1`
- overflow: `0`
- target thread switches: `0`
- return status: successful completions only; timeout count `0`, other-result count `0`

No alternate gameplay address/type appears in any post-warmup 120-frame report.

Calls can be 119/120/121 at report boundaries because one synchronous call may cross the reporting cut; completions close at approximately 120 per window and the key remains unchanged.

## Direct WaitForAddress table

| frame | calls | done | total ms | avg ms | max ms | address | type | timeout | overflow |
|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| 240 | 120 | 119 | 1800.106 | 15.127 | 32.090 | `0x210adbc120` | equal | -1 | 0 |
| 360 | 119 | 120 | 4467.210 | 37.227 | 131.353 | same | equal | -1 | 0 |
| 480 | 121 | 120 | 1723.315 | 14.361 | 62.061 | same | equal | -1 | 0 |
| 600 | 120 | 120 | 1790.420 | 14.920 | 27.053 | same | equal | -1 | 0 |
| 720 | 120 | 120 | 1639.121 | 13.659 | 23.613 | same | equal | -1 | 0 |
| 840 | 120 | 120 | 123.243 | 1.027 | 8.231 | same | equal | -1 | 0 |
| 960 | 120 | 120 | 432.149 | 3.601 | 69.922 | same | equal | -1 | 0 |
| 1080 | 121 | 120 | 7406.971 | 61.725 | 591.605 | same | equal | -1 | 0 |
| 1200 | 119 | 120 | 5471.183 | 45.593 | 80.726 | same | equal | -1 | 0 |
| 1320 | 120 | 120 | 4947.259 | 41.227 | 79.765 | same | equal | -1 | 0 |
| 1440 | 121 | 120 | 4819.116 | 40.159 | 83.820 | same | equal | -1 | 0 |

## Reconciliation with Guest Post Wait Arbitration bucket

The direct `Svc::WaitForAddress` duration matches the existing `[X1-GUESTWAIT] Arbitration` duration essentially one-for-one in every post-warmup report.

Examples:

- frame 240: direct `1800.106 ms`, Arbitration `1799.392 ms`
- frame 840: direct `123.243 ms`, Arbitration `122.700 ms`
- frame 1080: direct `7406.971 ms`, Arbitration `7392.920 ms`
- frame 1440: direct `4819.116 ms`, Arbitration `4818.364 ms`

Across the post-warmup reports the correlation is approximately `0.999999`. Largest observed total difference is about `14 ms` over 120 rendered frames (~`0.117 ms/frame`).

Therefore:

> The previously measured Arbitration bucket is effectively the synchronous duration of one stable `WaitForAddress(0x210adbc120, WaitIfEqual, timeout=-1)` key on the dominant submitter.

## Fast -> transition -> slow relationship

Representative direct wait averages and cadence:

- frame 840: `1.027 ms`, raw swap2 `120/120`
- frame 960: `3.601 ms`, raw swap2 `111/120`, swap3 `9/120`
- frame 1080: `61.725 ms`, swap2 `47/120`, swap3 `73/120`
- frame 1200: `45.593 ms`, raw swap3 `120/120`
- frame 1320: `41.227 ms`, raw swap3 `120/120`
- frame 1440: `40.159 ms`, raw swap3 `120/120`

Another transient exists at frame 360: direct wait `37.227 ms` while cadence is already mixed (`94x swap2 / 26x swap3`).

The wait expansion is upstream of the final raw-swap-3 classification and strongly tracks the slow regime.

## Exact dc95 semantic interpretation

Exact dc95 maps this runtime key through:

`Svc::WaitForAddress`
-> `WaitAddressArbiter`
-> `KAddressArbiter::WaitIfEqual`
-> thread enters `Waiting` with debug reason `Arbitration`.

`WaitIfEqual` blocks when the 32-bit value at the supplied guest address equals the expected value. Runtime timeout is `-1`; the direct profiler records no timeout exits. Therefore this is not a timeout-driven delay.

Wake side is `Svc::SignalToAddress` -> `SignalAddressArbiter`.

## Stage A conclusion

Stage A is **complete**.

Confirmed:

1. dominant submitter remains `tid=0x53`;
2. there is one stable gameplay AddressArbiter key;
3. key = `0x210adbc120 / WaitIfEqual / timeout -1`;
4. it completes approximately once per rendered frame modulo report-boundary carry;
5. its direct duration explains essentially the entire prior Arbitration bucket;
6. the same key persists through fast swap2, transition, and stable swap3 states;
7. its wait duration expands from low single-/teens-ms in fast windows to roughly 40-62 ms in the stable/transition slow regime.

Not yet known:

- which guest thread signals `0x210adbc120`;
- signal type/count/value behavior;
- why that producer/waker is late on the Snapdragon X / Adreno path;
- whether the final fix belongs in emulation scheduling, guest-visible synchronization timing, or an upstream producer path.

Do **not** state that the final root cause is solved yet. The blocked synchronization object is now identified; the producer/waker owner is not.

## Next boundary — Stage B signal owner

Instrument only `SignalToAddress` operations for exact guest address `0x210adbc120`.

Required aggregate fields:

- signaling guest thread ID
- signal type
- signal count
- cheap/read-only relevant value if available
- signal call timing
- enough timing correlation to relate signal to completion of the target `WaitIfEqual`

Constraints:

- exact address only; no generic SignalToAddress profiler
- no per-event log flood
- no scheduler tracing
- no new waits/sleeps/locks
- no change to signal/wake semantics
- default OFF or gated by the existing AddressArbiter diagnostic setting
- no ARM64 build without fresh explicit authorization.
