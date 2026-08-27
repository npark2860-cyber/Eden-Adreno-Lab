# NEXT ACTION — X1 Diagnostic Harness

Updated: 2026-08-27 KST

## Fixed baseline

- Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- lab branch: `exp/x1-diagnostic-harness`
- predecessor: `exp/x1-swap-interval-3-to-2-ab@9822e0017ca07da8c8aa0545339230efab6d4967`

Never change the exact Eden baseline without the explicit baseline-change procedure.

## Why this harness exists

The swap 3 -> effective 2 A/B worked correctly but did not materially change gameplay production cadence. raw `swap=3` buffers still arrived in roughly the 50-ms class.

Therefore the next attribution question is upstream of HardwareComposer gating:

> Where is the ~50 ms spent between one QueueBuffer and the next?

At the same time, the lab already has many useful logging and A/B controls. Rebuilding one experiment per question is inefficient. The harness consolidates them into one binary.

## Existing selectable controls retained

The full current diagnostic chain is recreated, retaining the existing checkboxes/A-B controls for:

- upload/barrier/full-flow logging
- pipeline/shader logging
- present/frame logging
- scheduler/sync logging
- descriptor-ring logging
- Draw/Dispatch exact-signature skip A/B
- adaptive Uniform fast-stream A/B
- main swap interval raw-3/effective-2 A/B

No existing control is removed or silently enabled.

## New controls

### `X1 Log: Frame Cadence`

Default OFF.

Controls:

- `[X1-CADENCE][QUEUE]`
- `[X1-CADENCE][ACQUIRE]`
- `[X1-CADENCE][VI]`

This is intentionally independent from `x1_present_frame_log`.

### `X1 Log: Dequeue Attribution`

Default OFF.

Observation-only records:

- `[X1-DEQUEUE][BEGIN]`
- `[X1-DEQUEUE][SLOT]`
- `[X1-DEQUEUE][END]`

The Dequeue switch automatically keeps `[X1-CADENCE][QUEUE]` records, because Queue/Dequeue pairing is required by the analyzer.

Measured components:

- Queue -> Dequeue BEGIN
- pre-slot service time
- `WaitForFreeSlotThenRelock()` total time
- full DequeueBuffer time
- Dequeue END -> next Queue
- total Queue -> Queue cadence

The helper `WaitForFreeSlotThenRelock()` itself must remain byte-for-byte unchanged by the harness pass.

## Analyzer

`tools/adreno_lab/analyze_x1_dequeue_attribution.py`

It selects the dominant BufferQueue core, pairs Dequeue calls with Queue records, and reports:

- average / median / p90 / p99 / max
- whole Dequeue time
- free-slot helper time
- Queue -> Dequeue
- Dequeue -> Queue
- Queue -> Queue
- separate swap=2 and swap=3 groups

Interpretation:

1. Queue -> Dequeue dominates
   - guest/game pacing before requesting the next buffer

2. free-slot helper / Dequeue dominates
   - BufferQueue backpressure / free-slot wait

3. Dequeue is short but Dequeue -> Queue dominates
   - guest rendering / GPU production after dequeue

## Workflow

`Build dc95 X1 Diagnostic Harness`

File:

`.github/workflows/build-dc95-x1-diagnostic-harness.yml`

Trigger:

`workflow_dispatch` only.

Artifact name after a successful build:

`Eden-dc95-X1-diagnostic-harness`

## Static safety boundaries

Harness pass may change only:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h`
- `src/yuzu/configuration/configure_debug.cpp`
- `src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

It must not change:

- raw `item.swap_interval = swap_interval`
- BufferQueue wait helper semantics
- buffer count policy
- VI 60-Hz scheduling
- GPU RequestComposite / WaitForComposite semantics
- Vulkan swapchain / present policy
- Vulkan scheduler
- fences
- barriers / render-pass behavior
- generic/Vulkan buffer-cache behavior
- Uniform behavior beyond the already-existing explicit A/B
- alias behavior

The workflow hashes critical untouched files and rejects newly-added sleeps, waits, schedule/composite requests, raw-swap assignment changes, or buffer-count policy changes.

## First runtime test after a successful authorized build

Use the same TOTK 1.4.2 route and normal gameplay.

Run A:

- `X1 Log: Frame Cadence` ON
- `X1 Log: Dequeue Attribution` ON
- `X1 A/B: Clamp Main Swap Interval 3 To 2` OFF
- `X1 A/B: Disable Adaptive Uniform Fast Stream` OFF
- unrelated high-volume diagnostic logs OFF

Capture both:

- a title/light ~30-FPS / swap=2 region if practical
- steady gameplay <=20 / swap=3 region

Intentional ForceStop after enough data is acceptable.

Upload the Eden log and analyze with:

`python analyze_x1_dequeue_attribution.py <log>`

Then, only if useful, Run B with the same settings except swap clamp ON.

## Build authorization

**No ARM64 build is currently authorized.**

One fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Diagnostic Harness`

If it fails, stop. No retry without another fresh explicit authorization.
