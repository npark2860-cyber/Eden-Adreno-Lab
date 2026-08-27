# CURRENT HANDOFF — Eden Adreno X1 frame-cadence attribution

Updated: 2026-08-27 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-frame-cadence-attribution`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Retained closed facts

### Alias

Repeated alias pair/region traffic is not trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse
- gameplay fast selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached Uniform path is mostly clean
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint; 99.17% of classified same-frame repeats same fingerprint
- wholesale classic-cache fallback A/B did not break the gameplay ceiling and moved cost into explicit copy/outside-RP/synchronization work

Do not blindly reuse old staging allocations or enable persistent Uniform bindings.

## Uniform cache A/B — completed

Branch: `exp/x1-uniform-cache-ab`

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Uniform Cache AB`
- run `33045572814`
- job `98428654028`
- attempt 1
- build HEAD `8e8351953d966a1c7677940b7a926aae902969d1`
- artifact `Eden-dc95-X1-uniform-cache-ab`
- artifact id `9636118096`
- SHA-256 `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`

ON runtime:

- `x1_ab_disable_adaptive_uniform_fast_stream = true`
- fast / fastSkip = 0
- redirected classic-cache visits mostly clean (~94.33%)
- gameplay remained ~18 FPS in the matched run
- representative frame-1440: ~122.8k Uniform copies, ~484.7 MiB copied, ~87.9k Uniform outside-RP operations, scheduler wait ~6504 ms / 120 frames

Conclusion: wholesale classic-cache fallback is not an optimization.

Paired OFF runtime then exposed a different pattern:

- title/light region ~30 FPS
- gameplay nearly always <=20 FPS
- intermediate 22-23 FPS unusually rare
- Vulkan `Target_60` pacing totals only fractions of a millisecond / 120 frames

That observation triggered the cadence attribution experiment.

## Frame cadence attribution — BUILD SUCCESS

Branch:

`exp/x1-frame-cadence-attribution`

