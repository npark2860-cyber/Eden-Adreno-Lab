# Eden Snapdragon / Adreno X1-85 Technical Bible

> Canonical durable technical reference for `npark2860-cyber/Eden-Adreno-Lab`.
>
> Last consolidated: 2026-08-27 (KST)
>
> Current work-in-progress state belongs in `CURRENT_HANDOFF.md`. Chronological experiment outcomes belong in `DEBUG_HISTORY.md`. Exact next implementation scope belongs in the current `NEXT_ACTION_*.md` file.

---

## 1. Project purpose

This project investigates why Eden on Windows ARM64 Snapdragon X / Adreno X1-85 is comparatively stable in demanding titles such as The Legend of Zelda: Tears of the Kingdom (TOTK), yet substantially slower than expected.

The core research question is:

> Is Eden already near the hardware/driver ceiling on Adreno X1-85, or is Eden losing material performance through resource preparation, repeated uploads/copies, render-pass disruption, synchronization, or Qualcomm-specific policy choices that are suboptimal on Windows ARM64?

The working method is always:

`source inspection -> passive instrumentation -> one-variable A/B -> matched runtime verification -> promote only proven facts`

Do not replace measured causes with architectural intuition. Correlation identifies the next A/B; it does not by itself justify a production optimization.

---

## 2. Immutable source control

### Eden source mirror

- repository: `eden-emulator/mirror`
- exact known-good source SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- diagnostic runtime identification may appear as `HEAD-dc95cd09ee-HEAD`
- official Nightly tag associated with the control source: `v1786904188.dc95cd09ee`
- nightly date: 2026-08-16

### Lab repository

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- immutable control branch: `lab/dc95-arm64-baseline`

The dc95 source baseline is fixed for the current experiment family. Never silently substitute a later Eden commit when interpreting an A/B.

A later imported source such as `0295dc5fff9b2977e753e7c126cc870abb07ee3f` is not the control and must not be used as though it were dc95.

---

## 3. Windows ARM64 build provenance

Known dc95-era CI reference:

- `Eden-CI/Workflow` commit: `afead830f3a444427f9fdfd841218f932465c03a`
- toolchain: MSYS2 `CLANGARM64`
- compiler: clang
- architecture family: ARM64 standard build

Known control artifacts established during the project include:

- PGO control run `32917736899`, artifact `Eden-dc95-ARM64-clean-PGO`, artifact id `9589236155`
- standard control run `32914980539`, artifact id `9588440312`

Experimental workflows must always verify that the checked-out Eden tree remains exactly:

`dc95cd09eea9749250fe31a3072684d341d19417`

---

## 4. Primary runtime platform

Current primary host/test environment:

- Windows 11 ARM64
- Snapdragon X1E80100 family
- Qualcomm Adreno X1-85 GPU
- Qualcomm Adreno Vulkan Driver `512.863.0`
- Vulkan `1.3.295`
- reported VRAM `6.00 GiB`
- host CPU threads: 12
- host RAM: about 15.6 GiB

Primary title:

- The Legend of Zelda: Tears of the Kingdom
- title id `0100F2C0115B6000`
- current matched Uniform diagnostics use TOTK 1.4.2

Observed high-level runtime distinction that must be preserved in interpretation:

- Eden dc95 family: generally continuous/stable feeling, with a normal gameplay ceiling around ~20 FPS and severe field/heavy-scene dips that may reach ~3–6 FPS
- Ryubing/Kenji user observation: good sections can hold 30 FPS, but freezing is the major problem

Do not force the normal ~20 FPS ceiling and the severe 3–6 FPS dips into one root cause.

The user intentionally closes Eden after enough logging because logs become very large. End-of-log `ForceStop` in these matched runs is not a crash by itself.

---

## 5. Evidence vocabulary

Use these labels consistently:

- **CONFIRMED**: directly supported by source, runtime evidence, or a controlled A/B.
- **STRONG**: multiple observations support the conclusion, but causality is not yet isolated by A/B.
- **REFERENCE**: useful source architecture or comparison evidence.
- **REJECTED**: tested and unable to explain the primary bottleneck under the tested conditions.
- **OPEN**: plausible and not yet isolated.

A large counter is not automatically a bottleneck. A causal performance claim requires an A/B or timing evidence that changes the relevant cost while preserving correctness.

---

## 6. Qualcomm behavior confirmed on Windows X1

