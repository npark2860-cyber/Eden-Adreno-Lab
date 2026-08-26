# CURRENT HANDOFF — Eden Adreno X1 alias synchronization

Updated: 2026-08-27 KST

## Fixed baseline

- Repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Completed texture experiment: `exp/x1-texture-fill-reasons`
- Completed alias-route experiment: `exp/x1-alias-copy-reasons`
- Recommended next branch: `exp/x1-alias-sync-redundancy`

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Latest successful diagnostic build

Alias Copy Reasons:

- workflow: `Build dc95 X1 Alias Copy Reasons`
- workflow file: `.github/workflows/build-dc95-x1-alias-copy-reasons.yml`
- run: `33019025980`
- job: `98344461231`
- build head: `eaec1e760057cd284fe379d5fd1bd0009805432d`
- result: **success**
- all transplant/preflight/configure/build/package/upload steps: success
- artifact: `Eden-dc95-X1-alias-copy-reasons`
- artifact id: `9626369486`
- size: 31,298,049 bytes
- SHA-256: `653b232e91aa2a120239106ac991e8b3308b5f95651b6ac0414eda38f2647aef`

The one-shot push trigger was removed immediately after launch. The workflow is back to `workflow_dispatch` only.

## Latest runtime contract

User tested the successful build with:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF

Runtime log: `eden_log(8).txt`.

## What `eden_log(8).txt` proved — CONFIRMED

Alias child whole-log totals:

| Bucket | Scopes | Outside-RP |
| --- | ---: | ---: |
| `other/texture/alias-copy/direct-route` | **100,021** | 0 |
| `other/texture/alias-copy/direct-resolve-invalidate` | **100,021** | 0 |
| `other/texture/alias-copy/direct-vk-copy` | **100,021** | **24,806** |
| `other/texture/alias-copy/reinterpret-route` | 0 | 0 |
| `other/texture/alias-copy/convert-route` | 0 | 0 |
| `other/texture/alias-copy/direct-bpb-reinterpret` | 0 | 0 |

Whole-log attributed Draw outside-RP: **39,017**.

`direct-vk-copy`: **24,806 / 39,017 = 63.58%**.

Previous texture-fill runtime had broad `other/texture/alias-copy` at **35,017 / 54,175 = 64.64%**. The near-match strongly cross-validates the child attribution.

Representative latest windows:

- frame 1080: direct-route scopes 16,009; direct-vk-copy outside 4,027; resolve invalidation outside 0
- frame 1320: direct-vk-copy outside about 3,696
- frame 1560: direct-route scopes 14,871; direct-vk-copy outside 3,740; resolve invalidation outside 0

## Exact resolved path

The dominant alias outside-RP chain is now:

`Draw Configure`
-> `FillImageViews`
-> `PrepareImage`
-> `SynchronizeAliases`
-> `CopyImage`
-> generic direct route
-> `TextureCacheRuntime::CopyImage`
-> `scheduler.RequestOutsideRenderPassOperationContext()`
-> `vkCmdCopyImage`

This is no longer a hypothesis.

## Ruled-out alias route hypotheses

For the matched `eden_log(8).txt` runtime:

- generic `ReinterpretImage` route: inactive
- generic `ConvertImage` route: inactive
- direct BytesPerBlock reinterpret fallback: inactive
- `InvalidateResolveShadow`: called but produced zero measured outside-RP events

Do not repeat these splits unless new evidence from a materially different runtime requires it.

## Other confirmed/active performance axes

Keep these separate:

### Draw barriers — CONFIRMED

`other/post-copy-barrier` owns the reason-level Draw barriers.

It is not the dominant alias outside-RP owner.

### Persistent Uniform pressure — STRONG

The latest 960–1560 windows still showed roughly:

- 8,666,347 Uniform upload requests
- 3,516.7 MiB
- ~425 bytes/request
- ~12,037 requests/frame

Tiny Uniform traffic remains a separate normal ~20 FPS ceiling candidate.

### Severe dips — COMPOSITE

The slowest windows still add bulk staging upload, Vertex/Index copy spikes and texture refresh activity on top of the persistent Uniform + alias-copy burdens.

Do not force these into one root cause.

## What NOT to do next

- do not split Vulkan `CopyImage()` further
- do not blindly suppress `RequestOutsideRenderPassOperationContext()`
- do not skip alias copies based only on intuition
- do not change alias dirty/up-to-date state without runtime evidence
- do not alter `modification_tick`
- do not combine the Uniform investigation with the next alias experiment
- do not start an ARM64 build during source preparation without fresh permission

`vkCmdCopyImage` must execute outside a render pass, so the next opportunity is likely reducing unnecessary **copy requests**, not deleting a required render-pass transition around a necessary copy.

## NEXT ACTION

Follow `NEXT_ACTION_ALIAS_SYNC_REDUNDANCY.md`.

High-level objective:

**Determine whether `SynchronizeAliases()` repeatedly requests the same direct image copy without new source content.**

Next task should:

1. create `exp/x1-alias-sync-redundancy` from the completed alias-copy branch
2. inspect exact dc95 alias/modification semantics before coding
3. add passive bounded telemetry around alias-copy requests only
4. measure unique/repeated src-dst pairs, same-frame/same-Draw repetition, source modification state and copy-region signatures
5. retain the proven direct-vk-copy categories for cross-checking
6. prepare a manual-only ARM64 workflow and static/preflight validation
7. update this handoff
8. stop **before running Actions**

Only after the user gives a fresh explicit build permission may exactly one ARM64 attempt be started.

## Current safety state

- current completed experiment: `exp/x1-alias-copy-reasons`
- successful alias workflow attempts: 1
- additional alias build attempts after success: 0
- gameplay behavior change: none
- copies skipped: none
- barriers suppressed: none
- render-pass requests suppressed: none
- optimization A/B selected: none
- next diagnostic build authorization: **not granted**
