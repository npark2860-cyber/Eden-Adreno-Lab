# P0.2 Transfer Pressure and Render-Pass End Reasons

P0.2 extends the opt-in Adreno profiler without changing Vulkan command generation,
synchronization policy, resource lifetime, or Qualcomm workaround policy.

## Added counters

Each `[ADRENO-P0.2]` summary reports:

- render-pass end counts tagged by caller reason: deferred clear, framebuffer change,
  outside-render-pass operation, submit, and deferred-clear flush,
- staging upload request count and requested bytes,
- staging download request count and requested bytes, with deferred-download subset,
- buffer-cache `CopyBuffer` call count and sum of `VkBufferCopy::size`,
- reordered stream-upload copy count and bytes as a subset of buffer copies.

## Interpretation

- Staging byte counters are requested mapped staging bytes. They are pressure indicators, not a
  claim that the GPU transferred exactly that many bytes.
- Buffer-copy bytes are the byte ranges submitted through `BufferCacheRuntime::CopyBuffer`; they do
  not include every image transfer in the renderer.
- Reordered-upload bytes are a strict subset where the source is the stream buffer and Eden already
  chose the existing upload-command-buffer reorder path.
- Render-pass reason tags describe the scheduler call-site cause. Deferred-clear realization can
  legitimately produce nested render-pass endings, so reason totals should be interpreted together
  with total render-pass begin/end counts.

## Safety rule

Do not remove barriers, merge render passes, alter submission cadence, or change transfer routing
from these counters alone. Use them to choose the next single-variable A/B experiment.
