# COMPLETED — X1 Guest Post Wait Attribution

Updated: 2026-08-28 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-guest-post-wait-attribution`

Experiment cleanup/code HEAD before documentation:

`d9df8d7f594c3030ee518a2bd489a15708ad87b4`

**No ARM64 build/rebuild/rerun without fresh explicit user authorization. Current authorization: NONE.**

## Build completed

Approved corrected build:

- run `33150086343`
- job `98779808729`
- build HEAD `d4cbe0ba893a61650583926434261565242bca3f`
- conclusion `success`
- artifact `Eden-dc95-X1-guest-post-wait-attribution`
- artifact id `9678004761`
- size `31,349,148` bytes
- SHA-256 `4c310923a53b3cfd337893329b1fbd41e317a79200139ae559064a520e882ee9`

The earlier run `33149694136` failed before ARM compilation because the wrapper selected WSL `bash` rather than Git Bash. It was not an experiment/compiler failure.

Persistent workflow remains:

`.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml`

with `workflow_dispatch` only. Corrected one-shot workflow/marker were removed.

## Runtime completed

Runtime log:

`eden_log(20260828-080040).txt`

Primary result:

> The dominant guest submitter's previous NVDRV completion -> next candidate request interval is overwhelmingly KThread Waiting, not CPU execution and not nvservices IPC dispatch.

Representative:

- fast frame 840: `windowAvg=16.929 ms`, `waitShare=96.05%`, `Arbitration=1.030 ms/frame`
- transition frame 960: `windowAvg=37.144 ms`, `waitShare=98.57%`, `Arbitration=57.526 ms/frame`
- slow frame 1080: `windowAvg=26.587 ms`, `waitShare=98.82%`, `Arbitration=26.751 ms/frame`
- slow frame 1200: `windowAvg=29.312 ms`, `waitShare=98.04%`, `Arbitration=50.103 ms/frame`
- slow frame 1320: `windowAvg=24.249 ms`, `waitShare=98.89%`, but `Arbitration=8.615 ms/frame` and `None=40.741 ms/frame`

Thus AddressArbiter wait growth correlates strongly with many slow windows, but **Arbitration alone is not yet the final root cause** because a stable-slow counterexample is dominated by `None` wait.

## Profiler correctness resolved

- exact dc95 `BeginWait()` enters Waiting before the caller sets its debug reason.
- the profiler classifies at wait exit using the old wait reason captured before `SetState()` clears it.
- therefore recorded `Arbitration` time is valid despite reason assignment following `BeginWait()`.
- `topSvc0=0x0` is invalid attribution: `current_svc_id` is declared but not populated in exact dc95, and this transplant installed no SVC-ID recorder.
- reply-wake exclusion counters are count-consistent with candidate request counts in steady windows.

## Exact source mapping resolved

`ThreadWaitReasonForDebugging::Arbitration` maps to the AddressArbiter blocking path:

`Svc::WaitForAddress` (`0x34`)
-> `KAddressArbiter`
-> `WaitIfLessThan` / `DecrementAndWaitIfLessThan` / `WaitIfEqual`.

Wake side:

`Svc::SignalToAddress` (`0x35`).

Mutex `ArbitrateLock` and process-wide condition-variable waits are tagged `ConditionVar`, not `Arbitration`.

The repeated `arbN=120` therefore means exactly one completed AddressArbiter wait per rendered frame for the target submitter in every non-startup report.

## Final status

This experiment is complete. Full runtime table, source review, instrumentation defect analysis and next-boundary design are recorded in:

`DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`

Next action:

`NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md`

Do not rebuild this pass. No ARM64 authorization exists.