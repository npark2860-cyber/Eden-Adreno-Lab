# CURRENT HANDOFF — Eden Adreno X1 Draw `other` reasons

Updated: 2026-08-26 KST

## Fixed baseline

- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Parent diagnostic branch: `exp/x1-buffer-category-correlation`
- Verified parent HEAD before this experiment: `0ed8df216fbe416f4f569a9490c5f8f128bb0cfc`
- Experiment branch: `exp/x1-draw-other-reasons`
- No ARM64 build may be started without explicit user permission.

## Why this experiment exists

Latest TOTK BufferCategory telemetry showed:

- Draw upload is dominated by `uniform` in normal ~20 FPS windows.
- Heavy 15–6 FPS windows add large `vertex` copy pressure.
- Draw outside-render-pass endings are dominated by residual `other` (~86%).
- All currently attributed Draw barriers landed in residual `other`.

Source inspection found an attribution artifact that must be separated before any optimization A/B: `GraphicsPipeline::ConfigureImpl()` calls `buffer_cache.runtime.PostCopyBarrier()` after the named BufferCache category scopes have ended. Exact dc95 `PostCopyBarrier()` itself requests outside-render-pass context and records a barrier, so BufferCache-generated post-copy synchronization is currently charged to `other`.

## Prepared reason map

Passive reason buckets now split the Draw `other` family into:

- `other/texture-sync-descriptors`
- `other/texture-fill-image-views`
- `other/transform-feedback-break`
- `other/descriptor-acquire`
- `other/push-image-descriptors`
- `other/post-copy-barrier`
- `other/update-render-targets`
- `other/feedback-loop`
- `other/configure-draw`
- `other/flush-work`
- `other/flush-caching`
- `other/dynamic-states`
- `other/query-segment`
- `other/transform-feedback`
- `other/query-counter`
- `other/draw-command`

Residual `cat=other` is intentionally retained. If it remains large, the next source caller must be isolated rather than guessed.

## Important provenance correction

`tools/adreno_lab/transplant_dc95_draw_dispatch_ab_controls.py` already invokes:

1. `transplant_dc95_draw_dispatch_ab_controls_base.py`
2. `transplant_dc95_buffer_category_correlation.py`

The new manual workflow therefore does **not** run BufferCategory a second time. The correct order is:

`dc95 -> full-flow -> Draw/Dispatch correlation -> A/B wrapper (A/B base + BufferCategory) -> Draw other reasons`

This avoids a guaranteed duplicate-transplant failure before configure/build.

## Files prepared on this experiment branch

- `DRAW_OTHER_REASON_MAP.md`
- `tools/adreno_lab/transplant_dc95_draw_other_reasons.py`
- `tools/adreno_lab/analyze_x1_draw_other_reasons.py`
- `.github/workflows/build-dc95-x1-draw-other-reasons.yml`

The workflow is `workflow_dispatch` only. No push trigger exists.

## Runtime logging contract

For the eventual matched gameplay run, enable the existing diagnostic logging needed by the correlation profiler:

- `X1 Log: Scheduler / Sync`
- `X1 Log: Upload / Barrier`

Use the same TOTK scene / comparable gameplay window used for the BufferCategory baseline. Analyze both the original `[X1-FLOW][BUFFER]` rows and the `other/*` family.

## NEXT ACTION

### Until explicit build permission

Do not start GitHub Actions and do not build locally/remotely.

### After explicit build permission

1. Manually dispatch `.github/workflows/build-dc95-x1-draw-other-reasons.yml` on `exp/x1-draw-other-reasons`.
2. Confirm all transplant/verification steps pass before compile.
3. Run the matched TOTK scene with Scheduler/Sync + Upload/Barrier logging enabled.
4. Rank `other/*` reasons by outside-RP, barrier count, staging upload, copy bytes, and wait time.
5. Compare heavy 15–6 FPS windows against normal ~20 FPS windows.
6. Only if one reason dominates, prepare one semantic optimization A/B for that reason. Do not optimize `other` generically.

## Current safety state

- No ARM64 build started.
- No gameplay behavior change introduced by the new reason instrumentation.
- No optimization A/B selected yet.
