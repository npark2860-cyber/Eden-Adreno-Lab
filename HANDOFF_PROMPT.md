# Handoff Prompt — Eden Adreno X1 Guest Post Wait Attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-guest-post-wait-attribution`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md`
3. `DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`
4. `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md` — completed predecessor
5. `DEBUG_HISTORY_20260828_IPC_DISPATCH.md`
6. `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`
7. `DEBUG_HISTORY_20260828_GUEST_SUBMIT.md`
8. `DEBUG_HISTORY_20260828_GPU_SUBMIT.md`
9. `DEBUG_HISTORY_20260828_CONTINUED.md`
10. `LAB_BOOTSTRAP.md`
11. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain the closed causal chain in `CURRENT_HANDOFF.md`, especially:

- BufferQueue free-slot wait is not the slow-gameplay owner
- HWC swap gating / DFPS / raw swap are not the root frame-production cause
- measured Vulkan Draw/Configure/Dispatch/Clear explains only a minority of the ~50 ms frame
- GPU worker spends a large fraction of slow frames in queue `PopWait`, waiting for upstream command supply
- lower NVDRV / GPFIFO submission is fast after candidate handler entry
- one guest thread `tid=0x53` owns essentially all candidate GPU submits and has only ~1-2% CPU share
- request -> `nvservices` handler dispatch is only ~0.02 ms/request and is NOT the missing 20-30 ms owner

Completed NVDRV IPC Dispatch Gap runtime:

`eden_log(20260828-061910).txt`

Representative results:

- frame 840: `guestPostAvg=16.840 ms`, `ipcDispatchAvg=0.021 ms`, `serviceReplyAvg=0.014 ms`
- frame 1320: `guestPostAvg=26.743 ms`, `ipcDispatchAvg=0.017 ms`, `serviceReplyAvg=0.039 ms`
- frame 1440: `guestPostAvg=29.091 ms`, `ipcDispatchAvg=0.027 ms`, `serviceReplyAvg=0.033 ms`

Critical conclusion:

> The live missing interval is previous candidate NVDRV completion/reply-adjacent C -> next candidate sync-request issue A on the guest side.

Do not reopen host `nvservices` scheduling/head-of-line unless new evidence contradicts these measurements.

Exact dc95 KThread facts for the current pass:

- wait reasons are None / Sleep / IPC / Synchronization / ConditionVar / Arbitration / Suspended
- BeginWait moves a thread to Waiting
- KThreadQueue EndWait/CancelWait move it back to Runnable
- KThread::SetState is the common transition point and clears the debug wait reason before applying the new base state

Current prepared experiment:

`X1 Log: Guest Post Wait Attribution`

New record:

`[X1-GUESTWAIT]`

It measures the dynamic candidate submitter's post-NVDRV interval and reports:

- candidate-window total/average/max
- completed KThread wait total and `waitShare`
- residual window time
- wait time/count by None/Sleep/IPC/Synchronization/ConditionVar/Arbitration/Suspended
- top three SVC IDs by tracked wait duration
- sanity counters

The current candidate request's own IPC wait is excluded. The next candidate handler entry is used as the window-end proxy; prior IPC-dispatch measurement shows handler-entry minus exact sync-send is only ~0.02 ms/request.

Interpretation:

- high waitShare -> follow only the dominant wait reason/SVC
- low waitShare + persistent ~1-2% submitter CPU share -> Runnable residency / scheduler competitor attribution
- mixed -> preserve both components and instrument only the dominant remainder

Prepared files:

- `src/core/x1_guest_post_wait_profiler.h`
- `tools/adreno_lab/transplant_dc95_guest_post_wait_attribution.py`
- `tools/adreno_lab/analyze_x1_guest_post_wait_attribution.py`
- `.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml`
- `NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md`
- `DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`

Workflow:

`Build dc95 X1 Guest Post Wait Attribution`

It must remain `workflow_dispatch` only.

Recommended runtime after a future successful build:

ON:
- Guest Post Wait Attribution
- NVDRV IPC Dispatch Gap
- Guest Submit Thread Attribution
- GPU Submit Gap Attribution
- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:
- Descriptor Ring
- swap 3 -> 2 clamp A/B
- all behavioral A/B controls
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs

NEXT ACTION:

Read `NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md`, verify branch/HEAD/workflow and Actions count. Static preparation is complete. Stop before ARM64 Actions unless the user gives fresh explicit authorization for exactly one build attempt.

No current ARM64 build authorization exists.
