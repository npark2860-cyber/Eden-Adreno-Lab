# DEBUG HISTORY — 2026-08-28 Guest Post Wait Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- Eden: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- lab branch: `exp/x1-guest-post-wait-attribution`
- experiment cleanup/code HEAD before documentation: `d9df8d7f594c3030ee518a2bd489a15708ad87b4`

The Eden baseline is immutable unless separately approved.

**ARM64 Actions rule: no new build/rebuild/rerun without fresh explicit user authorization. Current authorization: NONE.**

## Guest Post Wait build

Initial one-shot attempt:

- run `33149694136`
- failed before ARM compilation because the wrapper selected WSL `bash` instead of Git Bash on Windows
- not an experiment/compiler failure
- no automatic retry was performed

Approved corrected build:

- workflow/run `33150086343`
- job `98779808729`
- attempt `1`
- build HEAD `d4cbe0ba893a61650583926434261565242bca3f`
- conclusion `success`
- artifact `Eden-dc95-X1-guest-post-wait-attribution`
- artifact id `9678004761`
- artifact size `31,349,148` bytes
- SHA-256 `4c310923a53b3cfd337893329b1fbd41e317a79200139ae559064a520e882ee9`

The corrected one-shot workflow/marker was then removed. Persistent target workflow remains `.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml`, `workflow_dispatch` only.

## Runtime

Log:

`eden_log(20260828-080040).txt`

Environment:

- exact dc95
- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- swap3->2 clamp OFF
- Guest Post Wait / NVDRV IPC Dispatch / Guest Submit / GPU Submit / GPU Command / Frame Build / Dequeue / Cadence logging ON
- Descriptor Ring remained ON, but reports showed `alloc=0`, `reuseWait=0`; this runtime remains usable.

## Full 120-frame Guest Post Wait table

All reason/GPU totals below are normalized by 120 rendered frames. `windowAvg`, `guestPostAvg`, and `ipcDispatchAvg` retain the profiler's per-candidate-request average.

| frame | wall/f ms | windowAvg ms | waitShare | residual/f ms | None/f | Sleep/f | IPC/f | Sync/f | Cond/f | Arbitration/f | Susp/f | arbN | tid | CPU share | guestPostAvg ms | ipcDispatchAvg ms | GPU queueWait/f ms | GPU active/f ms | raw swap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| 120 | 109.587 | 37.279 | 62.60% | 27.999 | 32.324 | 0.086 | 0 | 0 | 0.509 | 13.951 | 0 | 1099 | 0x53 | 1.84% | 20.151 | 0.023 | 94.772 | 5.925 | startup/mixed |
| 240 | 33.471 | 16.719 | 98.18% | 0.608 | 31.575 | 0 | 0 | 0 | 0.0017 | 1.253 | 0 | 120 | 0x53 | 1.52% | 16.694 | 0.025 | 33.141 | 0.328 | 2 |
| 360 | 53.409 | 26.688 | 97.92% | 1.113 | 28.491 | 0 | 0 | 0 | 0.0001 | 23.771 | 0 | 120 | 0x53 | 1.23% | 26.655 | 0.032 | 46.217 | 7.191 | 2 |
| 480 | 33.332 | 16.648 | 98.09% | 0.637 | 31.578 | 0 | 0 | 0 | 0.0001 | 1.080 | 0 | 120 | 0x53 | 1.65% | 16.618 | 0.030 | 32.370 | 0.962 | 2 |
| 600 | 34.169 | 17.188 | 96.94% | 1.054 | 30.726 | 0 | 0 | 0 | 0.0032 | 2.595 | 0 | 120 | 0x53 | 1.56% | 17.168 | 0.020 | 33.656 | 0.511 | 2 |
| 720 | 33.329 | 16.532 | 98.80% | 0.396 | 31.555 | 0 | 0 | 0 | 0.0011 | 1.112 | 0 | 120 | 0x53 | 1.61% | 16.513 | 0.019 | 32.815 | 0.514 | 2 |
| 840 | 33.893 | 16.929 | 96.05% | 1.336 | 31.491 | 0 | 0 | 0 | 0.0017 | 1.030 | 0 | 120 | 0x53 | 1.59% | 16.908 | 0.021 | 33.383 | 0.507 | 2 |
| 960 | 75.533 | 37.144 | 98.57% | 1.078 | 16.613 | 0 | 0 | 0 | 0.0001 | 57.526 | 0 | 120 | 0x53 | 0.95% | 37.112 | 0.031 | 57.908 | 17.622 | transition->3 |
| 1080 | 52.938 | 26.587 | 98.82% | 0.627 | 25.797 | 0 | 0 | 0 | 0.0001 | 26.751 | 0 | 120 | 0x53 | 1.46% | 26.566 | 0.021 | 36.256 | 16.682 | 3 |
| 1200 | 59.915 | 29.312 | 98.04% | 1.174 | 8.568 | 0 | 0 | 0 | 0.0007 | 50.103 | 0 | 120 | 0x53 | 1.33% | 29.290 | 0.022 | 33.400 | 26.513 | 3 |
| 1320 | 50.227 | 24.249 | 98.89% | 0.556 | 40.741 | 0 | 0 | 0 | 0 | 8.615 | 0 | 120 | 0x53 | 1.57% | 24.228 | 0.021 | 32.677 | 17.548 | 3 |

