# NEXT ACTION — Qualcomm/X1 adaptive Uniform cache A/B

Updated: 2026-08-27 KST

## Purpose

Test whether the steady ~20 FPS ceiling is causally driven by exact-dc95 Vulkan's adaptive small-Uniform fast-stream policy.

Current evidence already shows:

- graphics Uniform processing is overwhelmingly fast mapped-stream traffic
- measured gameplay `fastAlignment=0`
- measured fast traffic is entirely adaptive `fastSkip`
- classic cached traffic is mostly clean / zero-upload
- repeated exact Uniform identities dominate across Draws
- sampled repeated identities overwhelmingly carry the same payload fingerprint

The next step must therefore be a controlled A/B of **policy selection**, not a custom payload dedupe.

## Fixed baseline

- Lab repo: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Current diagnostic branch: `exp/x1-uniform-payload-fingerprint`
- Latest successful diagnostic build HEAD: `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- Latest artifact: `Eden-dc95-X1-uniform-payload-fingerprint`
- Artifact id: `9634160587`
- Artifact SHA-256: `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

Do not move the Eden source baseline.

## Required new branch

Create a fresh experiment branch from the current restored payload-fingerprint branch HEAD, suggested name:

`exp/x1-uniform-cache-ab`

Do not modify the immutable control branch.

## A/B control semantics

Add one Qualcomm/X1 diagnostic checkbox, default OFF.

Suggested meaning:

`X1 A/B: Disable Adaptive Uniform Fast Stream`

Exact behavior:

### OFF

Must preserve exact existing dc95 behavior.

The current decision remains:

- alignment-required stream can select fast path
- adaptive small-buffer `fastSkip` can select fast path
- current staging/descriptor/guest-copy behavior is untouched

### ON

Change only the adaptive small-buffer policy decision:

- `needs_alignment_stream` remains authoritative and must still use fast mapped streaming
- adaptive `fastSkip` must not select mapped streaming
- the Uniform must fall through to the already-existing classic cached path
- the classic path must continue using existing `SynchronizeBuffer()` dirty-range logic

Do **not** add a new payload cache or reuse a previous staging allocation in this experiment.

## Hard safety boundaries

The A/B must not change:

- exact Eden source baseline
- memory tracker dirty semantics
- `SynchronizeBuffer()` behavior
- buffer aliasing semantics
- descriptor lifetime
- staging allocation lifetime
- command-buffer resource lifetime
- barriers
- render-pass begin/end behavior
- `RequestOutsideRenderPassOperationContext()` behavior
- scheduler source or wait semantics
- alias synchronization / `CopyImage`
- Vertex/Index/Storage paths
- alignment-required Uniform streaming

Do not enable `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS` as part of this experiment.

Do not implement same-key/hash dedupe as part of this experiment.

## Instrumentation to retain

Keep all currently useful passive telemetry so the A/B can be interpreted against previous runs:

- `[X1-FLOW]`
- `[X1-BUFFER]` / buffer-category correlation
- `[X1-ALIAS-SYNC]`
- `[X1-UNIFORM-PATH]`
- `[X1-UNIFORM-PAYLOAD]`

Add only minimal A/B-specific counters if necessary to prove how many visits were redirected from adaptive fast streaming into the classic cached path.

Useful counters:

- eligible adaptive-fast visits
- redirected-to-classic visits when A/B ON
- cached clean among redirected visits
- cached actual upload among redirected visits

Avoid per-Uniform logging.

## Static validation before any build

Before requesting/using an ARM64 build authorization, verify:

1. exact Eden checkout remains `dc95cd09eea9749250fe31a3072684d341d19417`
2. A/B switch defaults OFF
3. OFF path is source-equivalent to existing behavior
4. ON changes only adaptive `fastSkip` selection
5. `needs_alignment_stream` still forces fast streaming
6. no scheduler file is touched
7. no render-pass/barrier/outside-operation code is touched
8. no alias-copy code is touched
9. no dirty-state mutation is introduced
10. no staging/descriptor lifetime code is modified
11. no previous-payload reuse/dedupe appears in the diff
12. workflow remains manual-only before authorization

## Build rule

**Do not start or rerun ARM64 Actions without fresh explicit user authorization.**

One authorization = exactly one build attempt.

If the build fails, stop and request fresh authorization before any rerun.

## Runtime test matrix after a future successful build

Use the same TOTK 1.4.2 environment and settings used by the current diagnostics.

Minimum useful comparison:

### Run A — A/B OFF

- exact existing behavior
- confirm `[X1-UNIFORM-PATH]` remains dominated by `fastSkip`
- establish matched FPS and workload counters

### Run B — A/B ON

- disable only adaptive Uniform fast streaming
- use the same save / route / options as closely as possible
- record user-observed FPS
- note any new freezing/stutter behavior explicitly
- compare Uniform fast count, cached clean/upload count, uploadReq, outside-RP, barriers, scheduler waits, and severe-dip behavior

If one build contains the runtime checkbox, both A and B should use that same build so code provenance remains identical.

## Decision tree

### FPS materially rises and stability remains good

Strong causal confirmation that adaptive Uniform re-streaming is a major steady-state bottleneck. Next work should preserve cached reuse while preventing stalls, then investigate a production-safe Qualcomm policy.

### FPS materially rises but freezing/stalls appear

The cost is being shifted from continuous re-streaming into synchronization/stall events. This would closely match the observed Ryubing/Kenji tradeoff and makes buffer/resource lifetime and in-flight-range handling the next design problem.

### FPS does not materially improve

The fast-stream counts are visually enormous but are not the dominant frame-time cause. Retain the finding as architectural overhead and return priority to valid alias/render-pass disruption and heavy-scene bulk copy paths.

### Correctness breaks

Do not promote the optimization. Determine whether the classic path exposes a Qualcomm-specific synchronization or stale-data issue before any further performance interpretation.

## Handoff entry point

A new tab should read, in order:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `LAB_BOOTSTRAP.md`
4. this file

Then verify the actual GitHub branch HEAD before editing and begin with **static preparation of `exp/x1-uniform-cache-ab` only**.

Stop before Actions unless the user gives fresh explicit build authorization.
