# Eden Snapdragon / Adreno X1-85 Technical Bible

> Canonical technical reference for `npark2860-cyber/Eden-Adreno-Lab`.
>
> Last consolidated: 2026-08-26 (KST)
>
> This file contains durable facts, architecture, invariants, and experiment rules. Current work-in-progress state belongs in `CURRENT_HANDOFF.md`; chronological experiment results belong in `DEBUG_HISTORY.md`.

---

## 1. Project purpose

The project investigates why Eden on Windows ARM64 Snapdragon X / Adreno X1-85 is stable but much slower than expected in demanding titles such as The Legend of Zelda: Tears of the Kingdom (TOTK).

The central research question is:

> Is Eden already near the hardware/driver performance ceiling on Adreno X1-85, or is Eden still losing substantial performance because generic/mobile Qualcomm assumptions, resource synchronization, render-pass transitions, uploads, or submit behavior are suboptimal on Windows ARM64?

The working method is always:

`source inspection -> instrumentation -> one-variable A/B -> runtime verification -> promote only proven facts`

The user is the runtime tester on the actual X1-85 machine. Repository/source/diff/branch/CI/build analysis and edits are handled in the lab repository.

---

## 2. Repositories and immutable control

### Eden source mirror

- Repository: `eden-emulator/mirror`
- Exact known-good source SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- Runtime identification: `Eden Development Build | master-dc95cd09ee-master` / diagnostic builds may show `HEAD-dc95cd09ee-HEAD`
- Official Nightly tag: `v1786904188.dc95cd09ee`
- Nightly date: 2026-08-16

### Lab repository

- Repository: `npark2860-cyber/Eden-Adreno-Lab`
- Default branch: `main`
- Immutable control branch: `lab/dc95-arm64-baseline`

### Important non-control source

`0295dc5fff9b2977e753e7c126cc870abb07ee3f` is later than dc95 and is **not** the known-good control. It is 23 commits ahead of dc95 and includes later Qualcomm changes such as #4301. Never substitute it for dc95 when interpreting A/B results.

---

## 3. Exact Windows ARM64 build provenance

Official Nightly ARM64 does not use a separate ARM64 source commit. It builds the same Eden source using ARM64-specific CI/toolchain/PGO configuration.

Known dc95-era CI reference:

- Eden-CI/Workflow commit: `afead830f3a444427f9fdfd841218f932465c03a`
- Toolchain: MSYS2 `CLANGARM64`
- Compiler: clang, not clang-cl/MSVC
- Architecture flags: `-march=armv8-a`, `-mtune=generic`, `-O3`

Exact PGO reference used for the control investigation:

- Eden-CI/PGO tag: `v020525`
- asset: `eden.profdata`
- SHA256: `777dd9aefb9427ed08a642b02998f32c5ac120e5d32611d8f21cf1f4e68cee57`

Control artifacts established during this project:

- PGO control run: `32917736899`, artifact `Eden-dc95-ARM64-clean-PGO`, artifact id `9589236155`
- Standard control run: `32914980539`, artifact id `9588440312`

The control branch must not be edited to test hypotheses. Every behavioral experiment gets a separate branch.

---

## 4. Runtime test platform

Primary host:

- Windows 11 ARM64
- Snapdragon X1E80100
- Qualcomm Adreno X1-85 GPU
- Qualcomm Windows Vulkan driver `512.863.0`
- Vulkan `1.3.295`
- Reported VRAM: `6.00 GiB`
- Host CPU threads: 12
- Host RAM: about 15.6 GiB

Primary title for the current investigation:

- The Legend of Zelda: Tears of the Kingdom
- Title ID: `0100F2C0115B6000`
- Both 1.4.3 and 1.4.2 have been used in separate diagnostic runs; always record the exact version for each A/B.

Observed runtime behavior on the known-good family:

- Stable, no characteristic freeze feeling in the control Eden build
- Typical perceived gameplay: about **20 FPS**
- Heavy sections: roughly **15 down to 6 FPS**

Do not infer FPS directly from every profiler summary timestamp without checking how the summary cadence maps to rendered/emulated frames. Use the user's observed FPS and matched 120-frame windows together.

---

## 5. Evidence vocabulary

Use these labels consistently:

- **CONFIRMED**: directly supported by source/runtime evidence or a controlled A/B.
- **STRONG**: multiple independent observations support it, but causality is not yet isolated.
- **REFERENCE**: source architecture or external information useful to the investigation.
- **REJECTED**: tested and not capable of explaining the observed primary bottleneck under the tested conditions.
- **OPEN**: plausible and not yet isolated.

