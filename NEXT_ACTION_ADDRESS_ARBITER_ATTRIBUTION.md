# NEXT ACTION — X1 Address Arbiter Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- current lab branch: `exp/x1-address-arbiter-attribution`
- first built AddressArbiter code: `f2b1b6fed220597124274e873523a515e594c09a`
- corrected post-runtime profiler source: `0d09c314b1aec644624996f1ca800a10e93c9fa4`

Never change the Eden baseline without explicit baseline-change approval.

**ARM64 Actions rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## First Stage A attempt — build succeeded, runtime address table invalid

Approved ARM64 build:

- run `33156864030`
- job `98801611676`
- attempt `1`
- conclusion `success`
- build HEAD `f2b1b6fed220597124274e873523a515e594c09a`
- artifact `Eden-dc95-X1-address-arbiter-attribution`
- artifact id `9680703932`
- SHA-256 `7ceef9df425fae50845aa2f63183e40a2d91d2c6205af8e62151e16dbadc9527`

Runtime:

`eden_log(20260828-093056).txt`

Existing Guest Post Wait data is valid and strengthens the AddressArbiter correlation:

- steady fast frame 480-840: `Arbitration ~= 0.9-2.1 ms/frame`
- frame 960 transition to raw swap3: `Arbitration ~= 59.0 ms/frame`
- stable raw-swap-3 frame 1080-1440: `Arbitration ~= 34.1-43.8 ms/frame`
- `arbN=120` in each steady 120-frame gameplay report
- slow-regime Arbitration is roughly 65-81% of tracked Waiting in this runtime
- submitter remains `tid=0x53`, CPU share ~1-2%
- IPC dispatch remains ~0.02-0.03 ms/request

However `[X1-ADDRARB]` cannot identify the gameplay address in this build.

Observed direct-profiler failure:

- frame 120 startup: `slots=8`, `calls=8`, `overflow=1090`
- later gameplay reports: `calls=0`, `overflow ~= 120`

Root cause:

- fixed 8-slot table retains `address_key` forever;
- startup permanently occupies all eight slots;
- later gameplay address/type keys are dropped as overflow.

Do not interpret the stale later `top0..top3` addresses as gameplay objects.

Full record:

`DEBUG_HISTORY_20260828_ADDRESS_ARBITER.md`

## Corrected Stage A source prepared

Source correction commit:

`0d09c314b1aec644624996f1ca800a10e93c9fa4`

Only `src/core/x1_address_arbiter_profiler.h` changed versus the built source.

Correction:

- direct AddressArbiter collection is disabled during the first 120 rendered frames;
- the first report is startup warmup only;
- collection arms after that first report;
- address slots are explicitly cleared at profiler initialization;
- slot count remains 8;
- no new waits/sleeps/locks/scheduler changes/GPU policy changes.

Rationale:

- if gameplay uses one stable `(address, ArbitrationType)`, it should now be captured from frame 121 onward and remain countable across later reports;
- if gameplay uses more than eight distinct keys, post-warmup overflow proves the object/address is not a single stable key and justifies only the next minimal refinement.

## Next runtime question

With the corrected profiler, answer only:

1. does one gameplay guest address dominate the once/frame AddressArbiter wait?
2. which `ArbitrationType` is used?
3. is timeout stable, especially whether it is indefinite (`-1`)?
4. do direct WaitForAddress blocked totals reconcile with `[X1-GUESTWAIT] Arbitration`?
5. does the same address remain dominant across fast raw-swap-2, transition, and stable raw-swap-3 windows?

Do not implement Stage B before these are answered.

## Stage B — only if corrected Stage A proves one dominant address

For that exact proven address only, instrument `Svc::SignalToAddress` / wake side to identify:

- signaling guest thread ID
- signal type/count
- producer/waker timing needed to establish the dependency

Do not trace all SignalToAddress traffic.

## `None` fallback

The previous runtime had one stable-slow frame where `None` dominated; the new runtime did not reproduce that counterexample. Therefore do not branch into `None` tracing yet.

Only if a corrected Stage A runtime again shows a stable-slow window where AddressArbiter is small and `None` dominates should we add a minimal unclassified-BeginWait source tag for `tid=0x53`.

## Safety invariants

Must not change:

- Eden baseline
- scheduling/priority/core affinity
- KThread wait semantics
- AddressArbiter comparison/update semantics
- timeout semantics
- signal/wake semantics
- NVDRV submission behavior
- GPU worker behavior
- BufferQueue/HWC/VI/cadence
- swap interval or frame target

No generic all-SVC profiler.

No broad scheduler tracing.

No per-event AddressArbiter line logging.

## Build state

Corrected source is prepared but **not ARM64-built**.

No ARM64 build is authorized.

Before a future ARM64 attempt:

1. verify current branch/source diff and exact dc95 anchors;
2. verify persistent workflow is `workflow_dispatch` only;
3. ensure any temporary push-trigger one-shot workflow cannot retrigger from source/doc commits;
4. request fresh explicit authorization for exactly one ARM64 attempt;
5. no automatic retry if it fails.