Authorized build:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- result: success
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- artifact size 31,305,699 bytes
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`
- expires 2026-09-10
- attempts 1, reruns 0

Administrative cleanup after the build moved the branch HEAD beyond the build HEAD. Do not confuse branch HEAD with artifact build HEAD.

The one build authorization is consumed. No further ARM64 build is authorized.

## Frame cadence runtime — CONFIRMED RESULT

Runtime log:

`eden_log(20260827-104943).txt`

Matched environment:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- exact Eden identification `HEAD-dc95cd09ee-HEAD`
- `x1_present_frame_log = true`
- `x1_ab_disable_adaptive_uniform_fast_stream = false`

Instrumentation records:

- `[X1-CADENCE][QUEUE]`: guest BufferQueueProducer QueueBuffer completion, raw swap interval
- `[X1-CADENCE][ACQUIRE]`: compositor acquisition of a new main/overlay buffer and compositor tick
- `[X1-CADENCE][VI]`: active composition tick, WaitForComposite duration and total composition work

### Stable ~30-FPS / swap=2 regime

Guest QueueBuffer frames 562-910:

- 349 QueueBuffer records
- duration 11.830372 s
- effective QueueBuffer rate 29.416 FPS
- median QueueBuffer interval 33.352 ms
- main-buffer acquire median 33.506 ms
- adjacent main acquires: tick delta 2 for 344 / 348
- VI tick median ~16.609 ms
- no `WaitForComposite > 1 ms` event in this stable segment

### Stable gameplay / swap=3 regime

Guest QueueBuffer frames 911-1758:

- 848 QueueBuffer records
- duration 48.44955 s
- effective QueueBuffer rate 17.482 FPS because many nominal opportunities are additionally missed
- median QueueBuffer interval 49.985 ms
- main-buffer acquire median 50.044 ms
- adjacent main acquires: tick delta 3 for 726, remainder mostly 4+ tick misses
- VI tick median ~16.586 ms / mean ~16.667 ms
- `WaitForComposite` median 0 ms; only 4 VI ticks exceeded 1 ms in the stable gameplay segment

Critical transition:

- QueueBuffer frame 910: `swap=2`
- QueueBuffer frame 911: `swap=3`
- from frame 911 onward the final gameplay run remains `swap=3` through frame 1758

Therefore the user's observed 30 -> <=20 staircase is no longer merely a hypothesis.

### CONFIRMED cadence interpretation

> Main guest BufferQueue swap interval 2 provides nominal 60/2 = 30 FPS presentation opportunities. Main guest BufferQueue swap interval 3 provides nominal 60/3 = 20 FPS opportunities. When swap=3 is active, missed opportunities only reduce the observed FPS below 20; normal 22-23 FPS values are therefore absent.

This is why the gameplay feels 'pinned' to 20 or lower.

This is **not** evidence of a Qualcomm Vulkan driver hard cap or Eden `Target_60` pacing sleep.

## Exact dc95 swap-interval ownership — CONFIRMED

`src/core/hle/service/nvnflinger/graphic_buffer_producer.h`

- `QueueBufferInput` contains `s32 swap_interval`
- `Deflate()` returns that exact field

`src/core/hle/service/nvnflinger/graphic_buffer_producer.cpp`

- `QueueBufferInput::QueueBufferInput(InputParcel& parcel)` directly calls `parcel.ReadFlattened(*this)`

`src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`

- `QueueBuffer()` deflates the input into local `swap_interval`
- then writes `item.swap_interval = swap_interval`
- no Vulkan/Adreno-derived conversion occurs at this point

Therefore the raw `swap=3` seen by the cadence logger is already present in the guest QueueBuffer request.

`src/core/hle/service/nvnflinger/hardware_composer.cpp`

- VI/compositor frame counter itself advances at 60 Hz
- main-layer acquire is suppressed while `frames_since_last_acquire < NormalizeSwapInterval(item.swap_interval)`
- successful main acquire sets `release_frame_number = m_frame_number + swap_interval`
- `ComposeLocked()` still advances one compositor frame and returns 1
- source comment explicitly notes that only 0/1/2 had been observed historically and says interval 3 would need special consideration for relatively-prime multi-layer handling

For the single main-layer cadence observed here, raw interval 3 is clearly honored by acquire/release bookkeeping.

## What is NOT yet known

- why TOTK chooses/sends `swap_interval=3` in gameplay on this runtime
- whether interval 3 is purely a symptom of missing the 30-FPS budget
- whether an Eden timing/backpressure interaction helps keep the producer in the 3-tick regime once entered
- whether forcing an effective interval 2 would reveal useful 21-29 FPS throughput or merely change presentation/release timing

Do not claim that forcing 2 is a production fix.

## NEXT ACTION

Read:

`NEXT_ACTION_SWAP_INTERVAL_3_AB.md`

The proposed next diagnostic is an A/B control that would leave the raw guest `item.swap_interval` untouched/logged, but for the main non-overlay layer only use an effective composer acquire/release interval of 2 when the raw interval is exactly 3.

Purpose:

- distinguish `swap=3 is only an upstream symptom` from `swap=3 also creates a feedback ceiling`

This experiment is **proposal only**. It has not been implemented and no build is authorized.

A fresh explicit user approval is required before implementing or building it.

## What NOT to do

- no ARM64 Actions without fresh explicit permission
- no rerun of cadence build
- do not call Qualcomm Vulkan / Mailbox / Target_60 the source of the 20-FPS step
- do not rewrite raw guest QueueBuffer data casually
- no VSync/speed-limiter/scheduler/fence/barrier/render-pass changes without a dedicated experiment
- no alias trivial dedupe
- no blind persistent Uniform binding
- no blind previous staging allocation reuse
- do not treat intentional ForceStop as a crash

## Build authorization state

- current branch: `exp/x1-frame-cadence-attribution`
- frame-cadence build attempts: 1
- successful attempts: 1
- reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
