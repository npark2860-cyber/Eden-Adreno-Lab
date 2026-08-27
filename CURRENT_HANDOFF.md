# CURRENT HANDOFF — Eden Adreno X1 Uniform fast-stream diagnosis

Updated: 2026-08-27 KST

## Fixed baseline

- Lab repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Completed texture experiment: `exp/x1-texture-fill-reasons`
- Completed alias-route experiment: `exp/x1-alias-copy-reasons`
- Completed alias-redundancy experiment: `exp/x1-alias-sync-redundancy`
- Completed Uniform path experiment: `exp/x1-uniform-stream-reuse`
- Completed payload diagnostic: `exp/x1-uniform-payload-fingerprint`
- Current A/B experiment: `exp/x1-uniform-cache-ab`

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Current branch / build state

Branch:

`exp/x1-uniform-cache-ab`

Functional A/B preparation was created from payload-fingerprint HEAD:

`c7fc84bc7da50576235dd6f982be264c573e41cb`

The branch was initially prepared at:

`d2addb5247b3f31139074a8bca10cd9f24d8305e`

Because the connected GitHub tool did not expose direct `workflow_dispatch`, one authorized build was started through a temporary one-shot push trigger restricted to the experiment workflow. The trigger was then removed and the workflow restored to `workflow_dispatch` only.

Current branch HEAD before this handoff update was:

`6df9c5ad530fa2a2a57e9685d029aeb0ff5508fc`

### Authorized Uniform cache A/B build — SUCCESS

- workflow: `Build dc95 X1 Uniform Cache AB`
- run: `33045572814`
- job: `98428654028`
- attempt: 1
- build HEAD: `8e8351953d966a1c7677940b7a926aae902969d1`
- result: **success**
- static A/B verification: success
- configure: success
- ARM64 compile: success
- package: success
- artifact upload: success
- artifact: `Eden-dc95-X1-uniform-cache-ab`
- artifact id: `9636118096`
- size: 31,302,610 bytes
- SHA-256: `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`
- artifact expiry: 2026-09-10

Build attempts for this A/B: **1 total**. Authorization is consumed. There was no rerun.

## A/B implementation semantics

Checkbox:

`X1 A/B: Disable Adaptive Uniform Fast Stream`

Default: **OFF**.

At Vulkan `BufferCacheRuntime` construction, the A/B bit becomes active only when both are true:

- Vulkan driver is `VK_DRIVER_ID_QUALCOMM_PROPRIETARY`
- the checkbox setting is enabled

OFF preserves the existing payload-fingerprint fast-stream policy.

ON changes only adaptive small-Uniform fast-stream selection:

- `needs_alignment_stream` remains authoritative and still selects mapped streaming
- adaptive `fastSkip` eligibility no longer selects mapped streaming
- the Uniform falls through to the already-existing classic cached path
- existing `SynchronizeBuffer()` decides clean/no-upload versus actual upload

No custom payload cache, hash dedupe, previous staging allocation reuse, scheduler change, barrier suppression, alias-copy suppression, dirty-state mutation change, descriptor lifetime change, or persistent Uniform binding change is part of this A/B.

## Latest ON runtime — PARTIAL A/B RESULT, CONFIRMED

Log:

`eden_log(20260827-083649).txt`

Runtime:

- TOTK 1.4.2
- exact Eden identification `HEAD-dc95cd09ee-HEAD`
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- `x1_ab_disable_adaptive_uniform_fast_stream = true`
- run reached frame ~1503
- end `ForceStop` is the user's intentional stop and is not a crash

### A/B routing behavior — STRONG CONFIRMED

The ON control worked exactly as intended.

Representative reports show:

- `fast = 0`
- `fastAlignment = 0`
- `fastSkip = 0`
- `cached = visits`

Therefore adaptive graphics Uniform traffic was fully redirected to the existing classic cached path in this run.

Across report windows ending at frames 960, 1080, 1200, 1320 and 1440 (600 reported frames total):

- visits: **9,449,653**
- fast: **0**
- cached: **9,449,653**
- cachedClean: **8,913,714 = 94.33%**
- cachedUpload: **535,939 = 5.67%**

This independently confirms that most redirected Uniform visits are clean according to Eden's existing dirty tracking.

Payload-fingerprint sample counters are zero in the ON run because those samples are taken from the mapped fast-stream path, which is no longer entered. This is expected and is not an instrumentation failure.

### Performance direction — NO CEILING BREAK IN ON RUN

Using report timestamps only as a coarse runtime-rate indicator:

- frame 960 report: ~78.968 s
- frame 1440 report: ~105.501 s
- 480 frames elapsed in ~26.53 s
- coarse rate: ~18.1 frames/s

This ON run therefore did **not** show a material break above the existing ~20 FPS gameplay ceiling.

Do not yet assign an exact regression percentage versus OFF: a paired same-build OFF run on the same save/route/options is still required.

### Cost migration — STRONG CONFIRMED

The fast-stream work did not simply disappear. Redirecting into the classic cache moved a substantial part of the cost into buffer upload/copy/outside-render-pass and scheduler synchronization work.

Current ON frame-1440 / 120-frame report:

Uniform draw category:

- scopes: 3,156,315
- uploadReq: 122,803
- upload: 484.672 MiB
- copy: 122,803 / 484.672 MiB
- outside: 87,863

Overall upload/scheduler report:

