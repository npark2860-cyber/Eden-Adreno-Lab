# NEXT ACTION — X1 main swap interval 3 -> 2 A/B

Updated: 2026-08-27 KST

## Fixed baseline

- Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- lab branch: `exp/x1-swap-interval-3-to-2-ab`
- predecessor: `exp/x1-frame-cadence-attribution@d32cf164b12260d6ab49fc7c3d965141d22af69f`

Never change the exact Eden baseline without the explicit baseline-change procedure.

## Why this A/B exists

Cadence runtime `eden_log(20260827-104943).txt` confirmed:

- stable raw guest `swap=2` segment: QueueBuffer median ~33.352 ms, nominal 30-FPS opportunity
- stable raw guest `swap=3` gameplay segment: QueueBuffer median ~49.985 ms, nominal 20-FPS opportunity
- VI compositor remains ~60 Hz
- `WaitForComposite` is normally near 0 ms in the stable swap=3 segment
- raw `swap_interval` comes from guest `QueueBufferInput` and is stored unchanged as `item.swap_interval`

Therefore the discrete 30 -> <=20 ceiling is directly explained by the guest/main-layer interval changing 2 -> 3. What is not yet known is whether interval 3 is only a symptom of already-slow upstream production, or whether Eden's interval-3 acquire/release policy participates in a feedback ceiling.

## A/B control

Checkbox:

`X1 A/B: Clamp Main Swap Interval 3 To 2`

Default: **OFF**.

### OFF

Preserve the cadence-attribution baseline exactly.

### ON

In this dedicated Windows ARM64 Vulkan X1 diagnostic build only:

- preserve raw guest `QueueBufferInput::swap_interval`
- preserve `item.swap_interval = swap_interval`
- preserve `[X1-CADENCE][QUEUE] swap=` as the raw guest value
- for main non-overlay HardwareComposer behavior only, when raw interval is exactly 3:
  - effective acquire interval = 2
  - effective release interval = 2
- `[X1-CADENCE][ACQUIRE]` reports both `swap=<raw>` and `effective=<composer value>`
- overlays remain interval 1 behavior
- raw 0/1/2 and >=4 are not clamped

The HardwareComposer service layer does not own Vulkan driver identity. Therefore the implementation is guarded by:

- Windows ARM64 compile target
- Vulkan renderer setting
- explicit debug checkbox
- dedicated X1/Qualcomm lab workflow/branch

This is not a production Qualcomm detection mechanism and must not be promoted as one.

## Hard boundaries

Do not change:

- guest QueueBuffer parcel or raw `item.swap_interval`
- guest frame number
- VI 60-Hz base clock / conductor scheduling
- game speed / speed limiter
- Vulkan present mode / Mailbox / Target_60
- GPU scheduler or fences
- WaitForComposite / RequestComposite semantics
- barriers / render-pass handling
- Uniform policy
- alias path
- buffer-cache behavior
- overlays

No clamp outside raw main-layer interval exactly 3.

## Prepared files

- `tools/adreno_lab/transplant_dc95_swap_interval_3_to_2_ab.py`
- updated `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-swap-interval-3-to-2-ab.yml`

Workflow:

`Build dc95 X1 Swap Interval 3 To 2 AB`

Trigger: `workflow_dispatch` only.

The workflow snapshots and hashes pre-clamp critical files and requires no clamp change to:

- `buffer_queue_producer.cpp`
- VI conductor
- GPU core
- Vulkan swapchain
- Vulkan scheduler
- nvhost_ctrl
- generic buffer cache
- Vulkan buffer cache

Only the temporary Eden checkout's following files may change in the clamp pass:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h`
- `src/yuzu/configuration/configure_debug.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

## Runtime test after a successful authorized build

Use the same TOTK 1.4.2 save / route / settings.

Run A — checkbox OFF:

- confirm raw/effective swap 3/3 in the gameplay region
- record FPS and cadence

Run B — checkbox ON:

- confirm raw/effective swap 3/2 in the same gameplay region
- record visible FPS, QueueBuffer cadence, acquire tick deltas, VI cadence, WaitForComposite, rendering/game-speed correctness

Primary interpretation:

1. raw QueueBuffer remains ~50 ms while effective=2
   - clamp cannot create upstream frames
   - swap=3 is mainly a symptom/guest pacing decision

2. raw QueueBuffer shifts into 33-50 ms and 21-29 FPS begins appearing
   - Eden interval-3 acquire/release timing participates in a feedback ceiling

3. timing or rendering becomes incorrect
   - reject clamp as an optimization regardless of FPS

## Build authorization

**No ARM64 build is authorized by the static-preparation instruction.**

One fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Swap Interval 3 To 2 AB`

If that attempt fails, stop. No retry without another fresh explicit authorization.
