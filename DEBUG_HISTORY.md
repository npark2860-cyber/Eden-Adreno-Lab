# Eden Snapdragon / Adreno X1-85 Debug History

> Chronological experiment log for `npark2860-cyber/Eden-Adreno-Lab`.
>
> Last consolidated: 2026-08-26 (KST)
>
> Durable architecture belongs in `TECH_BIBLE.md`. Only the latest active state belongs in `CURRENT_HANDOFF.md`.

---

## 2026-08-26 — Control baseline established

### Known-good source

The project stopped treating later Eden source as the control and anchored all performance experiments to:

- Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- official tag: `v1786904188.dc95cd09ee`
- official Nightly date: 2026-08-16
- Lab control branch: `lab/dc95-arm64-baseline`

Important correction:

- `0295dc5fff9b2977e753e7c126cc870abb07ee3f` is later source, 23 commits ahead, and is not the control.

### Clean ARM64 control builds

PGO control:

- workflow run: `32917736899`
- artifact: `Eden-dc95-ARM64-clean-PGO`
- artifact id: `9589236155`

Standard control:

- workflow run: `32914980539`
- artifact id: `9588440312`

Runtime observation carried forward from the known-good build:

- about 20 FPS in ordinary gameplay
- heavy field sections can fall to about 15-6 FPS
- stable enough that the user does not feel the characteristic "about to freeze" behavior seen in other experiments

Result:

**CONFIRMED:** dc95 is the immutable performance/correctness anchor.

---

## 2026-08-26 — DescriptorBufferRing investigation

Branch:

- `exp/x1-descriptor-ring`

Instrumentation added for:

- allocations and aligned bytes
- frame-slot reuse `Scheduler::Wait`
- chunk switches
- chunk exhaustion and forced `Scheduler::Finish`

Main tools:

- `tools/adreno_lab/transplant_dc95_descriptor_ring_profiler.py`
- `tools/adreno_lab/analyze_x1_descriptor_ring_log.py`
- `tools/adreno_lab/transplant_dc95_logging_checkboxes.py`

Relevant commits recorded during the work:

- analyzer correction: `d9a56a3d5f0d8b4e913faf2f1ad9e3d076855f6a`
- docs: `cd9b195921573b3050b2185b3b78d25fe9e4545c`
- logging-checkbox companion: `95c8ebb213326ba2816b8f267a60e3f6f3566eb4`

Later runtime result:

- even with the descriptor profiler enabled, TOTK repeatedly reported zero allocations, zero reuse waits, zero chunk switches, and zero exhaustion finishes
- full-flow counters also reported `dbufEntries=0` and `dbufBinds=0`

Result:

**REJECTED for the current TOTK path:** DescriptorBufferRing is not the cause of the ordinary ~20 FPS ceiling in the measured runs.

The profiler remains useful for other games.

---

## 2026-08-26 — Full-flow profiler built

Branch:

- `exp/x1-full-flow-profiler`

Goal:

Measure the full Vulkan backend flow before making an optimization patch.

Added diagnostic categories:

1. Scheduler / Sync
2. Present / Frame Pacing
3. Pipeline / Shader
4. Upload / Barrier
5. QCOM Workaround Hits
6. Descriptor Ring

Shared output prefixes:

- `[X1-FLOW][SCHED]`
- `[X1-FLOW][PIPE]`
- `[X1-FLOW][PRESENT]`
- `[X1-FLOW][UPLOAD]`
- `[X1-FLOW][QCOM]`
- `[X1-FLOW][DBUF]`

### Build failure 1

Initial workflow commit:

- `ceb716dc6014c528afaf4f0ce76b295269a191c5`
- run: `32942572022`
- job: `98096432219`

Failure:

- P0.2 scheduler patch did not apply to exact dc95
- no compiler result; therefore not a performance result

Fix:

- exact dc95 scheduler-flow transplant created
- commit: `d5ec784cae6e89b4c0f32a5353b313b850508043`

### Build failure 2

Revised workflow:

- commit: `2337ac2afda3e05d595884c798a06b0698bb2296`
- run: `32942985025`
- job: `98097684139`

Pre-build transplant/configuration succeeded, but compile failed in swapchain instrumentation:

- `vk_swapchain.cpp` referenced `result` after the VkResult variable had been moved out of the switch initializer
- a pacing-lambda profiler variable also shadowed another name

Additional audit found an accidental later scheduler frame-pacing behavior had leaked into generated code. The finalizer was updated to restore exact dc95 behavior:

- sleep when remaining time is >15 ms, leaving about 1 ms
- yield until target
- reject any `spin_tail`

### Finalizer correction

Branch head before the authorized successful build included:

- `9727b33fd00988f7eaafecadfbcac855b4a59422`
- message: `profiler: fix swapchain scope and full pipeline wait timing`

The finalizer also:

- moved graphics/compute ready-wait timers to include mutex contention
- gated measured QCOM sampler hits to proprietary Qualcomm
- fixed Present result scoping
- rejected later-scheduler tokens such as `MarkResolveShadowsUpToDate`, `FlushDeferredClear`, and `depth_stencil_discard`

