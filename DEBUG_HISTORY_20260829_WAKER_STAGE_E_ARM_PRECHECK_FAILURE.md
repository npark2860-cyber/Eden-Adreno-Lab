# DEBUG HISTORY — Stage E ARM64 Pre-Configure Validation Failures

Date: 2026-08-29 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-waker-stage-e-recursive-arbiter`

Both ARM64 attempts below were separately and explicitly authorized. Each approval was consumed by exactly one workflow attempt. No rerun/retry occurred.

Current ARM64 authorization: **NONE**.

## Attempt 1 — workflow guard typo

- workflow: `Build dc95 X1 Waker Stage E`
- run: `33230457489`
- job: `99042246285`
- attempt: `1`
- event: `push`
- build HEAD: `0bab539c886a0c7b18be7ebe41476e81b7127a75`
- conclusion: `failure`

Passed before failure:

- exact dc95 checkout / HEAD verification
- retained diagnostic reconstruction
- focused Stage A through C reconstruction
- Stage D application
- Stage E application

Failure point:

`Verify Stage E before configure`

Exact cause:

The workflow checked nonexistent:

`TopSlotCount = 4`

The validated Stage E header actually defines:

- `TopWaitCount = 4`
- `TopSignalCount = 4`

Therefore MSYS2, configure, ARM64 C++ compile, package and upload were all skipped. No artifact was produced.

## Attempt 2 — second workflow guard typo

A fresh explicit approval authorized a second and only second attempt.

- workflow: `Build dc95 X1 Waker Stage E`
- run: `33230727557`
- job: `99042975831`
- attempt: `1`
- event: `push`
- build HEAD: `72ca7f189611e24acb74494b63bbdeeba0ee73f5`
- conclusion: `failure`

Again, exact dc95 checkout, retained reconstruction, Stage A-D reconstruction and Stage E transplant all completed successfully.

Again the run stopped at:

`Verify Stage E before configure`

MSYS2, configure, ARM64 compile, package and upload were skipped. No artifact was produced.

Exact cause:

The first typo had been corrected, but the ARM workflow still checked:

`ShouldTrackSignalAddress`

The actual Stage E API is:

`ShouldTrackPromotedSignalAddress`

The transplant itself uses that correct method and had already passed the original Stage E Ubuntu static validation.

## Guard audit after attempt 2

After the second attempt, no further ARM64 run was allowed or started.

The Stage E transplant was inspected directly. It confirmed the actual generated hook forms:

- `Core::X1WakerStageEProfiler::Get().BeginWait(...)`
- `Core::X1WakerStageEProfiler::Get().EndWait(...)`
- local variable `x1_stage_e_profiler`
- `x1_stage_e_profiler.RecordSignal(...)`
- predicate `ShouldTrackPromotedSignalAddress(...)`

This exposed another latent problem in the old ARM guard: it searched for `X1WakerStageEProfiler::Get().RecordSignal`, a form that the transplant does not generate.

The old ARM guard also compared cumulative Stage A-D+E source directly against exact dc95 for behavior-token checks. That is broader than the intended Stage E invariant and can false-positive on retained diagnostics.

## Hardened validation design

The persistent ARM workflow was changed, while remaining manual-only, to mirror the already-successful Stage E static methodology:

1. reconstruct through Stage D;
2. snapshot pre-Stage-E `svc_address_arbiter.cpp` and `vk_rasterizer.cpp`;
3. record pre-Stage-E counts for:
   - `WaitAddressArbiter(address...)`
   - `SignalAddressArbiter(address...)`
   - `IsValidArbitrationType`
   - `IsValidSignalType`
4. apply Stage E;
5. validate Stage E markers and exact hook counts;
6. compare call/helper counts against the pre-Stage-E snapshot;
7. run behavior-changing diff guards only against the pre-Stage-E snapshot, not against cumulative exact-dc95 diff.

The corrected generated-hook guards now check:

- `TopWaitCount = 4`
- `TopSignalCount = 4`
- `ShouldTrackPromotedSignalAddress`
- exactly one `Get().BeginWait`
- exactly one `Get().EndWait`
- exactly one `x1_stage_e_profiler.RecordSignal`

Persistent ARM workflow hardening commit:

`34c5d3e563c77395ea8d0834e67b3b210fa8406f`

No ARM64 run was triggered by this change.

## Ubuntu parity validation

A temporary Ubuntu-only workflow reproduced the hardened ARM pre-configure reconstruction and guard block.

First parity run, before full hardening:

- run `33230840202`
- job `99043279158`
- conclusion `failure`

This was useful because it reproduced the remaining bad guard without consuming ARM64 authorization.

After converting the guard to the pre-Stage-E snapshot model and correcting the generated hook form, parity was rerun:

- run `33230953769`
- job `99043581687`
- attempt `1`
- conclusion **`success`**

Successful parity passed:

- exact dc95 checkout
- retained diagnostic chain reconstruction
- Stage A-D reconstruction
- pre-Stage-E snapshot
- Stage E application
- exact dc95 HEAD preservation
- `git diff --check`
- Stage E marker/API checks
- exact Stage E BeginWait / EndWait / RecordSignal hook counts
- WaitAddressArbiter / SignalAddressArbiter call-count preservation against pre-E
- arbitration/signal validation-helper count preservation against pre-E
- no Stage-E-added kernel wait/yield/reschedule/priority/core-mask behavior
- no Stage-E-added QueueBuffer/swap/fence behavior

The temporary parity workflow was removed after success.

## Current state

Stage E source/transplant remains unchanged and statically validated. The two ARM attempts failed **before configure and before compilation due workflow-only validation mistakes**; neither provides evidence of a C++ compile failure.

Persistent ARM workflow is manual-only and its hardened pre-configure guard has now been reproduced successfully on Ubuntu.

A new ARM64 attempt requires a **fresh explicit one-attempt authorization**. Do not reuse either prior approval.
