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

## Native Windows ARM64 validation

Validation was performed on a native GitHub `windows-11-arm` runner.

- A pure MSVC `cl.exe` ARM64 attempt configured successfully but stopped in pre-existing Eden
  `src/common/uint128.h` because `_umul128/_udiv128` are not available on that path.
- Eden's own Windows CI configuration was checked and its `msvc` path selects `clang-cl`.
- The Eden-compatible validation used Windows 11 ARM64, clang-cl 22.1.4 and ARM64 Vulkan SDK
  1.4.341.1.
- CMake configuration succeeded.
- The complete `video_core` target build succeeded.

Successful validation branch/commit:
`lab/validate-p0-2-win-arm64 @ 53e1212075a2899ec35ae2801561a37e5e215911`

Successful Actions run: `32911250005`.

This validates compilation of the P0/P0.2 Vulkan instrumentation on native Windows ARM64 using
Eden's intended clang-cl toolchain path.

## Runtime capture protocol

Use one fixed game/save/scene/settings/cache state for each comparison. Do not change more than one
experimental variable between captures.

Before launching Eden from PowerShell:

```powershell
$env:EDEN_ADRENO_PROFILE="1"
$env:EDEN_ADRENO_PROFILE_FRAMES="120"
```

Then:

1. launch the P0.2 build,
2. enter the fixed comparison scene,
3. remain in that scene long enough to produce multiple `[ADRENO-P0]` and `[ADRENO-P0.2]` reports,
4. close Eden normally when possible,
5. preserve the complete log rather than copying only selected lines,
6. analyze it with:

```powershell
python tools/adreno_lab/analyze_eden_gpu_log.py "C:\path\to\log" --json
```

The profiler activates only when the Vulkan driver identifies itself as
`VK_DRIVER_ID_QUALCOMM_PROPRIETARY`.

## Decision order after capture

Use the measured dominant pressure source to select the next single-variable A/B:

1. synchronous wait time/count,
2. render-pass churn and its dominant termination reason,
3. post-render-pass barrier pressure,
4. transfer/copy pressure,
5. descriptor reservation/bind/overflow pressure,
6. pipeline build time/failures.

This order is for experiment selection, not for declaring any counter inherently defective.

## Safety rule

Do not remove barriers, merge render passes, alter submission cadence, or change transfer routing
from these counters alone. Use them to choose the next single-variable A/B experiment.