### Successful authorized full-flow build

A one-shot branch/path push trigger was temporarily used because the connected GitHub API did not expose direct workflow dispatch.

Trigger commit:

- `7c2984d8d590b61886dcc103171da41241671472`

Run:

- `32953939472`
- job: `98131344257`

Immediately restored manual-only workflow:

- restore commit: `b730d35031841ad68bdb6767e623086623037c08`

The restore commit triggered no second build.

---

## 2026-08-26 — First long full-flow runtime: bottleneck family identified

Title/run context:

- TOTK 1.4.3
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- 1x resolution, no AA, FSR, Docked
- GPU accuracy Low
- asynchronous presentation enabled
- asynchronous GPU emulation enabled
- compute pipelines disabled
- asynchronous shaders disabled
- buffer reorder enabled

Profiler state:

- Scheduler=true
- Present=true
- Pipeline=true
- Upload=true
- QCOM=true
- Descriptor Ring=false in this first long run

Sample size:

- 51 periodic summaries x 120 frames = 6120 summarized frames

### Aggregate findings

Scheduler:

- wait count: 51,409
- wait total: 89,004.668 ms
- GPU component: 88,981.862 ms
- pacing component: 22.808 ms
- Finish: 1,111 calls / 1,712.585 ms
- WaitWorker: 0
- submit: 77,221 (~12.62/frame)
- RP begin/end: 1,015,628 / 1,015,628
- RP reuse: 9,002,433
- post-RP image barriers: 2,219,258

RP end reasons:

- outside: 891,183 (~145.62/frame)
- framebuffer: 124,408 (~20.33/frame)

Pipeline:

- graphics builds: 2,523
- graphics-ready waits: 6 / 297.688 ms
- compute builds: 54
- shader emits: 5,100

Present:

- waits: 18,373 / 119.255 ms total
- acquire: 6,119 / 139.705 ms total
- present: 6,119 / 2,979.855 ms total

Upload:

- staging upload: ~24.75 GiB
- staging download: ~5.24 GiB
- deferred download: ~5.20 GiB
- BufferCopy: 891,236 calls / 7,398.652 MiB
- reordered upload: 189,103 calls / 923.013 MiB
- barriers: 443,075

### Strong transition example

Frame-1800 summary was a light window:

- scheduler wait ~0.455 ms / 120 frames
- submit 240
- RP begin/end 496
- outside RP ends 496
- staging upload 5.463 MiB
- BufferCopy 3.449 MiB
- barriers 616

Frame-1920 summary was a heavy window:

- scheduler wait 2,842.312 ms / 120 frames
- GPU wait 2,842.173 ms
- submit 1,715
- RP begin/end 25,758
- outside RP ends 22,744
- staging upload 1,186.822 MiB
- BufferCopy 638.942 MiB
- barriers 11,996
- Present total was not larger enough to explain the drop

Correlations across periodic windows, excluding startup:

- FPS vs staging upload MiB: about -0.925
- FPS vs BufferCopy count: about -0.868
- FPS vs staging-upload count: about -0.852
- FPS vs barriers: about -0.841
- FPS vs scheduler GPU wait: about -0.825
- FPS vs post-RP barriers: about -0.811
- FPS vs Present time: about -0.004

Important near-match:

- total BufferCopy count: 891,236
- total `RPend[outside]`: 891,183

Result:

**CONFIRMED:** low-FPS gameplay is associated with upload/copy pressure, render-pass fragmentation, barriers/submits, and scheduler GPU waits.

**REJECTED as steady-state primary causes:** Present/frame pacing and pipeline/shader compilation.

Next question became:

> Which Draw/Dispatch work actually generates this upload/copy/RP-break chain?

---

## 2026-08-26 — Draw vs Dispatch correlation

Branch:

- `exp/x1-draw-dispatch-correlation`

Prepared branch head reported during setup:

- `feff65eee555abdb02f2ddaeeee0133f4121cdf4`

Added:

- `[X1-FLOW][ORIGIN]` 120-frame Draw vs Dispatch aggregates
- `[X1-FLOW][ORIGIN-CALL]` heavy individual call records
- signatures for Draw/Dispatch
- optional signature A/B controls, default OFF

A single exact signature can be skipped before preparation for diagnostic purposes, but this is not a production optimization.

Authorized ARM64 build:

- run: `32961138166`

### Runtime result

The correlation run showed:

- Draw preparation dominated steady-gameplay upload cost
- Draw + Dispatch explained almost all measured staging upload inside the profiled origins
- 376 heavy individual origin calls were captured
- 373 were Draw; 3 were Dispatch
- 372 of the 373 heavy Draws belonged to the same high-level signature family beginning `0x82000001...`

Decoded family:

- indexed = true
- topology = 4 = triangles
- instance count = 1
- vertex count varies

Result:

**STRONG:** the issue is not one weird Draw signature. Ordinary indexed-triangle Draw preparation repeatedly enters expensive resource-preparation paths.

Next question became:

> Which BufferCache/resource category inside Draw preparation is generating the cost?

---

## 2026-08-26 — Buffer-category correlation experiment

Branch:

- `exp/x1-buffer-category-correlation`

