# DEBUG HISTORY — Waker Stage G Focused Producer CPU Attribution

Updated: 2026-08-29 KST

## Basis

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage F runtime source:

`eden_log(20260829-073615).txt`

Stage F established a mixed producer slowdown for the two dynamically selected signalers of the promoted AddressArbiter key:

- producer 0 estimated guest CPU slow-fast: about `+3.434 ms/interval`
- producer 1 estimated guest CPU slow-fast: about `+3.904 ms/interval`
- producer 0 Arbitration slow-fast: about `+2.381 ms/interval`
- producer 1 Arbitration slow-fast: about `+2.881 ms/interval`
- runnable-unscheduled growth remained small
- host scheduler starvation remained closed as the primary producer owner

The CPU branch is therefore the priority Stage G target, while the producer Arbitration branch remains open.

Observed Stage F TIDs and promoted guest VA are runtime observations only. They are not hardcoded in Stage G.

## Branch / pre-G snapshot

Stage G branch:

`exp/x1-waker-stage-g-producer-cpu-attribution`

Created exactly from Stage F handoff HEAD:

`4281991be0790584247de71c071e04c4374a6d74`

That commit is the pre-G repository snapshot.

The Ubuntu validation additionally snapshots the reconstructed exact-dc95 pre-G copies of:

- `src/core/x1_waker_stage_f_profiler.h`
- `src/core/hle/kernel/k_scheduler.cpp`
- `src/video_core/renderer_vulkan/vk_rasterizer.cpp`

before Stage G is applied.

## New files

- `src/core/x1_waker_stage_g_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_g_attribution.py`
- `tools/adreno_lab/analyze_x1_waker_stage_g_attribution.py`

New runtime marker:

`[X1-WAKERG]`

## Dynamic identity reuse

Stage G does not rediscover producer threads.

During the Stage G transplant, Stage F receives one read-only accessor:

`GetTrackedProducerIndex(thread_id)`

It returns only the producer slot already armed by Stage F's dynamic promoted-address/top-two producer selection.

Therefore Stage G inherits Stage F identity selection and does not contain:

- observed `0x80`
- observed `0x81`
- observed `0x210...` promoted guest address
- any other fixed runtime producer identity

## Exact CPU-slice attribution point

Stage G instruments exact dc95:

`KScheduler::SwitchThread`

The selected hook is the same switch where exact dc95 performs:

`cur_thread->AddCpuTime(m_core_id, tick_diff)`

For the switched-out thread only:

1. Stage G first asks Stage F whether the current TID is one of the two armed producers.
2. Only when that dynamic check succeeds does it read `cur_thread->GetContext()`.
3. The already-saved guest `pc` and `lr` are attributed to the exact `tick_diff` being charged to the thread CPU total.

The guest context has already been saved by the scheduler unload path before `SwitchThread`, so the PC/LR sample corresponds to the completed producer CPU slice rather than an all-thread periodic sample.

A matching selected-producer switch-in hook records slice start timing. No PC/LR is sampled on switch-in.

## No all-thread PC sampler

The Stage G scheduler hook exists at the context-switch accounting point, but guest PC/LR is read only inside:

`Stage F selected producer -> true`

Non-selected threads do not have their guest context sampled by Stage G.

There is:

- no timer PC sampler
- no all-thread PC trace
- no all-SVC profiler
- no per-switch log output
- no broad profiler

## Fixed-size aggregation

Each of the two producer slots has a fixed `64`-entry `(PC, LR)` context table.

Per context Stage G aggregates:

- completed CPU slice count
- exact scheduler CPU ticks
- observed switch-in -> switch-out steady-clock wall duration

Every `120` rendered frames Stage G reports only the top `4` PC/LR contexts by CPU ticks for each producer.

Additional counters:

- unknown PC slices/ticks/wall time
- context-table overflow slices/ticks/wall time
- producer identity switches
- missing switch-in anchors
- malformed switch-in anchors
- malformed negative tick deltas
- scheduler clock/tick mismatch sanity counter
- latest priority / active core / current core

