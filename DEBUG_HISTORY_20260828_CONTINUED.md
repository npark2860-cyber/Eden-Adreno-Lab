# DEBUG HISTORY — 2026-08-28 continuation

## Frame-Build Attribution runtime closure

Exact baseline remained:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Frame-Build build:

- workflow `Build dc95 X1 Frame Build Attribution`
- run `33115424368`
- job `98668715842`
- attempt 1
- build HEAD `a1eba5fdbea2455f24392629f594cbb99cc03e74`
- artifact `Eden-dc95-X1-frame-build-attribution`
- artifact id `9665216124`
- SHA-256 `43a83eeb51dd3ef9ba65f804a12f14f08dbf58796e84bed22e2147c9ab3af709`
- success, no rerun

### DFPS ON run

TOTK 1.2.1 / Adreno X1-85 / Qualcomm 512.863.0 / Vulkan 1.3.295 / Windows 11 25H2.

Observed stable slow gameplay:

- ~48.8 ms/frame (~20.5 FPS class)
- raw QueueBuffer swap=1
- Dequeue free-slot wait ~0.001 ms in slow state
- Dequeue END -> Queue remains ~45 ms class
- Draw count ~3,066/frame
- measured Vulkan Draw ~11.1 ms/frame
- Graphics Configure ~7.2 ms/frame
- FillImageViews ~0.7 ms/frame
- approximately ~37 ms/frame remained outside measured RasterizerVulkan scopes

Interpretation:

- FillImageViews is not the owner of the majority of the slow frame.
- high Draw count alone is not enough to explain the ~20-FPS class.
- Frame-Build measurement moved the unresolved owner above/outside the measured Vulkan Draw path.

### DFPS OFF comparison

Log:

`eden_log(20260827-234038).txt`

Relevant settings in that run:

- Frame Build Attribution ON
- Frame Cadence ON
- Dequeue Attribution ON
- Scheduler/Present/Pipeline/Upload/QCOM heavy logs OFF
- Descriptor Ring ON (not desired for next clean run)
- swap 3 -> 2 clamp ON (not desired for next clean run)

Observed slow gameplay:

- raw swap returned to 3
- effective interval became 2 only because old clamp A/B was ON
- actual frame rate remained ~19-21 FPS
- Dequeue wait remained ~0.001 ms
- Dequeue END -> next Queue median remained ~45.5 ms
- Draw count fell to ~1,962/frame
- measured Vulkan Draw time fell to ~8.4 ms/frame
- total measured RasterizerVulkan Draw/Dispatch/Clear class remained only ~9 ms/frame
- approximately ~39 ms/frame remained outside the measured scopes

Interpretation — strongly supported:

1. DFPS affects cadence/workload shape but is not the root cause of the slow ~45-50 ms frame-production interval.
2. raw swap=3 is not the root renderer-performance cause.
3. reducing Draw count materially did not remove the ~20-FPS class.
4. the remaining owner is above/outside the measured RasterizerVulkan Draw scopes.

## New experiment — GPU Command Attribution

Branch:

`exp/x1-gpu-command-attribution`

Predecessor cleanup HEAD:

`exp/x1-frame-build-attribution@f54b732e86e2ef0dd57a402a03b8a76cbbedc0e1`

Goal:

Separate the remaining ~39 ms/frame into:

- GPU worker idle waiting for upstream/guest commands, versus
- Eden GPU command scheduling / DmaPusher command processing.

Prepared runtime control:

`X1 Log: GPU Command Attribution`

Prepared record:

`[X1-GPUCMD]`

Measurements:

- GPU worker `PopWait` wall time
- GPU worker active command handling
- PushCommand total and block wait
- Control Scheduler::Push total / bind / Dma dispatch
- DmaPusher::DispatchCalls loop / tail
- Dma sync wait
- ProcessCommands wall time and command word volume

Profiler intentionally avoids both per-method wall-clock timers and per-method atomic counters to reduce measurement perturbation on the command hot path.

Prepared files:

- `src/video_core/x1_gpu_command_profiler.h`
- `tools/adreno_lab/transplant_dc95_gpu_command_attribution.py`
- `tools/adreno_lab/analyze_x1_gpu_command_attribution.py`
- `.github/workflows/build-dc95-x1-gpu-command-attribution.yml`
- `NEXT_ACTION_GPU_COMMAND_ATTRIBUTION.md`

No GPU-command ARM64 build has been authorized or run at the time of this entry.
