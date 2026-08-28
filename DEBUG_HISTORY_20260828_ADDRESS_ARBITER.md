# DEBUG HISTORY — 2026-08-28 Address Arbiter Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- experiment branch: `exp/x1-address-arbiter-attribution`
- first built code HEAD: `f2b1b6fed220597124274e873523a515e594c09a`
- corrected profiler source HEAD after runtime review: `0d09c314b1aec644624996f1ca800a10e93c9fa4`

The Eden baseline remains immutable.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## First Address Arbiter build

Approved ARM64 attempt:

- run `33156864030`
- job `98801611676`
- attempt `1`
- build HEAD `f2b1b6fed220597124274e873523a515e594c09a`
- conclusion `success`
- artifact `Eden-dc95-X1-address-arbiter-attribution`
- artifact id `9680703932`
- artifact size `31,372,998` bytes
- SHA-256 `7ceef9df425fae50845aa2f63183e40a2d91d2c6205af8e62151e16dbadc9527`

A preliminary Ubuntu dispatcher run `33156730741` failed with HTTP 404 before any ARM64 job was started because GitHub could not dispatch a workflow file that existed only on the experiment branch. It is not counted as an ARM64 attempt.

No rerun was performed.

## Runtime

Log:

`eden_log(20260828-093056).txt`

Environment from the runtime log:

- exact dc95
- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- swap3->2 clamp OFF
- Address Arbiter / Guest Post Wait / NVDRV IPC Dispatch / Guest Submit / GPU Submit / GPU Command / Frame Build / Dequeue / Cadence ON
- Descriptor Ring remained ON, but reports again showed `alloc=0`, `reuseWait=0`; this is not a rerun reason.

## Valid runtime result retained from Guest Post Wait

The direct Address Arbiter address table is defective in this build, but the existing `[X1-GUESTWAIT]` reason-level data is independent of that defect and remains valid.

All totals below are normalized by 120 rendered frames except profiler per-request averages.

| frame | wall/f ms | windowAvg ms | waitShare | residual/f ms | None/f ms | Arbitration/f ms | arbN | guestPostAvg ms | ipcDispatchAvg ms | GPU queueWait/f ms | GPU active/f ms | raw swap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 120 | 111.236 | 36.275 | 64.26% | 26.256 | 33.608 | 13.144 | 1098 | 20.471 | 0.023 | 95.858 | 6.924 | startup/mixed |
| 240 | 39.438 | 19.763 | 97.88% | 0.832 | 29.381 | 8.981 | 119 | 19.703 | 0.060 | 34.768 | 4.674 | mostly 2 |
| 360 | 48.331 | 24.096 | 98.44% | 0.750 | 30.096 | 17.347 | 120 | 24.065 | 0.032 | 44.628 | 3.703 | mixed, mostly 2 |
| 480 | 33.611 | 16.788 | 97.24% | 0.926 | 30.784 | 1.866 | 120 | 16.756 | 0.032 | 32.372 | 1.237 | 2 |
| 600 | 34.722 | 17.348 | 98.04% | 0.679 | 31.947 | 2.067 | 120 | 17.329 | 0.019 | 34.192 | 0.529 | mostly 2 |
| 720 | 34.445 | 17.200 | 96.69% | 1.140 | 31.122 | 2.137 | 120 | 17.178 | 0.022 | 33.885 | 0.560 | 2 |
| 840 | 33.335 | 16.651 | 98.44% | 0.520 | 31.861 | 0.921 | 120 | 16.637 | 0.014 | 32.783 | 0.551 | 2 |
| 960 | 75.725 | 37.731 | 98.58% | 1.076 | 15.712 | 58.989 | 120 | 37.694 | 0.038 | 60.262 | 15.461 | 60x2 / 60x3 |
| 1080 | 54.263 | 26.869 | 98.19% | 0.982 | 17.107 | 36.097 | 120 | 26.845 | 0.024 | 36.430 | 17.831 | 3 |
| 1200 | 53.495 | 26.700 | 97.96% | 1.087 | 18.217 | 34.097 | 120 | 26.675 | 0.025 | 33.131 | 20.364 | 3 |
| 1320 | 55.733 | 27.726 | 98.24% | 0.979 | 10.866 | 43.838 | 120 | 27.701 | 0.025 | 37.691 | 18.041 | 3 |
| 1440 | 54.170 | 26.729 | 98.23% | 0.960 | 10.229 | 42.938 | 120 | 26.700 | 0.029 | 36.001 | 18.166 | 3 |

Raw QueueBuffer cadence counts by 120-frame window:

- frame 480: 120x swap2
- frame 720: 120x swap2
- frame 840: 120x swap2
- frame 960: 60x swap2 + 60x swap3
- frame 1080/1200/1320/1440: 120x swap3 each

