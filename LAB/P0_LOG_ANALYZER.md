# P0/P0.2 Log Baseline Analyzer

`tools/adreno_lab/analyze_eden_gpu_log.py` reads Eden GPU/Vulkan logs and the opt-in Adreno profiler summaries without changing renderer behavior.

## Usage

```powershell
python tools/adreno_lab/analyze_eden_gpu_log.py "C:\path\to\eden_gpu.log"
python tools/adreno_lab/analyze_eden_gpu_log.py "C:\path\to\eden_gpu.log" --json
```

The same command can be used on the normal Eden log if that is where the `[ADRENO-P0]` lines were written.

## Existing-log baseline

The analyzer retains the original zero-modification counters when the selected log level exposes them:

- render-pass begin/end count and attachment count seen at begin,
- `vkQueueSubmit` / `vkQueueSubmit2` count,
- graphics/compute pipeline create/bind counts,
- graphics/compute pipeline build failures,
- descriptor binds,
- memory allocation/deallocation counts and Device/Host visibility flags,
- top Vulkan calls.

## P0 profiler summaries

All `[ADRENO-P0]` reports in the file are aggregated. The output includes:

- total reported frames,
- render-pass begin/reuse/end, attachment images and post-render-pass barrier counts,
- render-pass and barrier rates per reported frame,
- submits and submits per reported frame,
- finish/worker wait count and reported wall time,
- graphics/compute pipeline build count, failure count and build wall time,
- descriptor reservations, entries, descriptor-buffer entries/binds and overflows.

## P0.2 profiler summaries

All `[ADRENO-P0.2]` reports are aggregated. The output includes:

- render-pass end reasons: unknown, deferred clear, framebuffer change, outside operation, submit and deferred-clear flush,
- staging upload request count and reported MiB,
- staging download request count and reported MiB,
- deferred-download subset,
- buffer-copy call count and reported MiB,
- reordered-upload copy subset and its share of reported buffer-copy MiB in JSON output.

The MiB totals are reconstructed from the profiler's printed values, which are rounded to three decimal places. They must be treated as reported pressure metrics, not exact byte-accurate GPU transfer totals.

## Scope

A high count does not automatically indicate a bug. The analyzer exists to make same-scene A/B comparisons repeatable and to identify which pressure source deserves the next single-variable experiment.