Frame 120 is startup/mixed and must not be used as the steady-state causal reference.

## Runtime conclusion

### Confirmed

For the dominant submitter `tid=0x53`, the previous candidate NVDRV completion -> next candidate request interval is overwhelmingly KThread `Waiting` in normal sampled windows:

- fast windows: waitShare ~96-99%
- transition/slow windows: waitShare ~98-99%
- residual is generally ~0.4-1.3 ms/frame after startup
- submitter CPU share remains ~1-2%
- IPC dispatch remains ~0.02-0.03 ms/request

Therefore the missing guest-post interval is not Runnable CPU work and not nvservices dispatch latency. It is guest KThread wait residency.

### Arbitration correlation

Fast raw-swap-2 windows:

- frame 240: `Arbitration=1.253 ms/frame`
- frame 480: `1.080 ms/frame`
- frame 600: `2.595 ms/frame`
- frame 720: `1.112 ms/frame`
- frame 840: `1.030 ms/frame`

Slow/transition examples:

- frame 360, still raw swap 2: `23.771 ms/frame`
- frame 960 transition to raw swap 3: `57.526 ms/frame`
- frame 1080 stable slow: `26.751 ms/frame`
- frame 1200 stable slow: `50.103 ms/frame`

This is a strong correlation and can precede the raw-swap-3 state, so it is upstream of cadence classification.

### Critical counterexample

Frame 1320 remains stable slow at `50.227 ms/frame`, with `guestPostAvg=24.228 ms`, but:

- `Arbitration=8.615 ms/frame`
- `None=40.741 ms/frame`

Therefore **Arbitration alone is not yet proven to own the entire slowdown**. The correct current conclusion is:

> Guest-post slowdown is KThread Waiting dominated. One once-per-frame AddressArbiter wait frequently expands sharply with slowdown, but unclassified `None` waits can also dominate a slow window.

Do not state that a single AddressArbiter SVC is the root cause until the direct WaitForAddress identity/duration boundary is measured.

## Profiler correctness review

Files reviewed:

- `src/core/x1_guest_post_wait_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_post_wait_attribution.py`
- exact dc95 `KThread`, `KAddressArbiter`, `KConditionVariable`, synchronization and SVC sources

### Wait-reason timing

Exact dc95 `KThread::BeginWait()` calls `SetState(Waiting)` first.

`KAddressArbiter::WaitIfLessThan()` / `WaitIfEqual()` then call `SetWaitReasonForDebugging(Arbitration)` while still under scheduler locking.

The transplant snapshots `x1_old_wait_reason` at the later Waiting -> non-Waiting `SetState()` transition **before** baseline `SetState()` clears the debugging reason. Thus an AddressArbiter wait is classified as `Arbitration` on exit even though its reason is still `None` at the instant of Waiting entry.