Exact dc95 Vulkan applies generic Qualcomm handling to Windows X1-85. Runtime warnings confirm active assumptions/workarounds including:

- scaled vertex format emulation
- broken descriptor aliasing
- broken custom border color
- broken border color swizzle
- broken color write enable
- broken shader float controls
- broken shader atomic int64
- broken workgroup memory explicit layout
- sampler reservation because the driver reports 65536 samplers; Eden reserves 16384 and allows use of 49152
- higher-than-reported binding-limit handling

These are compatibility facts, not automatically performance bugs.

`Device::IsTiler()` is true for the proprietary Qualcomm path in exact dc95, including Windows X1. Tiler policies can therefore be active outside Android.

Do not globally remove Qualcomm workarounds without a one-variable correctness-safe test.

---

## 7. Causes already weakened or rejected for TOTK steady-state performance

### Present / swapchain / frame pacing

Measured acquire/present and pacing costs are too small to explain the persistent ~20 FPS ceiling.

Status: **REJECTED as primary steady-state cause**.

### Pipeline / shader compilation

Pipeline/shader creation can contribute startup/loading stutter, but long steady gameplay remains slow when steady-state build/emission activity is absent.

Status: **REJECTED as primary steady-state cause; retained as transient-stutter contributor**.

### Descriptor Buffer Ring

Exact dc95 policy has an 8-frame in-flight ring and can wait/finish on reuse/exhaustion, but matched TOTK profiler runs measured the relevant descriptor-ring activity as effectively inactive for the current path.

Status: **REJECTED as current primary TOTK bottleneck**.

### WaitWorker / frame pacing as standalone cause

Scheduler GPU waits are substantial, but the measured frame pacing/WaitWorker side is not sufficient to explain the primary ceiling.

Status: **REJECTED as standalone primary cause**.

---

## 8. Scheduler and render-pass synchronization facts

Relevant exact-dc95 scheduler behavior includes:

- `Wait(tick)` can flush as required and waits on the master semaphore
- `Finish()` presubmits/submits, waits, then allocates a new context
- upload command-buffer transitions are conservative
- exact dc95 frame pacing is not the later 1 ms `spin_tail` variant

Full-flow runtime established a recurring cost chain:

`staging upload / buffer copy rises`

`-> outside-render-pass endings rise`

`-> post-RP barriers and submits rise`

`-> scheduler GPU waits rise`

`-> FPS falls`

This is a backend cost relationship, not permission to suppress a required barrier or render-pass exit.

---

## 9. Draw / Dispatch architecture

A graphics draw is not just `vkCmdDraw*`. Resource preparation occurs before the final command:

`RasterizerVulkan::Draw`

`-> PrepareDraw`

`-> GraphicsPipeline::Configure`

`-> BufferCache::UpdateGraphicsBuffers(is_indexed)`

`-> BufferCache host binding / resource preparation`

`-> texture/image preparation as required`

`-> vkCmdDraw*`

Draw/Dispatch correlation showed that steady heavy resource preparation is overwhelmingly Draw-driven. Dispatch is materially smaller in the matched TOTK workload.

Heavy Draw work is not confined to one exact draw signature, so a single-signature skip is not a general optimization strategy.

---

## 10. Buffer-category decomposition

Profiler categories include:

- index
- vertex
- uniform
- storage
- texture-buffer
- transform-feedback
- other

Earlier steady gameplay decomposition established an extreme number of tiny graphics Uniform upload requests, around 10k+ requests/frame with payloads only a few hundred bytes on average.

Earlier severe-dip windows additionally showed:

- large staging upload growth
- Vertex/Index copy spikes
- texture refresh spikes
- large `other` outside-render-pass/barrier growth

Therefore the durable performance picture is:

### Normal ~20 FPS ceiling

- persistent tiny-Uniform processing pressure is a primary current candidate
- valid recurring alias synchronization/render-pass disruption remains a secondary recurring cost

### Severe 3–6 FPS dips

- persistent costs above
- plus bulk staging and Vertex/Index copy pressure
- plus texture refresh / other scene-dependent resource traffic

---

## 11. Alias synchronization path — resolved structure

The Draw-side alias path was isolated as:

`Draw Configure`

`-> FillImageViews`

`-> PrepareImage`

`-> SynchronizeAliases`

`-> CopyImage`

`-> generic direct route`

`-> TextureCacheRuntime::CopyImage`

`-> RequestOutsideRenderPassOperationContext()`

`-> vkCmdCopyImage`

