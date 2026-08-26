# CURRENT HANDOFF — Eden Snapdragon / Adreno X1-85

> Current checkpoint only. Keep this file short and overwrite/update it as the investigation moves.
>
> Updated: 2026-08-26 23:12 KST

---

## 1. Current objective

Explain and reduce:

- normal TOTK gameplay ceiling: about **20 FPS**
- heavy sections: about **15-6 FPS**

The investigation has already narrowed the backend cost from generic Vulkan performance to:

`Draw preparation -> Uniform / Vertex / other resource work -> render-pass break/barrier/submit -> scheduler GPU wait`

The next immediate goal is **not** another broad profiler. It is to identify what concrete caller(s) make up Draw category `other`, while separately preserving the Uniform and Vertex findings.

---

## 2. Repositories / current source state

### Lab repository

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-buffer-category-correlation`

Current branch HEAD after restoring manual-only CI:

`0ed8df216fbe416f4f569a9490c5f8f128bb0cfc`

HEAD message:

`ci: restore manual-only X1 buffer-category build`

### Exact Eden source used by the experiment

`eden-emulator/mirror`

`dc95cd09eea9749250fe31a3072684d341d19417`

Do not replace dc95 with later `0295dc5...`.

### Immutable control branch

`lab/dc95-arm64-baseline`

Do not modify it.

---

## 3. Last known-good control

Known-good Eden runtime family:

`Eden Development Build | master-dc95cd09ee-master`

Observed behavior:

- stable
- ordinary gameplay about 20 FPS
- heavy field sections about 15-6 FPS
- no characteristic freeze feeling

Official control reference:

- Nightly tag `v1786904188.dc95cd09ee`
- 2026-08-16

---

## 4. Current test build

Authorized BufferCategory build:

- workflow run: `32967450066`
- job: `98173182429`
- build result: **success**
- build head SHA: `3780a5746a35d22e01dbe87c27f14c7e9fc37e1b`
- branch: `exp/x1-buffer-category-correlation`

Artifact:

- id: `9607231624`
- name: `Eden-dc95-X1-draw-dispatch-correlation`
- digest: `sha256:877b2d9e1db44b69e55f93b20d2ed94237e6d75d1be60b9ee9de02a7f2ed76b0`

The artifact name is inherited from the previous Draw/Dispatch workflow. This particular run includes the BufferCategory transplant; do not reject it based on the artifact label.

The workflow has been restored to manual-only. **Do not start/re-run another ARM64 build without new explicit user permission.**

---

## 5. Latest runtime log

Latest uploaded log in the current work session:

`eden_log(5).txt`

Logical Eden filename:

`eden_log.txt`

Runtime:

- Eden `HEAD-dc95cd09ee-HEAD`
- TOTK title `0100F2C0115B6000`
- game version **1.4.2**
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295

Important renderer settings:

- Vulkan
- 1x resolution
- no AA
- FSR
- Docked
- GPU accuracy Low
- async presentation true
- async GPU emulation true
- compute pipelines false
- async shaders false
- buffer reorder enabled (`disable_buffer_reorder=false`)
- reactive flushing true
- barrier feedback loops true
- Mailbox VSync
- force max clock true

Diagnostic switches in latest log:

- X1 Scheduler / Sync: true
- X1 Present / Frame Pacing: true
- X1 Pipeline / Shader: true
- X1 Upload / Barrier: true
- X1 QCOM Workaround Hits: true
- X1 Descriptor Ring: true

Behavioral A/B switches:

- `x1_ab_skip_draw=false`
- Draw signature `0`
- `x1_ab_skip_dispatch=false`
- Dispatch signature `0`

Therefore the latest run is a passive measurement baseline. No Draw or Dispatch was intentionally skipped.

---

## 6. Confirmed / strong current findings

### CONFIRMED — Present is not the primary steady-state bottleneck

Present/acquire/pacing totals are much too small to explain the observed frame time. Do not return to VSync/present as the first target.

### CONFIRMED — Pipeline compilation is not the steady-state primary bottleneck

It contributes startup/loading stutters but steady gameplay remains slow with pipeline/shader counters at zero.

### CONFIRMED — DescriptorBufferRing is not active as the current TOTK bottleneck

The latest run enabled its profiler and reports zero allocation/reuse-wait/chunk-switch/exhaustion behavior in the relevant path.

### STRONG — Draw preparation is the dominant origin

Previous Draw/Dispatch correlation showed almost all heavy individual calls are Draw. Heavy Draws are mostly ordinary indexed-triangle, single-instance draws with varying vertex counts, not one unique signature.

### STRONG — Normal ~20 FPS has a persistent Uniform tiny-upload burden

Latest frames 960-3120, Draw-side classified upload:

- Uniform: **10,795.857 MiB / 87.2%**
- Other: 1,259.508 MiB / 10.2%
- Vertex: 294.508 MiB / 2.4%
- Index: 18.773 MiB
- Storage: 17.980 MiB

Uniform:

- 26,069,240 upload requests / 2,280 frames
- about **11,434 requests/frame**
- about **434 bytes/request** average

This is the strongest current candidate for the ordinary 20 FPS ceiling.

### STRONG — Slow sections add Vertex-copy and `other` explosions

Frame-1080 120-frame window:

- interval equivalent ~13.1 summary FPS
- staging upload 977.378 MiB
- BufferCopy 556.804 MiB
- barriers 12,550

Draw Vertex:

- upload 88.844 MiB
- **copy 375.469 MiB**
- 4,454 copy calls
- 1,169 outside-RP endings

Draw Other:

- upload 263.296 MiB
- **4,654 outside-RP endings**
- **5,062 barriers**

Normal ~20 FPS-class frame-1320/1440 windows show only ~6.55-7.58 MiB Vertex copy.

### STRONG — `other` owns the render-pass/barrier problem

Over frames 960-3120, Draw outside-RP share:

- other: **85.95%**
- vertex: 9.54%
- index: 1.67%
- uniform: 1.50%
- storage: 1.34%

All Draw-category barriers currently attributed by this profiler are recorded in `other`.

---

## 7. Rejected / do not restart first

Do not spend the next cycle on these unless new evidence appears:

- DescriptorBufferRing tuning
- Present/VSync/frame pacing
- steady-state pipeline/shader compile optimization
- skipping one exact Draw signature
- removing all Qualcomm workarounds at once
- assuming X1-85 hardware itself is simply a 20 FPS ceiling

---

## 8. Live hypotheses

### H1 — `other` contains the main RP-break/barrier caller

Likely classes to distinguish by source inspection/instrumentation:

- TextureCache/resource synchronization in Draw preparation
- image layout/feedback transitions
- explicit `RequestOutsideRenderPassOperationContext()` callers
- query/cache operations
- pipeline/configuration work outside the named BufferCache scopes
- copy/barrier work executed outside the current BufferCategory scope

Do not assume which one is dominant before adding caller/reason attribution.

### H2 — Uniform updates are correct in principle but too granular/frequent

Need to determine why Draw preparation makes ~11k tiny uniform uploads per frame:

- genuine guest changes vs over-invalidation
- dirty tracking granularity
- already-updated binding reuse
- stream/ring allocation behavior
- safe coalescing/batching opportunity

Do not blindly suppress uniform updates.

### H3 — Vertex copy amplification creates the deep dips

Need to find why some windows jump from ~7 MiB to ~375 MiB vertex copy:

- aliasing
- dirty range amplification
- reorder/upload path
- streaming geometry
- CPU/GPU write synchronization

---

## 9. Files added/changed for the current experiment

Important experiment tooling:

- `tools/adreno_lab/transplant_dc95_buffer_category_correlation.py`
- `tools/adreno_lab/analyze_x1_buffer_category_log.py`
- existing Draw/Dispatch correlation transplant and A/B control scripts
- `.github/workflows/build-dc95-x1-full-flow.yml` was temporarily given a branch/path push trigger for the one authorized build, then restored to manual-only

Do not treat temporary CI trigger commits as behavior changes in Eden runtime source.

---

## 10. NEXT ACTION — start here in the next tab

### Step 1 — no build yet

Inspect exact dc95 Draw preparation source and the current BufferCategory transplant to identify every operation that occurs while origin=`Draw` but category=`other`.

The first target is to create a **reason-level map of `other`**.

At minimum distinguish concrete callers for:

- outside-render-pass requests
- barriers
- staging uploads not owned by Uniform/Vertex/Index/Storage scopes

### Step 2 — prepare a separate experiment branch

Do not mutate:

- `lab/dc95-arm64-baseline`
- `exp/x1-full-flow-profiler`
- `exp/x1-draw-dispatch-correlation`
- `exp/x1-buffer-category-correlation`

Suggested next branch:

`exp/x1-draw-other-reasons`

The next instrumentation should be passive/default-safe and report aggregated reason classes, avoiding hot-event spam.

### Step 3 — only after `other` is isolated

Choose one semantic optimization A/B:

- reduce one unnecessary RP break/barrier class, **or**
- optimize Uniform tiny-upload behavior, **or**
- reduce Vertex copy amplification

Do not combine these in one behavioral build.

### Step 4 — build only with explicit permission

User rule remains absolute:

**No ARM64 build/re-run until the user explicitly says to proceed.**

---

## 11. New-tab start sentence

Use:

`Eden Adreno 구동분석 작업을 이어간다. GitHub npark2860-cyber/Eden-Adreno-Lab의 TECH_BIBLE.md, DEBUG_HISTORY.md, CURRENT_HANDOFF.md를 읽고 exp/x1-buffer-category-correlation의 실제 HEAD까지 확인한 뒤 CURRENT_HANDOFF의 NEXT ACTION부터 바로 진행해.`