- stagingUpload: 137,042 / 678.987 MiB
- bufferCopy: 136,314 / 623.469 MiB
- barriers: 114,016
- scheduler wait: 1,547 calls / 6504.470 ms
- finish: 378 / 794.399 ms
- submit: 2,249 = 18.74/frame
- RP: 117,243
- images/postRPbarrier: 439,934

For qualitative context only, the earlier payload-fingerprint OFF runtime at frame 1440 had:

- Uniform uploadReq: 1,899,945
- Uniform upload: 760.912 MiB
- Uniform copy: 2,283 / 14.883 MiB
- Uniform outside: 296
- scheduler wait: 1,230 / 2669.884 ms

These are not a perfectly paired same-build comparison, so do not use their ratios as final regression numbers. They do establish the architectural direction: disabling adaptive mapped streaming drastically reduces tiny Uniform staging requests but causes classic dirty Uniforms to become explicit copy/outside-RP work and increases synchronization pressure.

## Current interpretation

### Confirmed

1. Adaptive `fastSkip` can be completely disabled on Qualcomm/X1 without immediately preventing TOTK gameplay from reaching the measured test segment.
2. When redirected, about 94% of measured Uniform visits are classic-cache clean and avoid a real Uniform content upload.
3. Simply redirecting all adaptive fast Uniforms to the classic cache is **not a performance optimization** in this test.
4. The former fast-stream cost is exchanged for classic buffer-cache copy/outside-RP/synchronization pressure.
5. The hypothesis that adaptive Uniform re-stream volume by itself is the full cause of the steady ~20 FPS ceiling is not supported by this ON run.

### Still open

The Uniform findings are still important. Previous payload telemetry established that repeated fast Uniform keys overwhelmingly carry the same payload fingerprint. The next optimization design should therefore avoid both extremes:

- do not re-stream identical small Uniform payloads on every visit
- do not force those visits into the classic GPU-buffer copy/synchronization path

A future safe direction is a Qualcomm/X1-narrow fast-path reuse/cache design that preserves mapped-stream lifetime/in-flight safety while reducing redundant byte copies/staging work. Do **not** blindly reuse a previous staging allocation across frames or command-buffer lifetimes.

Before selecting that implementation, complete the paired A/B measurement with the same built artifact.

## Closed alias result

Repeated alias copy pair/region traffic is **not** trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not pursue simple alias copy dedupe or suppress required outside-render-pass `vkCmdCopyImage` work.

## Prior exact dc95 Uniform facts — RETAINED

1. Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
2. Vulkan revisits enabled graphics Uniform bindings rather than preserving the OpenGL-style dirty binding mask.
3. Classic cached path calls `SynchronizeBuffer()` and can finish with zero upload when the guest range is clean.
4. `uniform_cache_hits` counts that clean/no-upload outcome.
5. Adaptive small-Uniform fast path is a stall-avoidance mapped re-stream path, not payload reuse.
6. Fast Vulkan Uniform path requests upload staging, adds a descriptor and copies guest bytes again.

## Prior payload fingerprint runtime — RETAINED

Matched payload log:

`eden_log(20260827-052251).txt`

Gameplay aggregate frames 1320–3000 = 1800 frames:

- visits: 41,733,585
- fast: 41,188,346 = 98.69%
- fastAlignment: 0
- fastSkip: 41,188,346
- cached: 545,239
- cachedClean: 513,129 = 94.11% of cached
- cachedUpload: 32,110
- average fast payload: 410.46 bytes
- fast streams/frame: 22,882.4

Payload samples:

- samples: 1,890,393
- uniqueSamples: 14,526
- repeatSamples: 1,835,334
- sameFingerprint: 1,792,196
- changedFingerprint: 43,138
- sampleOverflow: 40,533
- 97.65% of tracked repeated samples had the same fingerprint
- 99.17% of classified same-frame repeats had the same fingerprint

Interpretation boundary remains:

> Same key/fingerprint is strong evidence for redundant payload restaging, but it does not by itself prove that an old staging allocation is safe to reuse. Descriptor identity, staging lifetime and in-flight GPU use must remain correct.

## What NOT to do next

- no ARM64 Actions without fresh explicit permission
- no build rerun from the already-consumed authorization
- no alias trivial dedupe
- no render-pass/barrier suppression
- no blind persistent-binding enable
- no blind previous-staging reuse
- no global change to all vendors
- no removal of alignment-required fast streaming
- do not treat `ForceStop` as a crash
- do not call the ON-vs-older-OFF timing difference a final A/B regression percentage

## NEXT ACTION

**No new build is needed.**

Using the already-built artifact `Eden-dc95-X1-uniform-cache-ab`, run the same TOTK 1.4.2 save/route/options with:

`X1 A/B: Disable Adaptive Uniform Fast Stream = OFF`

Then provide that OFF log.

Compare paired OFF vs ON using:

- displayed/runtime FPS and stability
- `[X1-UNIFORM-PATH]`
- `[X1-FLOW][UPLOAD]`
- draw `cat=uniform`
- buffer copy / outside-RP counts
- scheduler wait / finish / submit
- render-pass/image/barrier signals

Only after that paired OFF measurement should the A/B performance conclusion and next implementation experiment be finalized.

## Current build authorization state

- current branch: `exp/x1-uniform-cache-ab`
- Uniform cache A/B Actions runs: 1
- Uniform cache A/B build attempts: 1
- latest attempt result: success
- build authorization for that attempt: consumed
- next ARM64 build authorization: **not granted**
- gameplay optimization promoted: none
- alias copies skipped: none
- barriers/render-pass requests suppressed: none
