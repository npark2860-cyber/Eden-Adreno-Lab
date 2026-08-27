# Handoff Prompt — Eden Adreno X1 GPU Command Attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-gpu-command-attribution`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260827_CONTINUED.md`
4. `DEBUG_HISTORY_20260828_CONTINUED.md`
5. `LAB_BOOTSTRAP.md`
6. `NEXT_ACTION_GPU_COMMAND_ATTRIBUTION.md`
7. `HANDOFF_PROMPT.md`

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
- adaptive Uniform fast stream is mapped staging re-stream; wholesale classic-cache fallback did not fix gameplay
- TOTK 1.4.2 raw main BufferQueue `swap=2 -> 3` explains the discrete 30 -> <=20 cadence shape in that run
- raw swap originates in guest QueueBuffer input, not Qualcomm Vulkan Present
- raw-3/effective-2 HardwareComposer A/B executed correctly but did not break the gameplay ceiling
- Dequeue attribution closed 2-buffer backpressure as the slow-state cause
- slow gameplay waits ~0.001 ms for a free slot and spends ~45-47 ms after Dequeue END before next Queue
- heavy X1 diagnostic logs do not create that interval
- DFPS ON can remain ~20-FPS class with raw swap=1
- DFPS OFF can remain ~20-FPS class with raw swap=3
- therefore DFPS and raw swap=3 are not the root renderer-performance cause
- Frame-Build attribution showed only roughly ~9-12 ms/frame in measured Vulkan Draw/Dispatch/Clear scopes, leaving roughly ~37-39 ms/frame unexplained outside those scopes

Frame-Build build completed successfully:

- workflow `Build dc95 X1 Frame Build Attribution`
- run `33115424368`
- job `98668715842`
- attempt 1
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact id `9665216124`
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`
- cleanup HEAD `f54b732e86e2ef0dd57a402a03b8a76cbbedc0e1`

Current work is the runtime-selectable GPU command attribution layer.

New control:

`X1 Log: GPU Command Attribution`

It emits `[X1-GPUCMD]` 120-frame aggregates for:

- asynchronous GPU worker queue PopWait vs active command handling
- PushCommand total + synchronous block-wait
- `Tegra::Control::Scheduler::Push` total / bind / DmaPusher dispatch
- `DmaPusher::DispatchCalls` loop / tail / sync wait
- `ProcessCommands` total + command-word volume
- CallMethod / CallMultiMethod counts without per-method timers

Primary next split:

- queueWait dominates => GPU worker is idle waiting for upstream/guest command supply
- active/dma/process dominates => Eden command interpretation / method execution owns the missing time
- blockWait material => upstream caller synchronously waits for GPU-worker completion

Prepared files:

- `src/video_core/x1_gpu_command_profiler.h`
- `tools/adreno_lab/transplant_dc95_gpu_command_attribution.py`
- `tools/adreno_lab/analyze_x1_gpu_command_attribution.py`
- `.github/workflows/build-dc95-x1-gpu-command-attribution.yml`
- `NEXT_ACTION_GPU_COMMAND_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 GPU Command Attribution`

It must remain `workflow_dispatch` only.

Recommended first runtime after a future successful build:

- same TOTK 1.2.1 gameplay route
- DFPS OFF first
- GPU Command Attribution ON
- Frame Build Attribution ON
- Frame Cadence ON
- Dequeue Attribution ON
- all behavioral A/B controls OFF
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- Descriptor Ring OFF

NEXT ACTION:

Read `NEXT_ACTION_GPU_COMMAND_ATTRIBUTION.md`, verify branch/HEAD/workflow state, and finish static/pre-Actions validation. Stop before ARM64 Actions.

No current ARM64 build authorization exists. A fresh explicit user authorization is required for exactly one build attempt.