### Stronger correlation in this runtime

Steady fast raw-swap-2 windows 480-840:

- Arbitration roughly `0.921-2.137 ms/frame`
- Arbitration share of tracked Waiting roughly `2.8-6.4%`
- `windowAvg` roughly `16.65-17.35 ms`

Transition frame 960:

- raw swap evenly changes from 2 to 3
- `windowAvg=37.731 ms`
- `Arbitration=58.989 ms/frame`
- Arbitration share of tracked Waiting about `79%`

Stable raw-swap-3 windows 1080-1440:

- `windowAvg=26.7-27.7 ms`
- `Arbitration=34.1-43.8 ms/frame`
- Arbitration share of tracked Waiting about `65-81%`
- submitter CPU share remains about `1-2%`
- IPC dispatch remains about `0.02-0.03 ms/request`

The previous runtime's frame-1320 counterexample, where stable slow was dominated by `None`, did not reproduce here. In this runtime stable-slow frame 1320 and 1440 are both Arbitration-dominant.

This strengthens, but does not finish, the causal case:

> The slow raw-swap-3 regime is repeatedly accompanied by a large once-per-frame AddressArbiter wait. The relation is upstream of raw cadence and cannot be explained by CPU-bound submit work or NVDRV dispatch.

Do not yet claim the logical synchronization object or waking producer is known.

## First direct Address Arbiter result — invalid for gameplay identity

`[X1-ADDRARB]` frame 120:

- `slots=8`
- `calls=8`
- `done=8`
- `overflow=1090`
- the four displayed captured startup calls were `WaitIfEqual`, timeout `-1`, success

Every later gameplay report is effectively empty:

- frame 240: `calls=0`, `overflow=120`
- frame 360: `calls=0`, `overflow=120`
- frame 480: `calls=0`, `overflow=120`
- frame 720: `calls=0`, `overflow=121`
- frame 960: `calls=0`, `overflow=121`
- frame 1080/1200/1320/1440: `calls=0`, `overflow=120`

This does **not** mean no WaitForAddress calls occurred. Existing Guest Post Wait simultaneously records `arbN ~= 120` per gameplay report.

### Root cause of the direct-profiler failure

Built profiler `f2b1b6f...` uses a fixed 8-slot `(address, ArbitrationType)` table.

`FrameEnd()` resets per-window counters with `exchange(0)` but does not clear each slot's `address_key`.

Therefore:

1. startup produces 1098 AddressArbiter waits in the first 120-frame report;
2. the first eight distinct `(address,type)` keys permanently claim all eight slots;
3. later gameplay calls use different addresses and are rejected by `FindOrClaimSlot()`;
4. those calls increment only `slot_overflow` and lose address/type/duration data.

The persistent `top0..top3` addresses in later zero-call reports are stale startup keys and must not be interpreted as gameplay addresses.

Thus the first Stage A runtime cannot answer:

- gameplay guest address
- gameplay ArbitrationType
- gameplay timeout
- direct WaitForAddress duration by address

## Minimal correction prepared

Profiler source was corrected at:

`0d09c314b1aec644624996f1ca800a10e93c9fa4`

Diff versus the built source is only `src/core/x1_address_arbiter_profiler.h`, 8 additions / 1 deletion.

Correction:

- Address Arbiter collection is disarmed for the first 120 rendered frames;
- the first report is treated as startup warmup;
- collection arms only after that report;
- slots are explicitly cleared on profiler initialization;
- slot count remains 8;
- no new lock/wait/sleep/scheduler/GPU policy is added.

Reason for not expanding the table:

The next question is still narrow. If gameplay uses one stable address, the first post-warmup slot will retain and count it across all later windows. If gameplay cycles through more than eight address/type keys, overflow after warmup is itself evidence that the synchronization address is not a single stable object and can guide the next minimal refinement.

## Current conclusion

Confirmed:

- guest-post delay is still KThread Waiting dominated;
- AddressArbiter remains exactly once per rendered frame in steady gameplay;
- this runtime shows a much stronger slow-regime Arbitration correlation than the previous runtime;
- first direct address/type profiler runtime is invalid for gameplay identity because startup permanently occupied the fixed slots.

Not confirmed:

- which gameplay address owns the once/frame wait;
- whether the address is stable or rotates;
- exact gameplay ArbitrationType/timeout;
- which guest thread or object signals/wakes it;
- whether AddressArbiter alone explains every slow window across repeated runs.

## Next action

Use the corrected post-warmup profiler source only after a fresh explicit ARM64 authorization.

Do not add Stage B signal tracing yet.

Do not add broad scheduler/SVC tracing.

No ARM64 build is currently authorized.