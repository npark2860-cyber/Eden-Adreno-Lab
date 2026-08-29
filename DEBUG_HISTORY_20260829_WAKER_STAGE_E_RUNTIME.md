# DEBUG HISTORY — Waker Stage E Runtime

Updated: 2026-08-29 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- device: Windows 11 ARM64 / Snapdragon X Elite / Adreno X1-85
- game: TOTK 1.2.1
- behavior-changing diagnostic A/Bs OFF, including swap3->2 clamp
- Address Arbiter attribution ON

## Successful Stage E ARM64 build

The third separately authorized Stage E ARM64 attempt succeeded end-to-end:

- workflow: `Build dc95 X1 Waker Stage E`
- run: `33231201850`
- job: `99044246393`
- attempt: `1`
- build HEAD: `b750792e460f416a15ed1702c13232c19b9f6b4b`
- conclusion: `success`
- exact dc95 verification: success
- hardened Stage E pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 compile: success
- package/upload: success
- rerun/retry: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-e`
- artifact id: `9708884305`
- size: `31,402,413` bytes
- SHA-256: `a07b9d4d02a2617d710e32d3baae8a5b868e00f81b3b4df4e1390ed5f56dab60`
- expires: 2026-09-12

Persistent ARM workflow was restored to manual-only `workflow_dispatch` immediately after the single approved run was created. Current ARM64 authorization remains NONE.

## Runtime log

`eden_log(20260829-063358).txt`

Runtime identity:

- Eden `HEAD-dc95cd09ee`
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- TOTK 1.2.1
- dynamic victim submitter remains `tid=0x53`
- dynamic waker remains `tid=0x4f`

## Stage E reconciliation

Stage E direct `WaitForAddress` time reconciles with Stage D corrected `Arbitration` time in the stable gameplay windows. Therefore the Stage D Arbitration bucket is a real AddressArbiter dependency and the Stage E hooks cover essentially all of it.

Representative fast frame 960:

- Stage D inter-signal: `33.750 ms`
- Stage D CPU: `6.166 ms/signal`
- Stage D Arbitration total: `655.440 ms / 120f`
- Stage E total direct wait: `665.202 ms / 120f`
- Stage E top0 `0x210b05b39c`: `624.914 ms / 120f`, `0.514 ms` average per completed wait
- Stage E top1 `0x2181c09eb4`: `30.968 ms / 120f`

Representative fast frame 1080:

- Stage D inter-signal: `35.559 ms`
- Stage D CPU: `9.047 ms/signal`
- Stage D Arbitration total: `719.537 ms / 120f`
- Stage E total direct wait: `735.168 ms / 120f`
- Stage E top0 `0x210b05b39c`: `678.477 ms / 120f`, `0.591 ms` average per completed wait
- Stage E top1 `0x2181c09eb4`: `29.993 ms / 120f`

Stable slow windows show the same reconciliation with a large mode shift: Stage D Arbitration rises to roughly `31 ms/frame`, and Stage E direct wait rises to roughly the same level.

## Dominant recursive key

The dominant slow AddressArbiter key is:

`0x210b05b39c`

It owns roughly `26 ms/frame` of the approximately `31 ms/frame` slow Arbitration total. The secondary key `0x2181c09eb4` contributes roughly another `4-5 ms/frame`.

Important structural correction:

The dominant key is not one single ~32 ms wait per rendered frame. The dynamic waker performs this wait repeatedly, roughly 8-10 times per frame. Slowdown comes from each repeated wait becoming materially longer.

Observed top0 per-wait latency examples:

- fast frame 960: `0.514 ms` average
- fast frame 1080: `0.591 ms` average
- slow frame 1440: about `2.7 ms` average
- slow frame 1560: about `3.2 ms` average

The wait count does not explode in slow mode; the per-handshake release latency grows.

## Recursive signal owners

For promoted key `0x210b05b39c`, Stage E finds two dominant guest signalers in the measured run:

- `tid=0x80`
- `tid=0x81`

They split the promoted-key signals approximately evenly in slow gameplay.

Representative slow frame 1440:

- `tid=0x80`: 527 signals, `w2s ~= 2.371 ms` average, `s2e ~= 0.011 ms` average
- `tid=0x81`: 518 signals, `w2s ~= 3.037 ms` average, `s2e ~= 0.011 ms` average

Representative fast frame 960:

- `tid=0x80`: `w2s ~= 0.518 ms` average
- `tid=0x81`: `w2s ~= 0.497 ms` average
- signal-to-waker return remains only a few microseconds / about `0.005-0.007 ms`

Thus the slow delay is again almost entirely before the matching signal. Once either producer signals the promoted key, `tid=0x4f` returns essentially immediately.

## Causal frontier after Stage E

Closed edge:

`tid=0x80 / tid=0x81 -> SignalToAddress(0x210b05b39c) -> tid=0x4f return`

The return side is not the owner. The next question is why the two producer threads take much longer to reach their promoted-key signals in slow mode.

Keep the separate Stage D dynamic-waker CPU branch open:

- waker CPU is low in fast mode and rises by roughly 14-15 ms/signal in slow mode.
- Do not merge that CPU branch with the recursive producer branch without direct evidence.

## Next action

Stage F should dynamically identify the top two Stage E promoted-key signalers without hardcoding `0x80` or `0x81`, then split each producer's signal-to-signal interval into:

- total interval
- corrected KThread Waiting
- residual
- actual guest CPU time using the same scheduler clock domain as Stage D
- runnable-unscheduled residual
- corrected wait-reason totals

No broad all-thread scheduler trace and no PC/LR sampler yet. CPU callsite attribution is only justified later if Stage F shows CPU growth dominates.
