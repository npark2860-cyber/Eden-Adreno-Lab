# CURRENT HANDOFF — Eden Adreno X1 Address Arbiter Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-address-arbiter-attribution`
- first built AddressArbiter code HEAD: `f2b1b6fed220597124274e873523a515e594c09a`
- corrected unbuilt AddressArbiter profiler code HEAD: `0d09c314b1aec644624996f1ca800a10e93c9fa4`

Documentation commits may advance branch HEAD beyond the corrected code commit. Use `0d09c314...` as the current source-code anchor unless a later source commit is explicitly recorded.

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Current workflow / build state

Persistent workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

is `workflow_dispatch` only.

Temporary branch-only workflows remain present but are path-scoped to their own workflow files, so source/document commits do not trigger them:

- `.github/workflows/one-shot-x1-address-arbiter-build.yml`
- `.github/workflows/one-shot-x1-address-arbiter-dispatch.yml`

Do not modify either temporary workflow without treating that modification as potentially trigger-capable.

Approved Address Arbiter ARM64 build:

- run `33156864030`
- job `98801611676`
- attempt `1`
- build HEAD `f2b1b6fed220597124274e873523a515e594c09a`
- conclusion `success`
- artifact `Eden-dc95-X1-address-arbiter-attribution`
- artifact id `9680703932`
- size `31,372,998` bytes
- SHA-256 `7ceef9df425fae50845aa2f63183e40a2d91d2c6205af8e62151e16dbadc9527`

A preliminary Ubuntu dispatcher run `33156730741` failed with HTTP 404 before any ARM64 job was started. It is not an ARM64 build attempt.

No rerun was performed.

## Closed / retained causal facts

### Draw / texture / alias

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication.
- trivial alias dedupe / removal of required outside-RP CopyImage remains rejected.

### Uniform

- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant gameplay Uniform path is mapped adaptive fast stream.
- tracked payload fingerprint: 97.65% same payload.
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

### Frame Build / GPU Command

- slow gameplay is roughly 48-55 ms/frame while measured RasterizerVulkan scopes explain only a minority;
- GPU worker spends most slow wall time in `PopWait/queueWait`;
- DmaPusher active work is material but does not own the missing interval;
- `PushCommand` is tiny and synchronous `blockWait=0`.

Conclusion: GPU worker is starved waiting for upstream command supply.

### GPU Submit Gap / NVDRV

Exact path:

`NVDRV Ioctl -> nvhost_gpu SubmitGPFIFO -> PushGPUEntries -> GPUThread SubmitList -> GPU worker`

NVDRV service-entry, device-submit and PushGPUEntries gaps match. Handler body / SubmitGPFIFOImpl / lock / copy/read/fence/syncpoint are tiny.

Conclusion: the long inter-submit gap exists before NVDRV handler entry.

### Guest Submit Thread / IPC dispatch

- dominant submitter = `tid=0x53`, essentially 100% candidate submits;
- priority 30, current/active core 1;
- CPU share remains about 1-2% in slow gameplay;
- NVDRV IPC dispatch is about 0.02-0.03 ms/request;
- service/reply is also tiny.

Conclusion: the missing C -> next-submit interval is not CPU-bound guest execution and not Windows ARM64 nvservices dispatch latency.

## Guest Post Wait result retained

Prior runtime `eden_log(20260828-080040).txt` established:

- C -> next candidate interval is generally 96-99% KThread Waiting;
- `Arbitration` maps exactly to AddressArbiter `WaitForAddress`, not generic mutex/CV waits;
- `arbN=120` in steady 120-frame reports = exactly one completed AddressArbiter wait per rendered frame;
- one prior stable-slow frame 1320 was `None`-dominated, so AddressArbiter alone was not yet proven across all samples.

Profiler source review also established:

- reason classification timing is valid;
- `topSvc0=0x0` is broken because exact dc95 never populates the sampled `current_svc_id` field;
- direct `WaitForAddress` instrumentation is preferable to a broad SVC recorder.

## Address Arbiter Stage A first runtime

Runtime:

`eden_log(20260828-093056).txt`

Environment:

