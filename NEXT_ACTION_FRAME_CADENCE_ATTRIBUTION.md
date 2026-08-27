# NEXT ACTION — X1 frame cadence attribution

Updated: 2026-08-27 KST

## Why this experiment exists

The paired Uniform cache A/B did not break the steady gameplay ceiling. The OFF run also exposed a different pattern that must be resolved before choosing the next optimization target:

- light/title-like segment: approximately 30 FPS
- steady gameplay: approximately 19.5–19.6 FPS
- the user reports that intermediate 22–23 FPS values are unusually rare; gameplay feels pinned at or below 20

This resembles 60-Hz cadence quantization (new game frame every 2 composition ticks versus every 3 ticks), but **a literal 20-FPS cap is not yet proven**.

## Exact dc95 source facts already checked

1. `Service::VI::Conductor` schedules `ScreenComposition` from a 60-Hz `FrameNs` base.
2. `HardwareComposer::ComposeLocked()` currently returns `1` after composition; it does not return 2 or 3 to directly select 30/20 Hz.
3. The layer `item.swap_interval` is inspected for framebuffer acquire/release bookkeeping, but the dc95 composer still returns `1`.
4. `nvdisp_disp0::WaitForComposite()` calls `system.GPU().WaitForComposite()`.
5. The existing Vulkan swapchain `Target_60` resource pacing is not consuming the missing ~16.7 ms in measured gameplay: existing `[X1-FLOW]` pacing totals are only fractions of a millisecond per 120 frames.

Therefore do not blame Mailbox/Target_60 or a VI swap-interval cap without new evidence.

## Diagnostic question

Where does a nominal ~50-ms gameplay frame first appear?

The new observation-only instrumentation records three points with the same host steady clock:

1. `[X1-CADENCE][QUEUE]`
   - successful guest `BufferQueueProducer::QueueBuffer`
   - queue/core identity
   - guest frame number
   - slot
   - swap interval

2. `[X1-CADENCE][ACQUIRE]`
   - a new Nvnflinger framebuffer acquired by `HardwareComposer`
   - compositor tick number
   - consumer identity
   - overlay/main flag
   - guest frame number
   - swap interval

3. `[X1-CADENCE][VI]`
   - each active composition tick
   - whether a new main buffer was acquired
   - `WaitForComposite()` duration
   - total `ComposeLocked()` host duration

Analyzer:

`tools/adreno_lab/analyze_x1_frame_cadence.py`

## Interpretation matrix

- producer QueueBuffer ~50 ms **and** main acquire every 3 compositor ticks:
  - the 20-ish cadence already exists upstream / in guest frame production before the compositor

- producer QueueBuffer ~33 ms but main acquire every 3 compositor ticks:
  - consumer/compositor acquisition or release behavior is delaying/dropping ready buffers

- VI tick wall cadence itself stretches toward ~50 ms, or `WaitForComposite()` repeatedly consumes ~16/33 ms:
  - the compositor/GPU hand-off is stalling the 60-Hz VI thread

- producer and acquire both remain ~33 ms while displayed/runtime FPS remains ~20:
  - the cadence loss is after acquisition; investigate renderer composite/present completion next

## Static safety boundary

The cadence transplant is observation-only and is restricted to:

- `src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

The workflow hashes and requires no change to:

- `src/core/hle/service/vi/conductor.cpp`
- `src/video_core/gpu.cpp`
- `src/video_core/renderer_vulkan/vk_swapchain.cpp`
- `src/video_core/renderer_vulkan/vk_scheduler.cpp`
- `src/core/hle/service/nvdrv/devices/nvhost_ctrl.cpp`

It also rejects additions that introduce sleeps, new waits, scheduling changes, swap-interval assignments, speed-limit changes, new composite requests, or alternate return cadence.

## Prepared branch

`exp/x1-frame-cadence-attribution`

Prepared files:

- `tools/adreno_lab/transplant_dc95_frame_cadence_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-frame-cadence-attribution.yml`

Workflow:

`Build dc95 X1 Frame Cadence Attribution`

Trigger:

`workflow_dispatch` only.

Current Actions runs on this branch at preparation time: **0**.

## NEXT ACTION

Stop before Actions.

A fresh explicit user authorization is required for exactly one ARM64 build attempt. The previous Uniform A/B authorization is already consumed and does not carry over.

If a future authorized build succeeds, run TOTK 1.4.2 through both a ~30-FPS title/light segment and the steady ~20-FPS gameplay segment with existing X1 present logging enabled, then analyze the log with `analyze_x1_frame_cadence.py`.

Do not alter VSync, Mailbox, Target_60, swap interval, speed limiter, fences, waits, scheduler, barriers, render-pass behavior, or game mods as part of this attribution test.
