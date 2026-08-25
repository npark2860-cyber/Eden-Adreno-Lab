# P0 Existing-Log Baseline Analyzer

`tools/adreno_lab/analyze_eden_gpu_log.py` extracts a zero-modification baseline from Eden's existing GPU/Vulkan logs.

## Usage

```powershell
python tools/adreno_lab/analyze_eden_gpu_log.py "C:\path\to\eden_gpu.log"
python tools/adreno_lab/analyze_eden_gpu_log.py "C:\path\to\eden_gpu.log" --json
```

## What it currently extracts

- render-pass begin/end count and attachment count seen at begin,
- `vkQueueSubmit` / `vkQueueSubmit2` count,
- graphics/compute pipeline create/bind counts where the selected Eden log level exposes them,
- graphics/compute pipeline build failures,
- descriptor binds exposed by the existing logger,
- memory allocation/deallocation counts and Device/Host visibility flags,
- top Vulkan calls.

## Scope

This tool does not infer that a high count is automatically a bug. It exists to establish the baseline before renderer changes. Counts are limited by the Eden GPU logging level and enabled logging categories.

The runtime `P0 Adreno Profiler` extends this with counters that the existing logger does not expose reliably, including wait wall time, post-render-pass image barriers, descriptor reservation pressure, and pipeline build wall time.
