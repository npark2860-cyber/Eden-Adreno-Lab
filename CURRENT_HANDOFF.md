# CURRENT HANDOFF — Eden Adreno X1 alias synchronization redundancy

Updated: 2026-08-27 KST

## Fixed baseline

- Repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Completed texture experiment: `exp/x1-texture-fill-reasons`
- Completed alias-route experiment: `exp/x1-alias-copy-reasons`
- Current prepared diagnostic branch: `exp/x1-alias-sync-redundancy`

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Repository state verified before this experiment

The completed alias-route branch actual HEAD was verified as:

`26728e59c31c36a20ba1dc9d11e8a84e8d67cb74`

message:

`docs: hand off alias synchronization redundancy work`

The new branch `exp/x1-alias-sync-redundancy` was created directly from that HEAD.

The successful alias-route build itself used the earlier build HEAD documented below; later commits on the completed branch were documentation/workflow-restoration state, not an additional ARM64 build.

## Latest successful diagnostic build

Alias Copy Reasons:

- workflow: `Build dc95 X1 Alias Copy Reasons`
- workflow file: `.github/workflows/build-dc95-x1-alias-copy-reasons.yml`
- run: `33019025980`
- job: `98344461231`
- build head: `eaec1e760057cd284fe379d5fd1bd0009805432d`
- run attempt: 1
- result: **success**
- artifact: `Eden-dc95-X1-alias-copy-reasons`
- artifact id: `9626369486`
- size: 31,298,049 bytes
- SHA-256: `653b232e91aa2a120239106ac991e8b3308b5f95651b6ac0414eda38f2647aef`

The one-shot push trigger used for that authorized build was removed. The completed alias workflow is back to `workflow_dispatch` only.

## Latest matched runtime contract

User tested the successful alias-route build with:

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

The dominant alias outside-RP chain remains:

`Draw Configure`
-> `FillImageViews`
-> `PrepareImage`
-> `SynchronizeAliases`
-> `CopyImage`
-> generic direct route
-> `TextureCacheRuntime::CopyImage`
-> `scheduler.RequestOutsideRenderPassOperationContext()`
-> `vkCmdCopyImage`

This is confirmed and is not being re-split in the current experiment.

## Ruled-out alias route hypotheses

For the matched `eden_log(8).txt` runtime:

- generic `ReinterpretImage` route: inactive
- generic `ConvertImage` route: inactive
- direct BytesPerBlock reinterpret fallback: inactive
- `InvalidateResolveShadow`: called but produced zero measured outside-RP events

Do not restore these as current suspects without materially new runtime evidence.

## Exact dc95 source semantics verified for current diagnostic

### `AliasedImage`

Exact dc95 stores only:

- alias `ImageId`
- `std::vector<ImageCopy>` copy regions

There is no per-alias dirty/up-to-date boolean in `AliasedImage`.

`ImageFlagBits::Alias` is not the freshness gate; `CheckAliasState()` clears it only when the alias list becomes empty.

### `Image::modification_tick`

`MarkModification(ImageBase&)` sets `GpuModified` and assigns:

`image.modification_tick = ++modification_tick`

Exact dc95 can also propagate existing ticks in image join/copy maintenance, and `SynchronizeAliases()` propagates the most recent selected source tick to the destination.

Therefore the current diagnostic treats `modification_tick` as the source's Eden recency/version state, **not** as a content hash or byte-equality proof.

### `SynchronizeAliases()`

For destination `image_id`, an alias is selected only if:

`destination.modification_tick < source.modification_tick`

Selected aliases are sorted by source tick. Before executing their copies, the destination tick is advanced to the maximum selected source tick. The actual request is:

`CopyImage(image_id, aliased->id, aliased->copies)`

The new telemetry is attached immediately before this exact request in the existing alias-copy wrapper.

### Copy regions

`AddImageAlias()` builds the stable `ImageCopy` vectors from source/destination subresources, source/destination offsets and extents. The current diagnostic hashes those exact fields and the region count. It does not invent compressed-format byte volume.

See `ALIAS_SYNC_REDUNDANCY_MAP.md`.

## Current prepared diagnostic — NO RUNTIME YET

Branch:

`exp/x1-alias-sync-redundancy`

Prepared files:

- `tools/adreno_lab/transplant_dc95_alias_sync_redundancy.py`
- `.github/workflows/build-dc95-x1-alias-sync-redundancy.yml`
- `ALIAS_SYNC_REDUNDANCY_MAP.md`

Artifact when a future build is authorized:

`Eden-dc95-X1-alias-sync-redundancy`

New report marker:

`[X1-ALIAS-SYNC]`

### Passive measurements

At the existing report interval, default 120 frames:

- total SynchronizeAliases alias-copy requests
- unique `(dst ImageId, src ImageId)` pairs
- same-pair same-frame repeats
- same-pair same-Draw repeats using a telemetry-only Draw work serial
- consecutive-frame repeats
- same/advanced/regressed source `modification_tick`
- total/max copy-region count
- stable region signature
- same-pair same-signature repeats
- same-pair same-source-tick + same-signature repeats (`sameStateSignature`)
- bounded-table tracking overflow

No per-copy log is emitted.

### Bounded state

