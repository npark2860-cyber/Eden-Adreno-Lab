# CURRENT HANDOFF — Eden Adreno X1 texture Fill/RT reasons

Updated: 2026-08-27 KST

## Fixed baseline

- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Previous experiment: `exp/x1-draw-other-reasons`
- Current experiment: `exp/x1-texture-fill-reasons`
- No ARM64 build may be started or re-run without a fresh explicit user permission. One permission = one attempt.

## What the previous experiment proved

The successful `exp/x1-draw-other-reasons` runtime split the old Draw `other` bucket enough to establish:

- Draw barrier owner: `other/post-copy-barrier` — CONFIRMED
- Dominant Draw outside-RP owner: `other/texture-fill-image-views`
- Secondary outside-RP owner: `other/update-render-targets`

Across the analyzed 960–1680 windows:

- `other/texture-fill-image-views`: 16,570 outside-RP (~62.35%)
- `other/update-render-targets`: 6,693 (~25.19%)
- `other/post-copy-barrier`: 3,311 (~12.46%)

Uniform uploads remain a separate normal ~20 FPS ceiling candidate; heavy dips add texture outside-RP work and Vertex-copy spikes. Do not collapse these into one cause.

## Current experiment

Exact dc95 source path:

`FillImageViews -> VisitImageView -> PrepareImageView -> PrepareImage`

and `UpdateRenderTargets(false)` shares `PrepareImageView()` plus dirty-RT discovery / rescale work.

Prepared child buckets:

- `other/texture/create-view`
- `other/texture/refresh-standard`
- `other/texture/refresh-converted`
- `other/texture/refresh-accelerated`
- `other/texture/alias-copy`
- `other/texture/alias-scale`
- `other/texture/blacklist-scale`
- `other/texture/rt-find-color`
- `other/texture/rt-find-depth`
- `other/texture/rt-scale`

Existing parents remain:

- `other/texture-fill-image-views`
- `other/update-render-targets`

Instrumentation-only: no Draw/Dispatch work is skipped, synchronization is not suppressed, guest work is not reordered.

## Authorized build attempt — FAILED BEFORE COMPILE

User explicitly authorized one ARM64 build attempt on 2026-08-27 KST.

Trigger/build identifiers:

- workflow: `Build dc95 X1 Texture Fill Reasons`
- run: `33012886868`
- job: `98323462272`
- build head: `623593cdd4fa7a5256b5f83e97b90b65bd6fbafe`
- runner: `windows-11-arm` / image `windows-11-arm64`
- result: `failure`

The runner was acquired normally. Checkout and all previous profiler transplants succeeded. Failure occurred in:

`Transplant texture FillImageViews and RT subreasons`

Exact error:

`RuntimeError: alias copy calls: expected 3 matches, got 2`

No configure or compile step ran.

## Root cause — CONFIRMED

`SynchronizeAliases()` does contain three semantic `CopyImage(image_id, aliased->id, aliased->copies)` calls, but the exact dc95 source has two at 12-space indentation and the final one at 8-space indentation.

The transplant used one exact string with 12-space indentation and incorrectly expected three matches. This was a transplant pattern bug, not an Eden compile/runtime failure.

## Fix applied

Commit:

`4679d84871c14eb8a0f1b9d6afc38f918e889b12`

Message:

`fix: match all dc95 alias copy call indents`

The alias-copy replacement is now split into:

- two nested 12-space calls
- one final 8-space call

so all three semantic alias copies remain instrumented.

The workflow had already been restored to `workflow_dispatch` only before this fix. The fix commit has zero check runs, confirming it did not start another build.

## Current workflow

`.github/workflows/build-dc95-x1-texture-fill-reasons.yml`

Expected artifact after a successful future build:

`Eden-dc95-X1-texture-fill-reasons`

Runtime settings after success:

- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF

## NEXT ACTION

Do not start or re-run ARM64 Actions until the user gives a fresh explicit permission.

On the next explicit permission, start exactly one build attempt of the same texture-fill diagnostic workflow on `exp/x1-texture-fill-reasons` using the corrected script at/after `4679d84871c14eb8a0f1b9d6afc38f918e889b12`.

If that attempt fails, diagnose/fix but do not re-run without another fresh permission.

## Current safety state

- Latest source-fix commit: `4679d84871c14eb8a0f1b9d6afc38f918e889b12`
- Workflow: manual-only
- Authorized ARM64 attempts consumed: 1
- Additional build attempts after failure: 0
- Gameplay behavior change: none
- Optimization A/B selected: none
