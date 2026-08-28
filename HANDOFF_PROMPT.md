# Handoff Prompt — Eden Adreno X1 Guest Submit Thread Attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-guest-submit-thread-attribution`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260827_CONTINUED.md`
4. `DEBUG_HISTORY_20260828_CONTINUED.md`
5. `DEBUG_HISTORY_20260828_GPU_SUBMIT.md`
6. `DEBUG_HISTORY_20260828_GUEST_SUBMIT.md`
7. `LAB_BOOTSTRAP.md`
8. `NEXT_ACTION_GUEST_SUBMIT_THREAD_ATTRIBUTION.md`
9. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain all closed facts in `CURRENT_HANDOFF.md`, especially:

- alias trivial dedupe is closed
- wholesale classic-cache Uniform fallback did not break the gameplay ceiling
- raw swap / HardwareComposer gating and DFPS are not the root ~45-50 ms frame-production cause
- slow gameplay Dequeue free-slot wait is ~0.001 ms; BufferQueue backpressure is closed
- Frame-Build attribution found only ~9-12 ms/frame in measured Vulkan Draw/Dispatch/Clear scopes
- GPU Command Attribution found ~32-37 ms/frame of GPU worker queue `PopWait`; GPU worker is starved for upstream work
- GPU Submit Gap Attribution found candidate NVDRV service gap, confirmed nvhost_gpu submit gap and actual `PushGPUEntries` gap are effectively identical (~26 ms/submit in stable slow windows)
- NVDRV service, GPFIFO prep, channel lock and `SubmitGPFIFOImpl` are tiny and are closed as owners of the ~25-30 ms submit gap
- therefore the current causal boundary is **before the guest GPU-submit ioctl reaches NVDRV**

GPU Submit Gap build completed successfully:

- workflow `Build dc95 X1 GPU Submit Gap Attribution`
- run `33133440904`
- job `98728039155`
- attempt 1
- build HEAD `f65f93825979cde816aa41fc148deb042039416a`
- artifact id `9671670627`
- SHA-256 `0ef8e4172d812e4cfda90792f9bb2df0868dd192504cf2d3b11d30dcfbcdb313`
- cleanup HEAD `d17eb7314b2809c95e53874dbc7f64808df67006`

Runtime log:

`eden_log(20260828-030445).txt`

Note: that runtime accidentally still had swap 3->2 clamp and Descriptor Ring ON. The structural submit-gap result remains valid, but both should be OFF in the next clean run.

Exact new observation point:

- `HLERequestContext::GetThread()` exposes the originator guest `KThread`.
- exact dc95 `KThread` exposes thread ID, CPU time, core, priority and saved PC.
- exact dc95 `KScheduler::SwitchThread()` updates `KThread::GetCpuTime()` from the same `CoreTiming().GetClockTicks()` time base.

Current work is the runtime-selectable **Guest Submit Thread Attribution** layer.

New control:

`X1 Log: Guest Submit Thread Attribution`

New record:

`[X1-GUESTSUBMIT]`

It reports 120-frame aggregates for:

- active GPU-submit originator thread count
- dominant guest thread ID and submit share
- same-thread submit wall gaps
- guest CoreTiming tick delta
- submitter KThread CPU-time tick delta
- derived `cpuShare`
- saved caller PC and PC stability
- current/active core and priority

Primary split:

- high dominant share + high cpuShare => one guest GPU producer is CPU-bound; next target guest code / Dynarmic execution
- high dominant share + low cpuShare => submitter is mostly waiting/preempted; next target targeted kernel wait/SVC attribution
- multiple material submitter threads => attribute per-thread before deeper scheduler tracing

Prepared files:

- `src/video_core/x1_guest_submit_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_submit_thread_attribution.py`
- `tools/adreno_lab/analyze_x1_guest_submit_thread_attribution.py`
- `.github/workflows/build-dc95-x1-guest-submit-thread-attribution.yml`
- `NEXT_ACTION_GUEST_SUBMIT_THREAD_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 Guest Submit Thread Attribution`

It must remain `workflow_dispatch` only.

Recommended future runtime after a successful build:

ON:
- Guest Submit Thread Attribution
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:
- swap 3 -> 2 clamp A/B
- Descriptor Ring
- all behavioral A/B controls
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

NEXT ACTION:

Read `NEXT_ACTION_GUEST_SUBMIT_THREAD_ATTRIBUTION.md`, verify branch/HEAD/workflow state, and finish static/pre-Actions validation. Stop before ARM64 Actions.

No current ARM64 build authorization exists. A fresh explicit user authorization is required for exactly one guest-submit-thread build attempt.