Correlation is not causation. A high metric correlation is grounds for the next A/B, not a production patch by itself.

---

## 6. Qualcomm behavior confirmed on Windows X1

The dc95 Vulkan device path applies generic Qualcomm handling to the Windows X1-85. Runtime warnings confirm active assumptions/workarounds including:

- scaled vertex format emulation
- broken descriptor aliasing
- broken custom border color
- broken border color swizzle
- broken color write enable
- broken shader float controls
- broken shader atomic int64
- broken workgroup memory explicit layout
- sampler reservation: driver reports 65536, Eden reserves 16384 and allows Eden to use 49152
- higher-than-reported binding-limit handling

These are **not automatically performance bugs**. Remove or narrow them only after a one-variable test shows a benefit without correctness regressions.

`Device::IsTiler()` in exact dc95 returns true for the proprietary Qualcomm driver, including Windows X1. Therefore tiler policies can be active even outside Android.

---

## 7. Descriptor Buffer Ring facts

Exact dc95 policy:

- `FRAMES_IN_FLIGHT = 8`
- tiler frame size: 2 MiB
- desktop frame size: 4 MiB
- frame-slot reuse can call `scheduler.Wait(frame_ticks[frame_index])`
- chunk exhaustion can log `Descriptor buffer frame exhausted, stalling on the GPU` and call `scheduler.Finish()`

However, the TOTK diagnostic runs have now measured this path directly.

**REJECTED as the current primary TOTK bottleneck:** with the descriptor profiler enabled, repeated summaries reported zero allocations, zero reuse waits, zero chunk switches, and zero exhaustion finishes. Full-flow counters likewise showed `dbufEntries=0` and `dbufBinds=0` in the relevant runs.

Keep the profiler available for other titles, but do not return to DescriptorBufferRing as the first TOTK optimization target without new evidence.

---

## 8. Scheduler / synchronization facts

Relevant dc95 scheduler behavior:

- `Wait(tick)` can flush if needed, then waits on the master semaphore.
- Frame pacing is a separate component; exact dc95 uses a long-sleep-then-yield policy, not the later 1 ms `spin_tail` variant.
- `Finish()` presubmits, submits execution, waits, then allocates a new context.
- `SubmitExecution()` includes a conservative upload command-buffer transition from transfer writes toward `VK_PIPELINE_STAGE_ALL_COMMANDS_BIT`.

First full-flow runtime measurements showed large GPU-wait totals during normal low-FPS gameplay while frame-pacing time was tiny by comparison.

**CONFIRMED:** the scheduler's GPU wait is a large part of the observed low-FPS workload.

**REJECTED as primary causes in the tested steady state:**

- frame pacing
- present/acquire latency
- WaitWorker

Do not interpret `ORIGIN ... wait=0` as proof that Draw caused no later GPU wait. The current origin tracker is thread-local and does not propagate every downstream scheduler wait across threads.

---

## 9. Render-pass / copy relationship

Eden already reuses a render pass when renderpass/framebuffer/render area are compatible. But certain outside-operation paths force the render pass to end, after which image barriers and additional submission/synchronization work can follow.

The first full-flow log established a strong runtime chain:

`staging upload / buffer copy rises`

`-> outside-render-pass endings rise`

`-> post-RP barriers and submits rise`

`-> scheduler GPU waits rise`

`-> FPS falls`

Across the first long full-flow sample, `bufferCopy` and `RPend[outside]` totals were nearly identical in magnitude, and low-FPS windows showed orders-of-magnitude more upload/copy/RP fragmentation than light windows.

This made `CopyBuffer / RequestOutsideRenderPassOperationContext / barrier / submit` a primary investigation path.

---

## 10. Draw / Dispatch architecture and findings

### Source path

A graphics Draw is not just the final `vkCmdDraw*` call. The expensive preparation happens before it:

`RasterizerVulkan::Draw`

`-> PrepareDraw`

`-> GraphicsPipeline::Configure`

`-> BufferCache::UpdateGraphicsBuffers(is_indexed)`

`-> BufferCache::BindHostGeometryBuffers(is_indexed)` and related resource preparation

`-> vkCmdDraw*`

Compute Dispatch likewise performs pipeline/resource configuration and outside-render-pass/barrier operations where required.

### Draw/Dispatch correlation result

The Draw/Dispatch profiler showed that steady gameplay resource preparation is overwhelmingly Draw-driven:

- the overwhelming majority of heavy individual origin calls were Draw
- Dispatch was materially smaller
- heavy Draw signatures were mostly one family: indexed, triangle topology, single instance, with vertex count changing

