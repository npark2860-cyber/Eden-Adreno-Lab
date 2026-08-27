# Eden Adreno Lab

This repository is an experimental fork of Eden focused on Qualcomm Adreno X1-85 Vulkan behavior and performance.

## Method

1. Keep the upstream baseline reproducible.
2. Instrument before optimizing.
3. Change one Qualcomm workaround or Vulkan path at a time.
4. Test the same game, save, scene, settings, driver and cache state.
5. Record FPS, frametime, correctness and crashes for every A/B run.

## Initial investigation targets

- Qualcomm optimal-image readback / CopyImageToBuffer path
- scaled vertex format emulation
- descriptor aliasing workaround
- color write enable workaround
- shader atomic int64 workaround
- workgroup memory explicit layout workaround
- reported binding-limit override
- graphics/compute pipeline creation and cache behavior
- queue submit, fence and synchronization stalls

The first goal is not to remove workarounds. It is to measure their real cost and determine which ones are still required on the X1-85 Windows driver.
