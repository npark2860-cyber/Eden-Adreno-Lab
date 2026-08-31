# DEBUG HISTORY — Stage K Work-Target Helper Shadow Fix / Static Validation

Updated: 2026-08-31 KST

## Scope

Close the deterministic `-Wshadow` compile blocker from the first Windows ARM64 build attempt of the Stage K x26 work-target identity extension.

Fixed Eden baseline remains immutable:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No Windows ARM64 build, rebuild, rerun, workflow dispatch, or runtime attempt was performed by this fix/validation step.

## Failure being repaired

Canonical prior failure record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_ARM_BUILD_FAILURE.md`

The failed authorized ARM attempt was:

- run: `33351947642`
- job: `99366911164`
- attempt: `1`
- build/source HEAD: `5fa3b5fb59c5935eb9d48c4d6ea8f0faa52373c7`
- result: **FAILURE**
- artifact: none
- retry/rerun: none

Actual compile failure category:

`-Werror,-Wshadow`

The compatibility wrapper emitted a local helper whose first parameter was named `x1_stage_k_node`, conflicting with an already-live outer local of the same name in generated `k_scheduler.cpp`.

## Minimal source repair

Modified file only:

`tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

Repair commit:

`b22306fa55690e99aac94f521d302caa27893754`

Exact repair:

- helper first parameter renamed from `x1_stage_k_node` to `x1_stage_k_node_value`;
- only the three helper-body references to that parameter were updated:
  - zero-node test;
  - alignment test;
  - scheduler-node slot construction.

Unchanged:

- saved-x26 source and resolver pointer chain;
- selected-producer scope;
- guest-context capture count;
- guest-memory read count;
- range-validation count;
- work-pair histogram layout;
- 64-slot bound and top4 report shape;
- dynamic main normalization;
- static ModuleSystem semantic map;
- scheduler behavior;
- GPU behavior;
- waits/signals;
- QueueBuffer/cadence behavior;
- persistent Windows ARM workflow trigger;
- fixed baseline.

## Ubuntu/static regression validation

The historical Stage K Ubuntu reconstruction validator was restored temporarily and strengthened with an explicit shadow regression gate.

Temporary validator commit:

`72e32bbbfd4454f2fdbd9465fb5bf1b0be5ba557`

Workflow:

`Validate dc95 X1 Waker Stage K`

Run:

`33392096685`

Job:

`99487889955`

Attempt:

`1`

Runner:

`ubuntu-latest`

Result:

**SUCCESS**

The core job step `Reconstruct A-J and validate Stage K` completed successfully.

Validation covered:

- exact dc95 baseline checkout;
- retained diagnostic chain reconstruction through Stage J;
- Stage K compatibility wrapper application;
- existing Stage K structural/read/range/invariant checks;
- `git diff --check`;
- Python syntax checks;
- selected-producer guard preservation;
- no behavior-changing scheduler/GPU tokens;
- generated-source regression assertions:
  - `u64 x1_stage_k_node,` absent;
  - `u64 x1_stage_k_node_value,` present;
  - all three helper-body parameter references use `x1_stage_k_node_value`.

Therefore the specific deterministic helper-parameter `-Wshadow` defect is closed at the static/generated-source level.

This validation is not Windows ARM64 compile proof and does not consume ARM authorization.

## Temporary validator cleanup

The temporary push validator was deleted immediately after success:

`75c9671aa0c5387e3a9b56fc18d4c216980bfdbe`

It must not remain as a persistent automatic workflow.

The persistent Windows ARM workflow remains separate and manual:

- path: `.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`
- name: `Build dc95 X1 Waker Stage K`
- trigger: `workflow_dispatch` only.

## Current decision

The source repair requested by `NEXT_ACTION_WAKER_STAGE_K.md` is complete and Ubuntu/static validated.

Current ARM64 authorization remains:

**NONE**

The project is now at the fresh ARM authorization gate.

Do not rerun failed run `33351947642` or job `99366911164`.

A future fresh explicit authorization permits exactly one new Windows ARM64 attempt. Failure never authorizes an automatic retry.

If that future build succeeds and produces a runnable artifact, the next user test is Res1X with Stage K work-target fields, followed by strict swap2 `960/1080` versus swap3 `1320/1440/1560/1680` work-target attribution.

Do not create Stage L. Do not implement a behavior-changing optimization before runtime work-target identity is observed.