Current manual-only branch HEAD after restoring the temporary build trigger:

- `0ed8df216fbe416f4f569a9490c5f8f128bb0cfc`

Important instrumentation files added on the experiment branch include:

- `tools/adreno_lab/transplant_dc95_buffer_category_correlation.py`
- `tools/adreno_lab/analyze_x1_buffer_category_log.py`

The category profiler attributes Draw/Dispatch preparation to:

- other
- index
- vertex
- uniform
- storage
- texture-buffer
- transform-feedback

The scope was deliberately designed to include relevant `Update*` and host-binding/synchronization work rather than measuring only the state-update half.

### Authorized build

Temporary trigger commit used for the actual build:

- `3780a5746a35d22e01dbe87c27f14c7e9fc37e1b`

Workflow run:

- `32967450066`
- job: `98173182429`
- result: success

Artifact:

- id: `9607231624`
- name: `Eden-dc95-X1-draw-dispatch-correlation`
- digest: `sha256:877b2d9e1db44b69e55f93b20d2ed94237e6d75d1be60b9ee9de02a7f2ed76b0`

Note: the artifact name still says `draw-dispatch-correlation`, but this run was built from the buffer-category branch with the category transplant chained into the build. Do not mistake the artifact label for the instrumentation level.

The workflow was immediately restored to manual-only at branch HEAD `0ed8df...`; the restore commit did not start another build.

---

## 2026-08-26 — Latest buffer-category runtime: steady cost and dip cost split

Latest uploaded runtime log:

- user upload filename in this work session: `eden_log(5).txt`
- logical Eden log name: `eden_log.txt`
- TOTK version: 1.4.2
- X1 A/B skip Draw: false, signature 0
- X1 A/B skip Dispatch: false, signature 0
- Scheduler/Present/Pipeline/Upload/QCOM/Descriptor diagnostic checkboxes: enabled
- Descriptor profiler: enabled

### Steady gameplay classification: frames 960-3120

Draw-side classified upload total: 12,386.626 MiB.

By category:

- Uniform: **10,795.857 MiB (87.2%)**
- Other: **1,259.508 MiB (10.2%)**
- Vertex: **294.508 MiB (2.4%)**
- Index: 18.773 MiB
- Storage: 17.980 MiB
- Texture-buffer: 0
- Transform-feedback: 0

Uniform request frequency:

- 26,069,240 upload requests across 2,280 summarized frames
- ~11,434 requests/frame
- ~434 bytes/request on average

Normal 20 FPS-class example, frame 1440 summary:

- Uniform upload requests: 2,154,942 / 120 frames
- Uniform upload: 767.000 MiB
- Vertex copy: 7.582 MiB
- Other outside-RP: 3,073
- Other barriers: 3,845

Result:

**STRONG:** the ordinary ~20 FPS ceiling has a persistent extreme tiny-Uniform-upload burden.

### Slow-window example: frame 1080 summary

This 120-frame interval maps to about 13.1 summary frames/sec and matches the user's observed slowdown class.

Global:

- staging upload: 977.378 MiB
- BufferCopy: 556.804 MiB
- barriers: 12,550

Draw Uniform:

- 1,336,721 upload requests
- 531.697 MiB upload

Draw Vertex:

- 3,604 upload requests
- 88.844 MiB upload
- 4,454 copy calls
- **375.469 MiB copy**
- 1,169 outside-RP endings

Draw Other:

- 263.296 MiB upload
- **4,654 outside-RP endings**
- **5,062 barriers**

For comparison, 20 FPS-class frame-1320/1440 windows had Vertex copy around 6.55-7.58 MiB rather than hundreds of MiB.

Result:

**STRONG:** severe 15-6 FPS-class dips are associated with a Vertex-copy explosion plus `other` render-pass/barrier explosion, while Uniform remains a large constant background cost.

### Outside-RP attribution over frames 960-3120

Approximate Draw-side shares:

- other: **85.95%**
- vertex: 9.54%
- index: 1.67%
- uniform: 1.50%
- storage: 1.34%

All Draw-category barriers currently attributed by the category profiler land in `other`.

Result:

**Current highest-priority open question:** what concrete Draw-preparation caller(s) are hidden inside `other`?

---

## Current rejected / weakened hypotheses

The following should not be restarted as the first-line explanation without new evidence:

- Present/VSync/frame pacing as the primary 20 FPS bottleneck
- pipeline/shader compilation as the steady-state primary bottleneck
- DescriptorBufferRing as the active TOTK bottleneck
- one single exact Draw signature as the root cause
- one specific generic QCOM workaround as the root cause, based only on the device warnings

---

## Current live hypotheses

1. **Uniform tiny-upload overhead** is a major contributor to the ordinary ~20 FPS ceiling.
2. **Vertex dirty/alias/stream copy amplification** produces large slow-scene spikes.
3. **`other` Draw preparation** is the dominant source of outside-RP endings and attributed barriers and must be split into concrete callers/reasons.
4. The resulting render-pass fragmentation/submits ultimately amplify scheduler GPU waits.

Next action is maintained in `CURRENT_HANDOFF.md`.
