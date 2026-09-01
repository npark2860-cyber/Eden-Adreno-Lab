# NEXT ACTION — ARM64 Exclusive 32-bit Guest-PC Runtime Attribution

Updated: 2026-09-02 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md` for historical Stage K context and hard rules;
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`;
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`;
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_READ_IMPLEMENTED.md`;
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_ATTRIBUTION_IMPLEMENTED.md`;
- this file.

This file and the 2026-09-02 debug-history record supersede older `CURRENT_HANDOFF.md` statements that still describe the three non-common owner pairs as unresolved or name the older Stage K branch as current.

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-arm64-exclusive-pc-attribution`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent Windows ARM64 workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Persistent workflow trigger remains:

`workflow_dispatch` only.

Current ARM64 authorization:

**NONE**

Do not build/rebuild/rerun Windows ARM64 without a fresh explicit user authorization. One authorization means exactly one attempt; failure does not authorize retry.

## Stage K semantic owner status — CLOSED

The recurring non-common owner pairs are already semantically closed:

- `main+0x96e2a8 -> main+0x26936d0` = **`gsys::SystemTask` internal work/phase dispatcher**
- `main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker** owner pair
- `main+0x244fc20 -> main+0x2ad6b20` = **`ActorAIGroupMgr::Job`**

Runtime correlation keeps `gsys::SystemTask` and EventModuleSubWorker higher priority than ActorAIGroupMgr::Job.

Do not reopen semantic owner mapping merely to add stack depth.
Do not create Stage L.

## ARM64 exclusive-write / STXR runtime — CLOSED

Earlier STXR runtime excluded the initial strong suspicion that slowdown was caused by a retry storm or a dramatic STXR per-call latency increase.

Do not reopen STXR retry-storm or STXR per-call slowdown without new evidence.

## ARM64 exclusive-read / LDXR runtime — CLOSED FOR TOTAL COST

Authorized LDXR+STXR build/run:

- workflow run `33524417121`
- attempt `1`
- workflow head `1e1c8bc4574e3e8540630756eb8417a43d874577`
- result: **SUCCESS**
- retry/rerun: none

Runtime log:

`eden_log(20260901-155830).txt`

Exact runtime identity remained:

- Eden `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- main NSO build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- Qualcomm Adreno X1-85

Closed findings from the compared fast/slow windows:

1. LDXR `ReadAndMark` accounts for roughly **47%** of measured exclusive read+write time.
2. Combined selected-producer exclusive read+write aggregate CPU time increased from about `3.458 ms/frame` to `4.571 ms/frame`, about **1.322x**. This is aggregate producer CPU, not serial frame stall.
3. The major amplification is operation-count growth rather than a large per-operation latency spike.
4. P0 read/write attempts increased about **1.20x**; P1 about **1.25x**.
5. Roughly **94-96%** of measured exclusive time is **32-bit** traffic.
6. STXR failure-rate growth is small; no retry storm.
7. Exclusive read+write is material, roughly `10-12%` of selected-producer CPU wall in representative slow windows, but it is not the sole slowdown owner.

Therefore total LDXR/STXR cost is no longer the unknown. The unresolved question is **which guest instruction sites own the extra 32-bit traffic**.

## Exact guest-PC attribution — IMPLEMENTED / STATICALLY VALIDATED

Current branch adds a separate sampled PC layer without changing the existing exact `[X1-XEXCL]` totals.

New log prefix:

`[X1-XEXCLPC]`

Exact guest PC is obtained from the A64 IR's already-existing `ImmCurrentLocationDescriptor()` attached to the exclusive instruction. The ARM64 read callback now diagnostically receives that location descriptor and decodes its exact A64 PC.

No RunThread-entry PC guess and no guest stack walk is used.

Current PC layer scope:

- selected Stage F producers only;
- **32-bit LDXR only**;
- sample rate `1/16`;
- fixed `512` PC slots per producer;
- bounded probe count `8`;
- top `12` PC sites per 120-frame report;
- separate sampled counters from exact LDXR/STXR totals;
- analyzer normalizes runtime absolute PCs with `[X1-WAKERH]` module ranges to durable `module+offset`.

Successful exact-dc95 Ubuntu static validator:

- run `33531976983`
- result: **SUCCESS**

The first validator run `33531722117` applied both transforms successfully but failed a verifier-only string-count assertion; the assertion was corrected and the second run passed. The temporary validator workflow was then deleted.

Final implementation diff before documentation contained only:

- `src/core/x1_arm64_exclusive_pc_profiler.h`
- `tools/adreno_lab/analyze_x1_arm64_exclusive_pc_attribution.py`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_pc_attribution.py`
- minimal chain change in `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

No persistent workflow change remains.
No baseline change occurred.
No ARM build was started for this PC layer.

## Immediate next action

Current ARM64 authorization:

**NONE**

A fresh explicit user authorization is required.

If authorized:

1. perform exactly one Windows ARM64 build/run attempt from `exp/x1-arm64-exclusive-pc-attribution`;
2. do not retry if it fails;
3. collect a runtime log containing `[X1-XEXCLPC]`, existing `[X1-XEXCL]`, `[X1-WAKERH]`, and Stage K records;
4. identify fast/slow windows from the actual cadence of that same run rather than copying frame IDs blindly;
5. run `analyze_x1_arm64_exclusive_pc_attribution.py`;
6. normalize top sites to `module+offset`;
7. for dominant `main+offset` sites, use the exact TOTK 1.2.1 main NSO to map each LDXR PC to enclosing function/owner;
8. compare fast vs slow sampled count/time per PC and determine which sites account for the extra 32-bit exclusive traffic;
9. specifically test whether the added traffic belongs to `gsys::SystemTask`, EventModuleSubWorker, ActorAIGroupMgr::Job, or a different owner.

## Stop condition

Without fresh ARM authorization, stop here.

Do not automatically dispatch Windows ARM64.
Do not rerun a failed ARM attempt.
Do not create Stage L.
Do not implement a behavior-changing optimization before guest-PC ownership of the extra exclusive traffic is established.