No per-event log is emitted.

## Clock-domain interpretation

`cpuTicks` is the primary Stage G CPU attribution quantity.

It is the exact `tick_diff` that exact dc95 adds through `KThread::AddCpuTime()`, so it is in the same scheduler/CoreTiming CPU accounting domain used by Stage F `GetCpuTime()` deltas.

`cpuWall` is separately the steady-clock duration observed between the selected producer's switch-in and switch-out. It is useful as a sanity measure, but it is not a replacement for Stage F's signal-interval `ScaleTicksToNs()` estimate.

For Stage G runtime interpretation:

- use CPU ticks and PC/LR tick shares as the canonical callsite attribution;
- compare multi-window aggregate trends, not one slice;
- retain the Stage F context-switch tail caveat when reconciling exact window boundaries.

## Behavior preservation

Stage G is observation-only.

It does not modify:

- priority
- affinity/core masks
- yielding
- rescheduling policy
- wait/sleep behavior
- AddressArbiter behavior
- GPU behavior
- QueueBuffer/swap cadence
- fence behavior
- exact Eden baseline

The original scheduler `AddCpuTime`, `SwitchThread`, and `SetCurrentThread` call counts are preserved across the pre-G snapshot check.

## Ubuntu static validation — SUCCESS

One-shot Ubuntu workflow:

- workflow: `Validate dc95 X1 Waker Stage G`
- run: `33242026006`
- job: `99072879855`
- attempt: `1`
- conclusion: `success`
- validation HEAD: `40b59fff8728ead7df503db6b7279ef5af297ff5`

Passed:

- exact dc95 checkout / HEAD preservation
- retained non-scheduler patch reconstruction
- retained diagnostic chain reconstruction
- focused attribution reconstruction through Stage F
- pre-G invariant snapshot
- Stage G transplant
- `git diff --check`
- Stage G transplant/analyzer `py_compile`
- `[X1-WAKERG]` marker
- two producer slots
- 64 context slots per producer
- fixed top-4 report
- Stage F dynamic identity accessor
- no hardcoded observed TIDs
- no hardcoded observed promoted guest address
- exactly one selected-producer guest-context read
- exactly one switched-out CPU-slice hook
- exactly one selected-producer switch-in hook
- exactly one Stage G initialize hook
- exactly one Stage G 120-frame report hook
- guest PC/LR read is guarded by the Stage F producer check
- exact scheduler `AddCpuTime` count preserved
- exact `SwitchThread` count preserved
- exact `SetCurrentThread` count preserved
- no Stage-G-added priority/core-mask/reschedule/yield/sleep behavior
- no Stage-G-added QueueBuffer/swap/fence behavior
- Stage F report marker behavior preserved
- analyzer synthetic-log smoke test
- final exact dc95 HEAD preservation

The temporary Ubuntu workflow was deleted after successful validation.

## Persistent ARM workflow state

Persistent workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

It is prepared for Stage G and remains manual-only:

`workflow_dispatch`

It now reconstructs Stage A-F, snapshots pre-G invariants, applies Stage G, performs the Stage G pre-configure checks, and only then would configure/build ARM64.

No Stage G ARM64 workflow has been triggered.

## ARM64 authorization

Current ARM64 authorization: **NONE**.

No ARM64 build, rebuild, retry, or rerun was performed during Stage G implementation/static validation.

A fresh explicit authorization is required for exactly one Stage G ARM64 attempt.

## Runtime decision after a future authorized build

A. One/few PC/LR contexts own the slow-fast producer CPU growth:

> map those exact guest contexts to the guest execution/work path.

B. CPU ticks remain diffuse across many contexts:

> retain CPU as diffuse workload growth and move next to the already-open producer Arbitration branch.

C. Stage G CPU-tick totals or sanity counters fail to reconcile with Stage F behavior:

> audit instrumentation before any optimization.

Regardless of Stage G CPU result, keep open:

- producer-side Arbitration recursion
- separate Stage D dynamic-waker CPU-growth branch

No optimization is justified yet.