- fixed pair table: 4,096 entries
- probe cap: 32
- no dynamic table growth
- table state rotated/cleared at each report boundary

A non-zero `tableOverflow` means some pair-history classification was missed and must be considered when interpreting repeat ratios.

## Existing telemetry retained for cross-check

The prepared build retains:

- `other/texture/alias-copy`
- `other/texture/alias-copy/direct-route`
- `other/texture/alias-copy/direct-vk-copy`
- `other/post-copy-barrier`
- Uniform / Vertex / Index / refresh counters

The new alias request count must be compared with the established direct-route scope order of magnitude on a matched gameplay route.

## Static/preflight state

Direct preparation checks completed without starting Actions:

- GitHub transplant blob `b353167fcf49831d89be2b920c60ae920698f38b` was reproduced byte-for-byte locally with the same `git hash-object`
- that exact Python file passed `python -m py_compile`
- the transplant was executed against a marker fixture matching the outputs of the preceding draw/texture/alias scripts
- required bounded/report/Vulkan/OpenGL/source-tick/region-signature markers were generated
- the existing `CopyImage(dst_id, src_id, copies)` call remained present
- incremental generated diff passed `git diff --no-index --check` with no whitespace errors
- incremental diff scan found no added copy skip/dedupe/batching, barrier/render-pass suppression, `modification_tick` assignment, or `MarkModification()` call
- the new transplant contains no `vk_scheduler` source touch
- a standalone C++20 compile probe for the fixed `std::array`/`std::atomic_flag` tracker pattern passed

The prepared workflow additionally enforces before configure/build:

- exact Eden checkout SHA is dc95
- full transplanted-tree `git -C eden diff --check`
- Draw origin and retained alias route markers
- `[X1-ALIAS-SYNC]` marker
- fixed 4,096-entry table and 32-probe cap
- exact dc95 alias selection/tick semantic markers
- region-signature source fields
- Vulkan bridge and OpenGL no-op bridge
- alias-sync-only forbidden optimization/state-mutation diff scan
- no new scheduler-source touch
- existing exact-dc95 scheduler leak guards

Those workflow gates have not executed yet because no ARM64 run has been authorized.

## Workflow trigger state and GitHub constraint

Prepared workflow trigger:

`workflow_dispatch` only.

There is no `push` trigger, and the current experiment branch has **0 Actions runs**.

Repository default branch is `main`, and `.github/workflows/build-dc95-x1-alias-sync-redundancy.yml` does not exist on `main`. GitHub requires a `workflow_dispatch` workflow file to exist on the default branch before it can receive a manual dispatch. Therefore the branch-local manual-only file is intentionally non-running but is **not directly dispatchable as-is**.

Do not modify/merge `main` merely to make this experiment dispatchable.

For the future single authorized build, use the established main-preserving one-shot mechanism:

1. after explicit authorization only, add a branch-scoped `push` trigger to this prepared workflow
2. the trigger-enabling commit is the one authorized build attempt
3. after that attempt completes, restore the workflow to `workflow_dispatch` only with a workflow-only commit; because the restoring commit no longer contains the `push` trigger, it does not create another build
4. if the attempt fails, restore manual-only state before making any diagnostic fix; do not run the fix without another fresh authorization

## Instrumentation-only safety state

Current prepared diagnostic changes behavior only by collecting telemetry.

It does **not**:

- skip/deduplicate/cache alias copies
- batch `vkCmdCopyImage`
- suppress barriers
- suppress render-pass requests
- alter `modification_tick`
- force aliases up to date
- reorder Draw work
- change Draw/Dispatch A/B defaults

## Other confirmed/active performance axes

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

The slowest windows add bulk staging upload, Vertex/Index copy spikes and texture refresh activity on top of the persistent Uniform + alias-copy burdens.

Do not force these into one root cause.

## What NOT to do next

- do not start Actions without fresh explicit permission
- do not modify `main` just to expose `workflow_dispatch`
- do not split Vulkan `CopyImage()` again
- do not suppress `RequestOutsideRenderPassOperationContext()`
- do not skip a repeated alias copy before runtime evidence
- do not change alias/tick state
- do not combine the Uniform investigation into this alias diagnostic
- do not bring reinterpret/convert/BPB fallback/resolve-shadow invalidation back as current causes

## NEXT ACTION

The source/instrumentation/workflow preparation phase is complete.

The next action is **only after fresh explicit user build authorization**:

1. temporarily add the branch-scoped one-shot `push` trigger to `.github/workflows/build-dc95-x1-alias-sync-redundancy.yml`; that trigger-enabling commit is the single authorized ARM64 attempt
2. if it succeeds, run the same matched TOTK 1.4.2 setup and collect `[X1-ALIAS-SYNC]` plus existing telemetry
3. restore the workflow to `workflow_dispatch` only after the attempt without causing a second run
4. interpret redundancy only after runtime data
5. if the build fails, restore manual-only state and diagnose/fix, but do not run again without another fresh authorization

## Current build authorization state

- current prepared experiment: `exp/x1-alias-sync-redundancy`
- ARM64 runs for this experiment: **0**
- next diagnostic build authorization: **not granted**
- gameplay optimization applied: none
- copies skipped: none
- barriers suppressed: none
- render-pass requests suppressed: none
- `modification_tick` behavior changed: none
