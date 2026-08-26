# X1 alias-copy reason map

Updated: 2026-08-27 KST

Status: **runtime attribution complete / experiment closed**

Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`

Runtime target: TOTK 1.4.2 / Qualcomm Adreno X1-85 / driver 512.863.0 / Vulkan 1.3.295 / Draw+Dispatch skip OFF.

## Why this experiment existed

The preceding texture-fill run (`eden_log(7).txt`) showed that `other/texture/alias-copy` accounted for **35,017 Draw outside-RP events, 64.64% of 54,175**. The question was which concrete `CopyImage` route owned that churn.

The instrumentation was parent-gated so unrelated `CopyImage()` users such as image join/overlap maintenance could not contaminate the alias result.

## Exact dc95 route map

Generic `TextureCache<P>::CopyImage` routes as:

1. same `SurfaceType` -> `runtime.CopyImage`
2. different type + `ShouldReinterpret` -> `runtime.ReinterpretImage`
3. otherwise -> `runtime.ConvertImage`

Vulkan `TextureCacheRuntime::CopyImage` then performs:

1. optional `InvalidateResolveShadow`
2. BytesPerBlock mismatch -> possible `ReinterpretImage` fallback
3. otherwise -> `scheduler.RequestOutsideRenderPassOperationContext()` + barriers + `vkCmdCopyImage`

Prepared child buckets were:

- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/reinterpret-route`
- `other/texture/alias-copy/convert-route`
- `other/texture/alias-copy/direct-resolve-invalidate`
- `other/texture/alias-copy/direct-bpb-reinterpret`
- `other/texture/alias-copy/direct-vk-copy`

## Successful diagnostic build

- workflow: `Build dc95 X1 Alias Copy Reasons`
- run: `33019025980`
- job: `98344461231`
- build head: `eaec1e760057cd284fe379d5fd1bd0009805432d`
- result: success
- artifact: `Eden-dc95-X1-alias-copy-reasons`
- artifact id: `9626369486`
- artifact SHA-256: `653b232e91aa2a120239106ac991e8b3308b5f95651b6ac0414eda38f2647aef`

The workflow was restored to `workflow_dispatch` only after the one-shot trigger.

## `eden_log(8).txt` result — CONFIRMED

Whole-log alias child totals:

| Bucket | Scopes | Outside-RP |
| --- | ---: | ---: |
| `direct-route` | **100,021** | 0 |
| `direct-resolve-invalidate` | **100,021** | 0 |
| `direct-vk-copy` | **100,021** | **24,806** |
| `reinterpret-route` | 0 | 0 |
| `convert-route` | 0 | 0 |
| `direct-bpb-reinterpret` | 0 | 0 |

Whole-log attributed Draw outside-RP was **39,017**. `direct-vk-copy` alone contributed **24,806 = 63.58%**.

That almost exactly reproduces the previous broad `alias-copy` share of **64.64%**, strongly cross-validating the attribution.

Representative windows:

- frame 1080: direct-route scopes 16,009; `direct-vk-copy` outside 4,027; resolve invalidation outside 0
- frame 1320: `direct-vk-copy` outside about 3,696
- frame 1560: direct-route scopes 14,871; `direct-vk-copy` outside 3,740; resolve invalidation outside 0

## What is now ruled out

For this matched runtime:

- generic cross-type reinterpretation is not the alias outside-RP cause
- format conversion is not the alias outside-RP cause
- BytesPerBlock reinterpret fallback is not the alias outside-RP cause
- resolve-shadow invalidation is not the alias outside-RP cause

The measured alias outside-RP path is:

`SynchronizeAliases -> CopyImage -> TextureCacheRuntime::CopyImage -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

## Performance interpretation

This path is persistent even in ~20 FPS report windows, so it is a steady burden but not the only cause of severe dips.

The current multi-axis model remains:

- persistent tiny Uniform uploads: normal ceiling candidate
- persistent alias direct `vkCmdCopyImage` render-pass churn: second steady burden
- severe dips: the above plus bulk staging upload, Vertex/Index copy spikes, and texture refresh activity
- `PostCopyBarrier`: Draw barrier owner, but not the dominant alias outside-RP owner

Do not collapse these into one root cause.

## Next question

Do **not** split `TextureCacheRuntime::CopyImage` further and do **not** suppress `RequestOutsideRenderPassOperationContext()` blindly. `vkCmdCopyImage` must execute outside a render pass.

The next diagnostic must move upward to `SynchronizeAliases()` and determine **why so many direct copies are requested and whether copies are redundant**.

See `NEXT_ACTION_ALIAS_SYNC_REDUNDANCY.md`.
