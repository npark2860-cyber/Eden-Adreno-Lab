# X1 Descriptor Buffer Ring Experiment — dc95

## Control

- Immutable source control: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable Lab control branch: `lab/dc95-arm64-baseline`
- Experimental branch: `exp/x1-descriptor-ring`
- Target: Windows ARM64 / Snapdragon X / Adreno X1-85 / Qualcomm proprietary Vulkan driver

## Evidence state

### CONFIRMED — dc95 source behavior

1. `Device::IsTiler()` returns true for `VK_DRIVER_ID_QUALCOMM_PROPRIETARY` without an Android-only condition.
2. `DescriptorBufferRing` therefore selects `TILER_FRAME_SIZE = 2 MiB` on Qualcomm proprietary Vulkan, including Windows ARM64.
3. `FRAMES_IN_FLIGHT = 8`.
4. On first descriptor allocation after a frame slot is reused, dc95 calls `scheduler.Wait(frame_ticks[frame_index])`.
5. When the current frame consumes all descriptor chunks, dc95 logs `Descriptor buffer frame exhausted, stalling on the GPU` and calls `scheduler.Finish()`.
6. `RasterizerVulkan::TickFrame()` advances `descriptor_buffer_ring.TickFrame()` once per renderer frame.

### OPEN — X1-85 runtime question

Whether the 2 MiB Qualcomm/tiler frame policy creates measurable descriptor-buffer pressure or GPU stalls on Adreno X1-85 is not yet known.

Do not infer a bottleneck from the source policy alone.

## Minimal instrumentation

Enable with:

```text
EDEN_X1_DESCRIPTOR_PROFILE=1
EDEN_X1_DESCRIPTOR_PROFILE_FRAMES=120
```

Log prefix:

```text
[X1-DBUF]
```

Aggregated metrics per report interval:

- descriptor allocation count
- aligned descriptor bytes and KiB/frame
- frame-slot reuse `Scheduler::Wait` count and total wall time
- descriptor chunk-switch count
- descriptor-frame exhaustion `Scheduler::Finish` count and total wall time

The profiler activates only for `VK_DRIVER_ID_QUALCOMM_PROPRIETARY`.

## Instrumentation boundary

This phase does **not** change:

- `FRAMES_IN_FLIGHT`
- `TILER_FRAME_SIZE`
- descriptor chunk sizing
- scheduler synchronization policy
- render-pass policy
- Qualcomm feature gating

It is measurement-only.

Timing calls are made only around the pre-existing reuse `Wait` and exhaustion `Finish`. Counters are atomic because descriptor allocation may not be assumed to be single-threaded. Reports are aggregated rather than emitted per allocation.

## Runtime protocol

Use the same game, save, scene, settings and resolution as the clean dc95 Standard control.

1. Run clean dc95 Standard and record FPS/stability.
2. Run descriptor-ring profiled dc95 Standard in the same scene.
3. Capture the Eden log containing `[X1-DBUF]` lines.
4. Do not treat profiler-build FPS by itself as an optimization result; this build exists to identify descriptor-ring pressure.

## Interpretation

### STRONG candidate for X1-specific descriptor-ring A/B

Any repeatable `exhaustionFinish > 0`, especially with material `Finish` wall time, means the current ring budget is forcing synchronous GPU progress and justifies a separate one-variable ring-capacity experiment.

Material frame-slot reuse wait time also keeps this path open, but it must be interpreted with scheduler/GPU progress evidence because reuse waits can reflect upstream GPU latency rather than ring capacity alone.

### Not sufficient by itself

Chunk switches without exhaustion do not prove a stall. Allocation bytes alone do not prove a bottleneck.

### REJECT descriptor ring as a primary ceiling candidate for the tested scene

If repeated scene captures show:

- `exhaustionFinish = 0`, and
- reuse `Wait` time is negligible,

then do not tune ring size first. Move to scheduler synchronization scope / render-pass boundaries according to the project experiment order.

## Next A/B only if runtime evidence supports it

Create a new branch from exact dc95 and change one ring policy variable only. Do not mutate this instrumentation branch into the optimization branch.
