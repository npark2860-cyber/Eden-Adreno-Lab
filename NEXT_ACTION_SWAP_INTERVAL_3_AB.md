# NEXT ACTION — guest swap-interval 3 attribution / A-B proposal

Updated: 2026-08-27 KST

## Confirmed trigger

The frame-cadence attribution runtime closed the original 30 -> ~20 question.

Runtime log:

`eden_log(20260827-104943).txt`

Matched environment:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- exact Eden source identification `HEAD-dc95cd09ee-HEAD`
- `x1_ab_disable_adaptive_uniform_fast_stream = false`
- `x1_present_frame_log = true`

### Stable swap=2 regime

Guest QueueBuffer frames 562-910:

- 349 QueueBuffer records
- wall duration 11.830372 s
- effective queue rate 29.416 FPS
- median QueueBuffer interval 33.352 ms
- main-buffer acquire median 33.506 ms
- compositor acquire tick delta: 2 for 344 / 348 adjacent acquires
- VI tick median ~16.609 ms
- `WaitForComposite` had no >1 ms waits in this stable segment

### Stable swap=3 gameplay regime

Guest QueueBuffer frames 911-1758:

- 848 QueueBuffer records
- wall duration 48.44955 s
- effective queue rate 17.482 FPS because many 50-ms opportunities are additionally missed
- median QueueBuffer interval 49.985 ms
- main-buffer acquire median 50.044 ms
- compositor acquire tick delta: 3 for 726 adjacent acquires; remaining misses are mostly 4+ ticks
- VI tick median ~16.586 ms and average ~16.667 ms
- `WaitForComposite` median 0 ms; only 4 VI ticks in the segment exceeded 1 ms

The numerical ceiling is therefore explained by the guest/main-layer cadence:

- swap 2 -> nominal 60/2 = 30 FPS opportunity
- swap 3 -> nominal 60/3 = 20 FPS opportunity

The game can still run below 20 when it misses those 3-tick opportunities, which explains the user's observation that gameplay is almost always <=20 and rarely 22-23.

## Exact source ownership

Exact dc95 `QueueBufferInput` contains an `s32 swap_interval` field and is constructed by directly reading the guest `InputParcel` with `parcel.ReadFlattened(*this)`.

`BufferQueueProducer::QueueBuffer()` deflates that input and assigns:

`item.swap_interval = swap_interval`

There is no Vulkan/Adreno-derived conversion at that point.

`HardwareComposer` then honors the main-layer interval in two important places:

1. it suppresses another acquire while `frames_since_last_acquire < expected_interval`
2. after a successful acquire it sets `release_frame_number = m_frame_number + swap_interval`

The compositor thread itself still advances at 60 Hz and `ComposeLocked()` returns 1.

Therefore the observed `swap=3` value is already present in the guest QueueBuffer request before Vulkan present/acquire. Do not describe it as a Qualcomm driver 20-FPS cap.

## Interpretation boundary

CONFIRMED:

> The discrete 30 -> <=20 display cadence comes from the main guest BufferQueue swap interval changing from 2 to 3. This is why 22-23 FPS is normally absent: once swap=3 is active, the nominal next presentation opportunity is every third 60-Hz tick (50 ms), with additional misses only reducing FPS further.

NOT YET CONFIRMED:

- why TOTK chooses/sends swap interval 3 in this runtime
- whether it is a normal game-side response to missing the 30-FPS budget, an emulation-timing interaction, or an Eden-specific feedback behavior
- whether forcing interval 2 would improve useful throughput or only alter presentation/release timing

## Proposed diagnostic A/B — DO NOT IMPLEMENT WITHOUT USER APPROVAL

Goal: determine whether `swap=3` merely reflects an already-slow game or also creates a feedback ceiling that prevents intermediate 20-30 FPS throughput.

Proposed checkbox:

`X1 A/B: Clamp Main Swap Interval 3 To 2`

Default: OFF.

Proposed ON behavior, Qualcomm proprietary Vulkan / diagnostic build only:

- preserve/log the raw guest `item.swap_interval` unchanged
- only for the main non-overlay layer, use an effective composer acquire/release interval of 2 when raw interval is exactly 3
- do not change guest frame number, CPU speed, VI base clock, speed limiter, Vulkan present mode, scheduler, fences, barriers, render-pass handling, Uniform policy, alias path, or raw QueueBuffer parcel
- overlays remain untouched
- no clamp for interval 0/1/2 or >=4

Primary observation:

- if raw guest QueueBuffer cadence remains ~50 ms even though composer effective interval is 2, then swap=3 is mostly a symptom of upstream/game pacing and clamping presentation does not restore headroom
- if QueueBuffer cadence shifts into the 33-50 ms range and visible FPS begins showing 21-29 FPS, then the current interval-3 acquire/release policy participates in a feedback ceiling
- if speed/gameplay timing becomes incorrect or rendering regresses, reject the clamp as an optimization regardless of FPS

This is an attribution A/B, not a proposed production fix.

## Build rule

No new ARM64 build is authorized.

The cadence build authorization was consumed by exactly one successful attempt:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`

A fresh explicit user authorization is required before implementing/building the proposed clamp A/B.
