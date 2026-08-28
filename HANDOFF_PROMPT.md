# Handoff Prompt — Eden Adreno X1 NVDRV IPC Dispatch Gap

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-nvdrv-ipc-dispatch-gap`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`
3. `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`
4. `DEBUG_HISTORY_20260828_IPC_DISPATCH.md`
5. `DEBUG_HISTORY_20260828_GUEST_SUBMIT.md`
6. `DEBUG_HISTORY_20260828_GPU_SUBMIT.md`
7. `DEBUG_HISTORY_20260828_CONTINUED.md`
8. `LAB_BOOTSTRAP.md`
9. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain the closed facts in `CURRENT_HANDOFF.md`, especially:

- BufferQueue free-slot wait is not the slow-gameplay owner
- HWC swap gating / DFPS / raw swap are not the root frame-production cause
- measured Vulkan Draw/Configure/Dispatch/Clear explains only a minority of the ~50 ms frame
- GPU worker spends ~30-35 ms/frame in queue `PopWait`, waiting for upstream command supply
- lower NVDRV / GPFIFO submission is fast after candidate handler entry
- one guest thread `tid=0x53` owns essentially all candidate GPU submits and has only ~1-2% CPU share between observed candidate-handler entries

Critical exact-source correction:

- synchronous IPC sleeps the originator KThread in IPC wait
- Nvidia services run on a detached host process named `nvservices`
- one Nvidia `ServerManager` services `nvdrv`, `nvdrv:a`, `nvdrv:s`, `nvdrv:t`, and `nvmemp`
- no additional Nvidia host workers are started in that path
- therefore previous handler-entry timing did NOT distinguish guest-side post-reply delay from host-service request-dispatch delay

Current prepared experiment:

`X1 Log: NVDRV IPC Dispatch Gap`

New record:

`[X1-IPCDISPATCH]`

It splits:

- `guestPostAvg`: previous candidate handler completion -> current candidate generic sync-request send boundary
- `ipcDispatchAvg`: generic sync-request send boundary -> candidate NVDRV handler entry
- `serviceReplyAvg`: candidate handler entry -> handler completion / reply-adjacent boundary

Interpretation:

- `guestPostAvg` dominates => guest-side post-reply work/wait
- `ipcDispatchAvg` dominates => host `nvservices` wake/scheduling/head-of-line path
- `serviceReplyAvg` dominates => reopen handler/reply path

Prepared files:

- `src/core/x1_nvdrv_ipc_dispatch_profiler.h`
- `tools/adreno_lab/transplant_dc95_nvdrv_ipc_dispatch_gap.py`
- `tools/adreno_lab/analyze_x1_nvdrv_ipc_dispatch_gap.py`
- `.github/workflows/build-dc95-x1-nvdrv-ipc-dispatch-gap.yml`
- `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`
- `DEBUG_HISTORY_20260828_IPC_DISPATCH.md`

Workflow:

`Build dc95 X1 NVDRV IPC Dispatch Gap`

It must remain `workflow_dispatch` only.

Recommended runtime after a future successful build:

ON:
- NVDRV IPC Dispatch Gap
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

Read `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md`, verify branch/HEAD/workflow and Actions count. Static preparation is complete. Stop before ARM64 Actions unless the user gives fresh explicit authorization for exactly one build attempt.

No current ARM64 build authorization exists.