This means an exact single-signature skip is too narrow as the main optimization strategy. The likely issue is a repeated resource-preparation pattern used by ordinary indexed-triangle draws, not one anomalous draw call.

The signature A/B controls are still useful for diagnostics and default OFF.

---

## 11. Buffer-category decomposition: current strongest result

The latest profiler divides Draw/Dispatch preparation into:

- `index`
- `vertex`
- `uniform`
- `storage`
- `texture-buffer`
- `transform-feedback`
- `other`

The category scopes cover both update and host-binding/synchronization work where applicable. `other` deliberately captures work inside the Draw/Dispatch origin but outside the named BufferCache category scopes.

### Steady gameplay, frames 960-3120 of the latest run

Draw-side upload totals:

- Uniform: **10,795.857 MiB** (**87.2%** of classified Draw upload)
- Other: **1,259.508 MiB** (**10.2%**)
- Vertex: **294.508 MiB** (**2.4%**)
- Index: **18.773 MiB**
- Storage: **17.980 MiB**
- Texture-buffer: 0
- Transform-feedback: 0

Uniform upload requests:

- about **26.07 million requests over 2,280 frames**
- about **11,434 requests per frame**
- average payload about **434 bytes per request**

**STRONG:** the normal ~20 FPS ceiling is associated with an extreme number of tiny Uniform uploads during Draw preparation.

### Heavy window example: frame 1080 summary (120 frames)

Overall upload/copy pressure rises sharply:

- staging upload: **977.378 MiB**
- buffer copy: **556.804 MiB**
- barriers: **12,550**

Draw categories include:

- Uniform: 531.697 MiB upload, 1,336,721 requests
- Vertex: 88.844 MiB upload, **375.469 MiB actual buffer copy**, 4,454 copy calls, 1,169 outside-RP endings
- Other: **263.296 MiB upload**, **4,654 outside-RP endings**, **5,062 barriers**

The same 120-frame interval maps to about 13.1 summary frames/sec, consistent with a user-observed slowdown region rather than the normal ~20 FPS state.

**STRONG:** severe dips are associated with Vertex-copy explosions plus a large `other` outside-RP/barrier explosion, on top of the persistent Uniform upload burden.

### `other` is now a first-class target

Across the same steady-gameplay range, Draw-side outside-RP endings are approximately:

- `other`: **85.95%**
- vertex: 9.54%
- index: 1.67%
- uniform: 1.50%
- storage: 1.34%

All Draw-category barriers currently attributed by this instrumentation are in `other`.

Therefore the next source-analysis priority is to subdivide `other` into concrete caller/reason classes, not to assume BufferCache alone explains all render-pass breaks.

---

## 12. Causes currently weakened or rejected for TOTK steady-state 20 FPS

### Present / swapchain / pacing

First-pass full-flow measurement showed acquire and present costs far too small to explain ~50 ms-class frame time and essentially no useful correlation with FPS.

Status: **REJECTED as primary steady-state cause**.

### Pipeline / shader compilation

Pipeline and shader work matters at startup/loading and can produce transient stutters. But long steady gameplay windows continued to run slowly while graphics builds, ready waits, compute builds, and shader emits were zero.

Status: **REJECTED as primary steady-state cause; retained as transient-stutter contributor**.

### Descriptor Buffer Ring

Measured inactive in the current TOTK path.

Status: **REJECTED as current primary cause**.

### Specific QCOM workaround hit counters

The currently instrumented recurring QCOM event counters were mostly zero after startup. Generic Qualcomm policy remains active, but no specific measured workaround hit has yet explained steady-state FPS.

Status: **OPEN generally, but not first priority**.

---

## 13. Current optimization hypothesis tree

### H1 — Uniform tiny-upload overhead

Question:

> Why does normal gameplay perform more than ten thousand tiny uniform uploads per frame?

Investigate:

- whether the guest genuinely changes that many constant/uniform ranges
- whether dirty tracking invalidates more often than necessary
- whether already-updated bindings can be reused longer
- whether many tiny stream uploads can be coalesced/batched without violating guest-visible ordering
- whether alignment/ring/stream policy is expensive specifically on Windows Qualcomm

Do not skip Uniform updates blindly; correctness risk is high.

### H2 — Vertex copy explosion in heavy scenes

Question:

> What invalidation/aliasing/streaming condition changes a normal ~7 MiB/120-frame vertex-copy window into ~375 MiB/120-frame copy traffic?

Investigate:

- same-buffer reupload / aliasing
- dirty-range granularity
- reorderable-upload path
- CPU writes vs GPU writes
- geometry streaming patterns
- conservative synchronization around copied ranges

### H3 — `other` outside-RP/barrier source

Question:

> Which concrete Draw-preparation callers account for the ~86% of outside-RP endings and all currently attributed Draw barriers in `other`?

Subdivide at least:

- TextureCache preparation/synchronization
- image layout transitions / feedback handling
- pipeline configuration paths outside BufferCache
- query/cache interactions
- explicit `RequestOutsideRenderPassOperationContext()` callers
- buffer-copy calls that execute outside the current category scope

This is the **next immediate diagnostic step**.

---

## 14. Experiment discipline

1. Keep `lab/dc95-arm64-baseline` immutable.
2. Use a new experimental branch for each behavioral hypothesis.
3. Instrument first when the causal path is not isolated.
4. Change only one semantic variable per optimization A/B.
5. Keep diagnostic switches default OFF unless the build's entire purpose is passive measurement.
6. Record exact game version, scene, settings, driver, branch, HEAD, run id, and log filename.
7. Compare the same scene/settings/resolution whenever possible.
8. Do not call a performance gain real if visual/correctness behavior is broken.
9. Do not rerun or launch a new ARM64 build unless the user explicitly authorizes it.
10. A failed workflow parsing/transplant step is not a runtime A/B result.

---

## 15. Build/CI rule

User rule:

> Do not build until explicit permission is given.

When permission is given for one build, run exactly that authorized build. Do not automatically rerun a failed job or start a second build without new permission.

One-shot push triggers may be used only to invoke an otherwise manual workflow when the connector cannot dispatch it directly. Immediately restore the workflow to `workflow_dispatch`/manual-only state and verify the restore commit did not trigger another build.

---

## 16. Diagnostic controls currently available

Full-flow debug controls, default OFF in source:

- `X1 Log: Descriptor Ring`
- `X1 Log: Scheduler / Sync`
- `X1 Log: Present / Frame Pacing`
- `X1 Log: Pipeline / Shader`
- `X1 Log: Upload / Barrier`
- `X1 Log: QCOM Workaround Hits`

Draw/Dispatch A/B controls, default OFF:

- `X1 A/B: Skip Matching Draw`
- `Draw signature (hex)`
- `X1 A/B: Skip Matching Dispatch`
- `Dispatch signature (hex)`

Main log output prefixes:

- `[X1-FLOW][SCHED]`
- `[X1-FLOW][PIPE]`
- `[X1-FLOW][PRESENT]`
- `[X1-FLOW][UPLOAD]`
- `[X1-FLOW][QCOM]`
- `[X1-FLOW][DBUF]`
- `[X1-FLOW][ORIGIN]`
- `[X1-FLOW][ORIGIN-CALL]`
- `[X1-FLOW][BUFFER]`
- `[X1-FLOW][AB]`
- `[X1-DBUF]`

On the current non-portable Windows setup the normal log is under `%APPDATA%\eden\log\eden_log.txt`.

---

## 17. Known diagnostic branches

- `lab/dc95-arm64-baseline` — immutable control
- `exp/x1-descriptor-ring` — descriptor-ring profiler
- `exp/x1-full-flow-profiler` — scheduler/present/pipeline/upload/QCOM full-flow profiler
- `exp/x1-draw-dispatch-correlation` — Draw vs Dispatch origin attribution and signature A/B
- `exp/x1-buffer-category-correlation` — current category decomposition experiment

Do not collapse these branches into the control merely for convenience.

---

## 18. External-reference priority

When outside evidence is needed, prefer:

1. Qualcomm official documentation
2. Eden upstream/source history
3. validated Cemu Adreno patterns
4. Kenji
5. Ryubing
6. SnapRyu runtime experiments

ARM64 portability and Adreno Vulkan correctness/performance are separate dimensions. Do not mix them into one explanation without evidence.

---

## 19. Cross-project lesson from SnapRyu

SnapRyu experiments repeatedly showed that successful queue submission does not prove the workload is safe or efficient on Qualcomm. Draw/Dispatch workload/resource/state/lifetime combinations can determine whether progress continues, stalls, or becomes extremely slow.

The current Eden work connects that lesson to measurable backend costs:

`Draw/Dispatch entry -> resource preparation -> upload/copy -> render-pass boundary/barrier -> submit/scheduler wait`

The goal is not to indiscriminately skip Draw/Dispatch. It is to identify which preparation behavior is unnecessarily expensive on Windows X1 and preserve correctness while reducing it.

---

## 20. Canonical workflow for future tabs

At the start of a new tab, read in this order:

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `CURRENT_HANDOFF.md`
4. Verify the Lab repository's current branch/HEAD before editing.

Then continue from the `Next action` section of `CURRENT_HANDOFF.md` without reconstructing the project from conversation memory.