- exact dc95 / TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Adreno X1-85, driver 512.863.0, Vulkan 1.3.295
- swap3->2 clamp OFF
- Address Arbiter / Guest Post Wait / NVDRV IPC Dispatch / Guest Submit / GPU Submit / GPU Command / Frame Build / Dequeue / Cadence ON
- Descriptor Ring still ON but sampled DBUF remained zero-cost (`alloc=0`, `reuseWait=0`).

### Valid causal data from this runtime

Steady fast raw-swap-2 windows:

- frame 480: `wall/f=33.611 ms`, `windowAvg=16.788 ms`, `Arbitration=1.866 ms/frame`
- frame 600: `34.722`, `17.348`, `2.067`
- frame 720: `34.445`, `17.200`, `2.137`
- frame 840: `33.335`, `16.651`, `0.921`

Transition:

- frame 960: raw QueueBuffer is exactly 60x swap2 + 60x swap3
- `wall/f=75.725 ms`
- `windowAvg=37.731 ms`
- `waitShare=98.58%`
- `Arbitration=58.989 ms/frame`
- `arbN=120`

Stable raw-swap-3:

- frame 1080: `wall/f=54.263`, `windowAvg=26.869`, `Arbitration=36.097 ms/frame`
- frame 1200: `53.495`, `26.700`, `34.097`
- frame 1320: `55.733`, `27.726`, `43.838`
- frame 1440: `54.170`, `26.729`, `42.938`

In these stable slow reports Arbitration is roughly 65-81% of tracked Waiting. The prior run's frame-1320 `None`-dominant counterexample did not reproduce.

Correct current causal statement:

> Guest-post slowdown remains KThread Waiting dominated. In this second runtime, the once-per-frame AddressArbiter wait becomes strongly dominant exactly across the raw-swap-3 slow regime, which materially strengthens the case that it owns a causal portion of the slowdown. The logical wait object/waker is still unknown.

Do not yet state that one specific guest synchronization object is the root cause.

## Direct `[X1-ADDRARB]` first-runtime defect

The first direct address/type table is invalid for gameplay identity.

Frame 120 startup:

- `slots=8`
- `calls=8`
- `done=8`
- `overflow=1090`

Later gameplay:

- frame 240 onward: `calls=0`
- `overflow ~= 119-121` per 120-frame report

Simultaneously `[X1-GUESTWAIT]` reports `arbN ~= 120`, proving the WaitForAddress events still occur and the direct profiler is dropping them.

Source defect in built code `f2b1b6f...`:

- fixed 8-slot table claims by `(address, ArbitrationType)`;
- report resets counters but never clears `address_key`;
- startup permanently occupies all eight slots;
- later gameplay addresses are all overflowed;
- stale later `top0..top3` addresses are startup keys and must not be interpreted as gameplay objects.

The first runtime therefore does **not** establish gameplay address, mode, timeout, direct duration or waker.

## Corrected Stage A source prepared

Code commit:

`0d09c314b1aec644624996f1ca800a10e93c9fa4`

Diff versus the successfully built source:

- only `src/core/x1_address_arbiter_profiler.h`
- 8 additions / 1 deletion

Correction:

- direct AddressArbiter collection is disarmed during the first 120 rendered frames;
- first report is startup warmup;
- collection arms after the warmup report;
- slots are explicitly cleared at initialization;
- slot count remains 8;
- no new wait/sleep/lock/scheduler/GPU policy behavior.

This corrected source has **not** been ARM64-built.

## Current next action

Read:

- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER.md`
- `NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md`

With a future freshly authorized corrected Stage A build, answer only:

1. does one gameplay `(address, ArbitrationType)` dominate?
2. is it exactly one call per rendered frame?
3. what timeout is used?
4. does direct WaitForAddress blocked duration reconcile with the reason-level Arbitration bucket?
5. does the same key remain dominant from fast swap2 through transition into stable swap3?

Only if one address is proven dominant should Stage B instrument `SignalToAddress` for that exact address.

Do not add broad scheduler tracing.

Do not add a generic all-SVC recorder.

Do not chase `None` unless another corrected runtime reproduces a stable-slow `None`-dominant window.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.