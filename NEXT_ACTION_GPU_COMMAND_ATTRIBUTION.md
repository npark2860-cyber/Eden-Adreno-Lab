# NEXT ACTION — X1 GPU Command Attribution

Updated: 2026-08-28 KST

## Goal

Resolve the remaining ~39 ms/frame that is not explained by the current Vulkan Frame-Build scopes in slow TOTK gameplay.

Current strongest split:

- Dequeue free-slot wait: essentially zero in slow gameplay
- Dequeue END -> next QueueBuffer: ~45-50 ms
- measured Vulkan Draw/Dispatch/Clear path: roughly ~9-12 ms/frame depending on DFPS state
- therefore roughly ~37-39 ms/frame remains outside the measured RasterizerVulkan Draw scopes

The next question is:

> Is the asynchronous Eden GPU worker mostly idle waiting for upstream/guest commands, or is it busy spending that time inside command scheduling / DmaPusher processing?

## Fixed baseline

- Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- branch: `exp/x1-gpu-command-attribution`
- predecessor: `exp/x1-frame-build-attribution@f54b732e86e2ef0dd57a402a03b8a76cbbedc0e1`

Do not change the baseline.

## New runtime control

`X1 Log: GPU Command Attribution`

Default OFF.

## New aggregate record

`[X1-GPUCMD]`

120-frame aggregates include:

### Asynchronous GPU worker

- queue `PopWait` count and wall time (`queueWait`)
- active command handling wall time (`active`)
- SubmitList / GPUTick / FlushRegion / InvalidateRegion sub-totals

### Upstream PushCommand

- total PushCommand wall time
- synchronous `blockWait` count/time if any caller blocks on the GPU worker

### `Tegra::Control::Scheduler::Push`

- total
- channel bind / scheduling-lock section
- DmaPusher dispatch section

### `DmaPusher`

- `DispatchCalls` total
- command-processing loop total
- tail (`FlushCommands + OnCommandListEnd`)
- Step count
- synchronization wait time
- `ProcessCommands` total + command word count
- CallMethod / CallMultiMethod counts only

No per-method wall-clock timer is used, intentionally minimizing profiler overhead.

## Interpretation

### Case A — queueWait dominates

If GPU worker `queueWait` is large while `active/dma/process` is small:

> the GPU worker is often idle and the upstream guest/CPU side is not supplying GPU command work quickly enough.

Next attribution should move toward GPU command submission producers / guest CPU execution.

### Case B — active/dma/process dominates

If `active`, `dma`, or `process` approaches the missing frame time:

> Eden command interpretation / method execution is the primary owner.

Then split `DmaPusher::ProcessCommands` by puller vs engine/macro/method classes, still avoiding per-method wall-clock sampling unless necessary.

### Case C — PushCommand blockWait is material

If caller `blockWait` is large:

> an upstream thread is synchronously waiting on GPU-worker completion.

Trace the blocking command type and caller rather than assuming pure CPU or GPU saturation.

## Recommended runtime

Use the same TOTK 1.2.1 gameplay route used for the DFPS comparison.

ON:

- GPU Command Attribution
- Frame Build Attribution
- Frame Cadence
- Dequeue Attribution

OFF:

- swap 3 -> 2 clamp A/B
- Uniform cache A/B
- Draw skip A/B
- Dispatch skip A/B
- Scheduler Sync heavy log
- Present log
- Pipeline log
- Upload/Barrier log
- QCOM workaround log
- Descriptor Ring

Run DFPS OFF first for the cleanest comparison with the latest baseline; DFPS ON can then be repeated without rebuilding if needed.

## Safety / scope

Observation only.

Do not modify:

- queue block/non-block semantics
- condition-variable predicates
- command order
- scheduler policy
- guest state
- Vulkan submit/fence/barrier/render-pass policy
- BufferQueue or swap interval
- speed limiter / VSync / Mailbox / Target_60

## Build rule

**No ARM64 build/re-run without a fresh explicit user authorization. One authorization = exactly one attempt.**

Workflow prepared:

`Build dc95 X1 GPU Command Attribution`

Trigger must remain `workflow_dispatch` only until a separately authorized one-shot administrative trigger is intentionally used.