Conclusion: the observed `Arbitration` duration is semantically valid; it is not an artifact of the BeginWait/reason-call ordering.

### Why `None` exists

The profiler classifies completed waits using the old debug reason at wait exit. Therefore the large `None` bucket is not explained by `KAddressArbiter` setting its reason immediately after BeginWait.

It means the target thread also traverses Waiting paths for which the debug reason remains `None` through exit. Exact dc95 has BeginWait users that do not necessarily populate a debug reason. The current profiler cannot identify which unclassified call site produced each `None` wait.

### `topSvc0=0x0` is an instrumentation defect

The profiler stores `GetStackParameters().current_svc_id` at Waiting entry. However exact dc95 code search finds `current_svc_id` only in the `KThread::StackParameters` declaration; no recorder populates it, and the transplant script installs no SVC-ID hook.

Therefore `topSvc0=0x0` does **not** mean SVC 0 owns these waits. SVC attribution in this build is nonfunctional and must not be used.

### reply-wake exclusion

Steady windows are count-consistent with the intended exclusion:

- frame 360: `begins=720`, `ends=480`, `ignoredReplyWake=240`
- frame 1080: `begins=722`, `ends=482`, `ignoredReplyWake=240`
- frame 1200: `begins=731`, `ends=486`, `ignoredReplyWake=245`
- frame 1320: `begins=727`, `ends=480`, `ignoredReplyWake=247`

The ignored wake count tracks candidate request count, and begin/end accounting closes apart from report-boundary waits. No orphan/nested/malformed pattern indicates obvious mispairing in the representative windows.

## Exact dc95 Arbitration source mapping

Code search for `ThreadWaitReasonForDebugging::Arbitration` finds one setter path: `KAddressArbiter`.

Blocking path:

`Svc::WaitForAddress` (`SvcId 0x34`)
-> current process `WaitAddressArbiter`
-> `KAddressArbiter::{WaitIfLessThan, WaitIfEqual}`
-> `BeginWait`
-> wait reason `Arbitration`.

Valid WaitForAddress arbitration modes:

- `WaitIfLessThan`
- `DecrementAndWaitIfLessThan`
- `WaitIfEqual`

Wake side:

`Svc::SignalToAddress` (`SvcId 0x35`)
-> current process `SignalAddressArbiter`
-> wakes matching address-arbiter waiters.

Important exclusion:

- `ArbitrateLock` / `ArbitrateUnlock` mutex paths use `KConditionVariable`
- `WaitProcessWideKeyAtomic` / process-wide condition-variable paths also use `KConditionVariable`
- those blocked waits are tagged `ConditionVar`, not `Arbitration`

Therefore the runtime `Arbitration` bucket is specifically an AddressArbiter/WaitForAddress wait, not generic mutex/CV contention.

`arbN=120` in every non-startup report means the target submitter completes exactly one such AddressArbiter wait per rendered frame in these windows. Source alone cannot yet identify the guest address, arbitration mode, timeout, or logical TOTK/SDK synchronization object.

## Next minimal boundary

Do not add a broad scheduler profiler.

Stage A only:

Instrument `Svc::WaitForAddress` for dynamic target `tid=0x53` during the existing guest-post window and aggregate, per 120 frames:

- guest address
- `ArbitrationType`
- timeout
- count
- total/average/max actual blocked duration
- result/timeout status if available without changing semantics

Prefer grouping by `(address, ArbitrationType)` and no per-event log.

This directly replaces the broken `current_svc_id` inference and answers whether the once/frame long AddressArbiter wait is one stable object and how much of each fast/transition/slow window it owns.

Only after one address is proven dominant should Stage B add `SignalToAddress` attribution for that exact address to identify the waking/signaling thread. If a frame-1320-like slow `None` bucket remains dominant after Stage A, the next separate step is a minimal unclassified-BeginWait source tag for `tid=0x53`, not broad scheduler tracing.

## Status

Guest Post Wait Attribution runtime/source analysis is **completed**.

Next action document:

`NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md`

No ARM64 build is authorized.