# P0 Adreno Profiler

The P0 profiler is instrumentation-only. It does not change Vulkan command generation,
synchronization, resource lifetime, or Qualcomm workaround policy.

## Enable

On Windows PowerShell before launching Eden:

```powershell
$env:EDEN_ADRENO_PROFILE="1"
$env:EDEN_ADRENO_PROFILE_FRAMES="120"
```

`EDEN_ADRENO_PROFILE_FRAMES` is optional and is clamped to 1..3600. The default is 120.
The profiler only activates when the Vulkan driver reports
`VK_DRIVER_ID_QUALCOMM_PROPRIETARY`.

## Current counters

Each `[ADRENO-P0]` summary reports:

- render-pass begin, reuse, end and attachment counts,
- post-render-pass image barrier count,
- realized deferred clears,
- queue submits,
- synchronous `Finish()` wait count/time,
- `WaitWorker()` count/time,
- graphics/compute pipeline build count, failures and wall time,
- descriptor reservation count and entries,
- descriptor-buffer entries/binds,
- descriptor payload overflows.

## Interpretation rules

- This pass is for locating expensive behavior, not changing it.
- Do not infer GPU execution time from CPU wall time around pipeline builds or waits.
- A high post-render-pass barrier count is a candidate for role-aware synchronization review,
  not proof that a barrier is unnecessary.
- A high render-pass begin/end rate is a candidate for TBDR/GMEM locality review.
- Descriptor counts are pressure/churn indicators; they do not prove descriptor aliasing is safe.

## Next instrumentation

P0.2 should add byte counts and reason tags for upload/readback/copy paths, plus render-pass
termination reasons. GPU timestamp instrumentation should remain targeted and opt-in so the
profiler itself does not materially perturb the workload.