Alias-route telemetry established that the direct Vulkan alias-copy path was a major source of Draw outside-render-pass events in the measured run.

`RequestOutsideRenderPassOperationContext()` is required for the real `vkCmdCopyImage` path. Do not remove or suppress it merely to reduce the counter.

Do not reopen already-zero or eliminated alias branches such as reinterpret/convert/BPB fallback/resolve-shadow invalidation without new evidence.

---

## 12. Alias trivial-dedupe hypothesis — CLOSED

The bounded alias synchronization runtime measured:

- copies: 194,396
- sameFrame: 59,722
- sameDraw: 0
- consecutiveFrame: 111,202
- sameSrcTick: 0
- advancedSrcTick: 190,823
- regressedSrcTick: 0
- sameSignature: 190,823
- sameStateSignature: 0
- regions: 194,396
- maxRegions: 1
- tableOverflow: 0

Every tracked repeated `(dst,src)` pair/region had the same copy-region signature but a strictly newer source `modification_tick`.

Therefore:

- same pair + same region does not prove redundant work
- same source tick + same region had zero measured candidates
- simple alias-copy dedupe is not supported by the evidence
- same-frame collapse is unsafe because the source version advances and the repeats occur across Draws

Status: **CONFIRMED / trivial alias dedupe CLOSED**.

---

## 13. Exact dc95 graphics Uniform design facts

### Vulkan persistent binding policy

Exact dc95 Vulkan has:

`HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`

The generic graphics Uniform binding loop therefore revisits enabled Vulkan Uniform bindings rather than using the persistent dirty-binding behavior available under other policy configurations.

### Classic cached path

The classic path calls `SynchronizeBuffer(buffer, device_addr, size)`.

`SynchronizeBuffer()` checks CPU-dirty upload ranges through the existing memory tracker.

- zero upload bytes -> clean result; physical upload can be avoided
- dirty bytes present -> existing `UploadMemory(...)` path performs the update

`uniform_cache_hits` corresponds to the clean / zero-upload outcome.

### Adaptive fast path

`TickFrame()` uses recent Uniform hit/shot history to decide whether small Uniforms should bypass the cache through `uniform_buffer_skip_cache_size`.

Exact dc95 Vulkan fast Uniform handling performs mapped upload staging and descriptor insertion, then copies the guest bytes into the mapped span.

Therefore the fast path is:

> a stall-avoidance mapped re-stream path, not persistent payload reuse.

This distinction is central to the current investigation.

---

## 14. Uniform stream/reuse runtime — CONFIRMED

Branch:

`exp/x1-uniform-stream-reuse`

Authorized successful build:

- workflow `Build dc95 X1 Uniform Stream Reuse`
- run `33037180003`
- job `98402328028`
- attempt 1
- build HEAD `8f33dc37c98afa134ad5efbbf14ab85df388ee42`
- artifact `Eden-dc95-X1-uniform-stream-reuse`
- artifact id `9633005533`
- SHA-256 `03491e648026bf0226f2bbd3817d4a979040cc027991af45f9117c2a68564860`

Matched runtime established:

- fast mapped-stream processing dominates graphics Uniform visits
- gameplay fast reason was adaptive `fastSkip`
- measured gameplay `fastAlignment=0`
- classic cached path was mostly clean / zero-upload
- exact `(stage,index,device_addr,size)` fast keys repeat heavily across Draws
- `sameDraw=0`, so the repetition is cross-Draw rather than duplicate calls inside one Draw

Representative aggregate from one matched 600-frame gameplay range:

- visits: 9,927,196
- fast: 9,762,092 = 98.34%
- cached: 165,104
- cached clean: 154,847 = 93.79% of cached
- cached actual upload: 10,257
- fastAlignment: 0
- fastSkip: 9,762,092

The previous tiny Uniform `uploadReq` explosion is therefore overwhelmingly produced by the adaptive mapped-stream policy rather than classic cached dirty uploads.

Status: **CONFIRMED**.

---

## 15. Uniform payload fingerprint runtime — STRONG RUNTIME EVIDENCE

Branch:

`exp/x1-uniform-payload-fingerprint`

Authorized successful build:

