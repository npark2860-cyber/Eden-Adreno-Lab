# DEBUG HISTORY — Waker Stage G ARM64 Precheck Failure

Updated: 2026-08-29 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- branch: `exp/x1-waker-stage-g-producer-cpu-attribution`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- Stage G Ubuntu static validation: run `33242026006`, job `99072879855`, success

## Approved ARM64 attempt

One fresh explicit Stage G ARM64 authorization was consumed.

- workflow: `Build dc95 X1 Waker Stage G`
- run: `33243420048`
- job: `99076555976`
- attempt: `1`
- build HEAD: `1b0acbb63776e43a0555566aa30aca450bfff19c`
- event: `push`
- conclusion: `failure`
- rerun/retry: none

The persistent workflow was restored to manual-only `workflow_dispatch` immediately after the run was created.

## What passed

Before failure, the Windows ARM64 runner successfully completed:

- Adreno Lab checkout
- Eden CI workflow checkout
- exact dc95 Eden checkout
- exact dc95 SHA verification
- retained non-scheduler patch reconstruction
- retained X1 diagnostic chain reconstruction
- focused attribution reconstruction through Stage C
- Stage D application
- Stage E application
- Stage F application
- pre-Stage-G invariant snapshot
- Stage G focused producer CPU attribution transplant

## Failure point

Failure occurred in `Verify Stage G before configure`, before MSYS2 setup, configure, compile, packaging, or artifact upload.

Exact exception:

`FileNotFoundError: [Errno 2] No such file or directory: '\\tmp\\stage-f-pre-g.h'`

Cause:

- the snapshot step used Git Bash `/tmp/stage-f-pre-g.h`;
- the verification step invoked native Windows Python;
- `Path('/tmp/stage-f-pre-g.h')` was interpreted as `C:\\tmp\\stage-f-pre-g.h` instead of Git Bash's `/tmp` mapping.

This is a workflow path portability bug. It is not evidence of a Stage G instrumentation failure and no C++ compilation was attempted.

## Fix applied after the failed attempt

Persistent workflow was updated without running ARM64 again:

- fix commit: `49120c82777d2c8156336bef9439dc3ad3a7cccf`
- pre-G snapshots now use repository-workspace-relative `.x1-stage-g-precheck/` paths;
- Bash checks, diffs, and native Python all reference the same relative paths;
- workflow remains `workflow_dispatch` only.

No Stage G profiler/transplant/analyzer source changed as part of this fix.

## Authorization state

The approved ARM64 attempt was consumed by run `33243420048`.

Current ARM64 authorization: **NONE**.

A new explicit authorization is required before any Stage G ARM64 retry/rebuild/rerun.
