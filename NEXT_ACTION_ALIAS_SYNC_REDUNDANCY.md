# NEXT ACTION — Alias Synchronization Redundancy Diagnostic

Updated: 2026-08-27 KST

Status: **ARM64 diagnostic build succeeded / runtime evidence pending**

## Fixed starting point

Repository: `npark2860-cyber/Eden-Adreno-Lab`

Exact Eden source:

`dc95cd09eea9749250fe31a3072684d341d19417`

Current experiment:

`exp/x1-alias-sync-redundancy`

Parent completed alias-route HEAD:

`26728e59c31c36a20ba1dc9d11e8a84e8d67cb74`

## Proven motivation

Matched alias-route runtime (`eden_log(8).txt`) established:

- direct-route: 100,021 scopes
- direct-resolve-invalidate: 100,021 scopes / outside 0
- direct-vk-copy: 100,021 scopes / outside 24,806
- reinterpret-route: 0
- convert-route: 0
- direct-bpb-reinterpret: 0
- whole-log attributed Draw outside-RP: 39,017
- direct-vk-copy share: **63.58%**

Resolved chain:

`SynchronizeAliases -> CopyImage -> TextureCacheRuntime::CopyImage -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

Do not reopen Vulkan route attribution in this experiment.

## Diagnostic build result — SUCCESS

Exactly one authorized ARM64 attempt was launched.

- workflow: `Build dc95 X1 Alias Sync Redundancy`
- run: `33024690895`
- job: `98363162523`
- attempt: `1`
- build head: `804f394c5db280f842a01113e6ca92f7ad57d219`
- result: **success**
- preflight: **success**
- configure: **success**
- ARM64 build/link: **success**
- package: **success**
- upload: **success**
- artifact: `Eden-dc95-X1-alias-sync-redundancy`
- artifact id: `9628554127`
- size: `31,300,012` bytes
- SHA-256: `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

The temporary one-shot branch `push` trigger was removed after launch. Workflow state is back to `workflow_dispatch` only. The branch has exactly one Actions run for this experiment; no rerun occurred.

## Telemetry now available at runtime

New aggregate marker:

`[X1-ALIAS-SYNC]`

Fields:

- `copies`
- `uniquePairs`
- `sameFrame`
- `sameDraw`
- `consecutiveFrame`
- `sameSrcTick`
- `advancedSrcTick`
- `regressedSrcTick`
- `sameSignature`
- `sameStateSignature`
- `regions`
- `maxRegions`
- `tableOverflow`

Bounded pair tracker:

- 4,096 entries
- 32-probe cap
- cleared/rotated at each report boundary
- no unbounded growth

Existing alias route, barrier, Uniform, Vertex, Index and refresh telemetry remains enabled for cross-check.

## Safety contract

This build is measurement-only. It does not:

- skip/deduplicate/cache alias copies
- alter `modification_tick`
- suppress `RequestOutsideRenderPassOperationContext()`
- suppress barriers
- batch `vkCmdCopyImage`
- reorder Draw work
- change Draw/Dispatch A/B defaults

## NEXT ACTION — collect matched runtime

Run `Eden-dc95-X1-alias-sync-redundancy` with:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- driver 512.863.0
- `X1 Log: Scheduler / Sync` = ON
- `X1 Log: Upload / Barrier` = ON
- `X1 A/B Skip Draw` = OFF
- `X1 A/B Skip Dispatch` = OFF
- a comparable field route containing normal ~20 FPS and slower sections when practical

Collect and provide the resulting Eden log containing `[X1-ALIAS-SYNC]`.

Then compare the new alias-sync request counters against the retained direct-route/direct-vk-copy totals.

### Decision rules

- High `sameStateSignature`, especially high `sameFrame`/`sameDraw`: supports a later **separate one-variable A/B** for only the proven repeated subset.
- Mostly `advancedSrcTick`: repeated copies are generally justified by source version advances; dedupe is not supported.
- Mostly unique pairs: move next diagnostic toward alias-set churn / why many aliases become synchronization candidates.
- Non-zero `tableOverflow`: treat repeat ratios as lower-bound/incomplete classification.
- Same source tick is Eden version-state evidence only, not independent byte-equality proof.

Do **not** implement copy skipping before runtime evidence.

## Build authorization boundary

Current ARM64 attempts for this experiment: **1**.

Attempt 1 succeeded.

**No second build or rerun is authorized. Fresh explicit user authorization is required for any additional ARM64 attempt.**