- workflow `Build dc95 X1 Uniform Payload Fingerprint`
- run `33040377420`
- job `98412364840`
- attempt 1
- build HEAD `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- artifact `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id `9634160587`
- artifact size 31,299,993 bytes
- SHA-256 `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

Instrumentation design:

- deterministic 1/16 Uniform-key sampling
- fingerprint computed from the already-copied staging span
- no second guest-memory read
- fixed bounded sample table
- observation-only; no Uniform skip/reuse/batching or dirty-state mutation

Matched gameplay aggregate used for the current conclusion: report frames 1320–3000 inclusive, 1800 frames.

### Uniform path totals

- visits: **41,733,585**
- fast: **41,188,346 = 98.69%**
- fastAlignment: **0**
- fastSkip: **41,188,346**
- cached: **545,239**
- cachedClean: **513,129 = 94.11% of cached**
- cachedUpload: **32,110**
- average fast payload: **410.46 bytes**
- fast streams/frame: **22,882.4** on this matched route

### Sampled payload totals

- samples: **1,890,393**
- uniqueSamples: **14,526**
- repeatSamples: **1,835,334**
- sameFingerprint: **1,792,196**
- changedFingerprint: **43,138**
- sampleOverflow: **40,533**

Among tracked repeat samples:

- **97.65% same fingerprint**
- **2.35% changed fingerprint**

Among same-frame repeated samples with classification:

- same fingerprint: **1,445,069**
- changed fingerprint: **12,119**
- **99.17% same fingerprint**

Representative report blocks remain in the mid/high-90% same-fingerprint range across the run, demonstrating persistence rather than a single spike.

Interpretation:

> Eden's dominant adaptive fast Uniform path repeatedly stages the same Uniform identity, and sampled repeated identities overwhelmingly carry the same payload fingerprint, especially within the same frame.

This is strong evidence of avoidable-looking re-stream traffic. It is not yet permission to reuse an old staging allocation because descriptor/staging lifetime and in-flight GPU use must remain correct. A 64-bit fingerprint is strong equality evidence, not mathematical byte-for-byte proof.

---

## 16. Current causal hypothesis

The strongest current steady-state hypothesis is now more specific than “Uniform uploads are numerous”:

> Exact-dc95 Vulkan's adaptive small-Uniform skip-cache policy sends the overwhelming majority of graphics Uniform visits through mapped staging re-streaming even though the existing classic cached path is mostly clean, and sampled repeated fast-stream identities overwhelmingly carry unchanged payload fingerprints.

This architecture can explain a continuous CPU/driver/bookkeeping burden without requiring a visible freeze on every frame.

However, the payload experiment is still observational. It does not yet prove the fast-stream policy is responsible for the ~20 FPS ceiling in frame-time terms.

A causal A/B is required next.

---

## 17. Safest next A/B — Qualcomm/X1 adaptive Uniform cache policy

The next experiment must not begin with custom payload dedupe or previous-staging reuse.

The safest causal test is a Qualcomm/X1 diagnostic checkbox, default OFF, with the following semantics:

### A/B OFF

Exact existing dc95 behavior.

- alignment-required stream can select fast path
- adaptive small-buffer `fastSkip` can select fast path
- current staging/descriptor/guest-copy behavior remains unchanged

### A/B ON

Change only the adaptive policy selection:

- `needs_alignment_stream` remains authoritative and still uses fast mapped streaming
- adaptive `fastSkip` is prevented from selecting mapped streaming
- affected Uniforms fall through to Eden's existing classic cached `SynchronizeBuffer()` path
- memory dirty semantics remain existing Eden behavior

Do not in this A/B:

- enable persistent Vulkan Uniform bindings
- add previous-staging reuse
- add same-key/hash dedupe
- change `SynchronizeBuffer()` semantics
- change descriptor/staging lifetime
- touch scheduler source
- change barriers or render-pass behavior
- alter alias synchronization
- alter Vertex/Index/Storage paths

The detailed implementation and validation contract is in `NEXT_ACTION_UNIFORM_CACHE_AB.md`.

---

## 18. A/B interpretation tree

### FPS materially rises and stability remains good

Strong causal confirmation that adaptive Uniform re-streaming is a major steady-state bottleneck. Then design a production-safe Qualcomm policy that preserves cached reuse without introducing stalls.

### FPS materially rises but freezing/stalls appear

The cost has shifted from continuous re-streaming into synchronization/stall events. This would match the user's observed Ryubing/Kenji tradeoff and make buffer/resource lifetime and in-flight-range handling the next design target.

### FPS does not materially improve

The huge fast-stream count is real architectural overhead but not the dominant frame-time limiter. Priority returns to valid alias/render-pass disruption and heavy-scene bulk copy paths.

### Correctness breaks

Do not promote the optimization. Determine whether the classic path exposes a Qualcomm-specific stale-data/synchronization issue before drawing performance conclusions.

---

## 19. Ryubing / Kenji comparison boundary

Reference source comparison shows Ryubing/Kenji maintain explicit resource state such as pending data/ranges, mirrors, and fence-backed lifetime, and can reuse certain `(offset,size)` mirror resources while respecting in-flight writes.

This is structurally different from exact-dc95 Vulkan's mapped fast Uniform path, which re-streams the payload on each fast visit.

Do not overstate the comparison:

- matched Ryubing/Kenji Uniform counters have not been measured
- it is not proven that they perform fewer total Uniform updates in the same scene
- it is not proven that they never break render passes

The useful design lesson is narrower:

> preserve resource identity/range/lifetime long enough to avoid unnecessary physical work where correctness allows it.

The user-observed 30 FPS + freezing behavior in Ryubing/Kenji is an important runtime clue, not a source-level proof of the exact mechanism.

---

## 20. Heavy-scene open work

Even if the Uniform A/B solves part of the normal ceiling, severe 3–6 FPS dips remain a separate composite problem.

Open heavy-scene targets include:

- Vertex/Index copy explosions
- bulk staging growth
- texture refresh spikes
- valid alias synchronization / render-pass fragmentation

Do not declare the whole TOTK performance problem solved from a steady-state Uniform win alone.

---

## 21. Experiment discipline

1. Keep `lab/dc95-arm64-baseline` immutable.
2. Keep Eden source fixed at exact dc95 for this experiment family.
3. Use a new branch for each behavioral hypothesis.
4. Instrument before optimizing when the causal path is not isolated.
5. Change one semantic variable per A/B.
6. Diagnostic switches must default OFF unless the build is passive-measurement-only.
7. Record game version, settings, driver, branch, build HEAD, run id, artifact, and log identity.
8. Compare the same save/route/settings as closely as possible.
9. Do not call a performance gain valid if correctness is broken.
10. Do not remove required synchronization merely because its counter is high.
11. Do not reinterpret user-initiated `ForceStop` as a crash.
12. Do not rerun a failed ARM64 workflow without fresh explicit authorization.

---

## 22. Build / CI hard rule

User rule:

> Do not build until explicit permission is given.

One fresh explicit authorization permits exactly **one** ARM64 build attempt.

If that attempt fails:

- stop
- diagnose statically/logically
- do not rerun until the user explicitly authorizes another attempt

A one-shot branch-scoped push trigger may be used when the connector cannot dispatch a manual workflow. Immediately restore the workflow to `workflow_dispatch` only and verify that the restore does not create another run.

Documentation-only commits must not be used as an excuse to create another build.

---

## 23. Current diagnostic branches

Important branch history:

- `lab/dc95-arm64-baseline` — immutable control
- `exp/x1-descriptor-ring` — descriptor-ring measurement
- `exp/x1-full-flow-profiler` — scheduler/present/pipeline/upload/QCOM measurement
- `exp/x1-draw-dispatch-correlation` — Draw/Dispatch attribution
- `exp/x1-buffer-category-correlation` — buffer-category attribution
- `exp/x1-texture-fill-reasons` — texture/FillImageViews reason split
- `exp/x1-alias-copy-reasons` — alias copy route split
- `exp/x1-alias-sync-redundancy` — alias state/region repeat telemetry
- `exp/x1-uniform-stream-reuse` — Uniform fast/cached path telemetry
- `exp/x1-uniform-payload-fingerprint` — sampled repeated payload fingerprint telemetry

The next behavioral experiment is to be prepared on a new branch such as:

`exp/x1-uniform-cache-ab`

Do not modify the immutable control branch.

---

## 24. Canonical handoff workflow

At the start of a new tab, read in this order:

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `CURRENT_HANDOFF.md`
4. `LAB_BOOTSTRAP.md`
5. the `NEXT_ACTION_*.md` referenced by `CURRENT_HANDOFF.md`

Then verify the Lab repository's actual current branch/HEAD before editing.

Do not reconstruct the project from conversational memory when the repository documents disagree.

Continue directly from the `NEXT ACTION` section of `CURRENT_HANDOFF.md`.

Before starting any ARM64 Action, check the build-authorization state in `CURRENT_HANDOFF.md`. Fresh explicit permission is mandatory for every attempt.
