# CURRENT HANDOFF — Eden Adreno X1 swap-interval 3->2 A/B

Updated: 2026-08-27 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-swap-interval-3-to-2-ab`
- predecessor HEAD: `exp/x1-frame-cadence-attribution@d32cf164b12260d6ab49fc7c3d965141d22af69f`

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

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Uniform Cache AB`
- run `33045572814`
- job `98428654028`
- attempt 1
- build HEAD `8e8351953d966a1c7677940b7a926aae902969d1`
- artifact `Eden-dc95-X1-uniform-cache-ab`
- artifact id `9636118096`
- SHA-256 `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`

ON result:

- adaptive fast / fastSkip = 0
- redirected classic-cache visits ~94.33% clean
- gameplay still ~18 FPS in matched run
- representative frame-1440: ~122.8k Uniform copies, ~484.7 MiB, ~87.9k outside-RP Uniform operations, scheduler wait ~6504 ms / 120 frames

Conclusion: wholesale classic-cache fallback is not an optimization.

## Frame cadence attribution — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- size 31,305,699 bytes
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`
- attempts 1, reruns 0

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
- Uniform cache A/B OFF

### Stable raw swap=2 regime

QueueBuffer frames 562-910:

- 349 QueueBuffer records
- duration 11.830372 s
- queue rate 29.416 FPS
- median QueueBuffer interval 33.352 ms
- main acquire median 33.506 ms
- acquire tick delta 2 for 344 / 348 adjacent acquires
- VI tick median ~16.609 ms
- no `WaitForComposite > 1 ms` event in the stable segment

### Stable raw swap=3 gameplay regime

QueueBuffer frames 911-1758:

- 848 QueueBuffer records
- duration 48.44955 s
- queue rate 17.482 FPS because nominal 50-ms opportunities are additionally missed
- median QueueBuffer interval 49.985 ms
- main acquire median 50.044 ms
- acquire tick delta 3 for 726 adjacent acquires; remainder mostly 4+ tick misses
- VI tick median ~16.586 ms / mean ~16.667 ms
- `WaitForComposite` median 0 ms; only 4 VI ticks exceeded 1 ms

Critical transition:

- QueueBuffer frame 910: `swap=2`
- QueueBuffer frame 911: `swap=3`
- final gameplay remains raw `swap=3` through frame 1758

CONFIRMED:

> raw main guest BufferQueue swap 2 creates nominal 60/2=30 FPS opportunities; raw swap 3 creates nominal 60/3=20 FPS opportunities. Misses only lower the rate further, explaining why 22-23 FPS is normally absent and gameplay feels pinned to <=20.

This is not a Qualcomm Vulkan driver hard cap and is not caused by Eden `Target_60` pacing sleep.

## Exact dc95 swap ownership — confirmed

`QueueBufferInput` contains `s32 swap_interval` and is read directly from guest `InputParcel` via `parcel.ReadFlattened(*this)`.

`BufferQueueProducer::QueueBuffer()` deflates it and stores:

`item.swap_interval = swap_interval`

No Vulkan/Adreno conversion occurs there.

`HardwareComposer` honors the main-layer interval by:

1. suppressing another main acquire while `frames_since_last_acquire < expected_interval`
2. setting `release_frame_number = m_frame_number + swap_interval` after successful acquire

The VI/compositor itself still advances at ~60 Hz and `ComposeLocked()` returns 1.

## Current experiment — static preparation complete

Branch:

`exp/x1-swap-interval-3-to-2-ab`

Purpose:

Determine whether raw guest `swap=3` is only a symptom of already-slow upstream frame production, or whether Eden's interval-3 main-layer acquire/release bookkeeping also participates in a feedback ceiling.

Checkbox:

`X1 A/B: Clamp Main Swap Interval 3 To 2`

Default: OFF.

OFF:

- preserve cadence-attribution behavior exactly

ON in the dedicated Windows ARM64 Vulkan X1 diagnostic build:

- preserve raw guest QueueBuffer parcel and `item.swap_interval`
- preserve `[X1-CADENCE][QUEUE] swap=<raw>`
- only for main non-overlay layer, when raw interval is exactly 3:
  - effective acquire interval = 2
  - effective release interval = 2
- overlays unchanged
- raw 0/1/2 and >=4 unchanged
- `[X1-CADENCE][ACQUIRE]` reports both `swap=<raw>` and `effective=<value>`

Important implementation boundary:

HardwareComposer does not own Vulkan driver identity. Runtime guard is therefore Windows ARM64 + Vulkan + explicit checkbox, inside a dedicated X1/Qualcomm lab build. This is not a production Qualcomm-detection mechanism.

Prepared files:

- `tools/adreno_lab/transplant_dc95_swap_interval_3_to_2_ab.py`
- updated `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-swap-interval-3-to-2-ab.yml`
- `NEXT_ACTION_SWAP_INTERVAL_3_TO_2_AB.md`

Workflow:

`Build dc95 X1 Swap Interval 3 To 2 AB`

Trigger: `workflow_dispatch` only.

Clamp pass may alter only the temporary Eden checkout files:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h`
- `src/yuzu/configuration/configure_debug.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

Workflow hashes and requires no clamp change to:

- `buffer_queue_producer.cpp`
- VI conductor
- GPU core
- Vulkan swapchain
- Vulkan scheduler
- nvhost_ctrl
- generic buffer cache
- Vulkan buffer cache

It also rejects newly-added sleeps, wait/schedule/composite requests, speed changes, present-mode changes, and raw `item.swap_interval` assignment changes.

## Runtime interpretation after a future successful build

A/B OFF:

- expect raw/effective 3/3 in steady gameplay

A/B ON:

- verify raw/effective 3/2

Interpretation:

1. raw QueueBuffer remains ~50 ms with effective=2
   - clamp cannot create upstream frames
   - swap=3 is mainly a symptom/guest pacing decision

2. raw QueueBuffer shifts into 33-50 ms and 21-29 FPS begins appearing
   - Eden interval-3 acquire/release timing participates in a feedback ceiling

3. timing/render regression
   - reject clamp as optimization regardless of FPS

## What NOT to do

- no ARM64 Actions without fresh explicit permission
- no rerun of prior cadence build
- do not modify raw guest QueueBuffer data
- no VSync/speed-limiter/Mailbox/Target_60/scheduler/fence/barrier/render-pass changes in this A/B
- no clamp for intervals other than raw main-layer 3
- no alias trivial dedupe
- no blind persistent Uniform binding
- no blind previous staging allocation reuse
- do not treat intentional ForceStop as a crash

## NEXT ACTION

Read:

`NEXT_ACTION_SWAP_INTERVAL_3_TO_2_AB.md`

Static preparation is complete. **Stop before Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Swap Interval 3 To 2 AB`

If it fails, stop. No retry without another fresh explicit authorization.

## Build authorization state

- current branch: `exp/x1-swap-interval-3-to-2-ab`
- swap-clamp build attempts: 0
- reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
