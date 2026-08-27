# DEBUG HISTORY — Eden Adreno X1-85

This file records confirmed experiment outcomes and the current diagnostic chain. It was absent from the working branch before the 2026-08-27 Uniform investigation, so earlier history remains represented by the existing TECH_BIBLE / maps / handoff documents rather than being reconstructed here from memory.

## 2026-08-27 — X1 alias synchronization redundancy runtime

Baseline:

- exact Eden source `dc95cd09eea9749250fe31a3072684d341d19417`
- branch `exp/x1-alias-sync-redundancy`
- authorized build run `33024690895`, job `98363162523`, attempt 1
- build HEAD `804f394c5db280f842a01113e6ca92f7ad57d219`
- result success
- artifact `Eden-dc95-X1-alias-sync-redundancy`, id `9628554127`
- artifact SHA-256 `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

Matched runtime:

- TOTK 1.4.2
- Adreno X1-85, driver 512.863.0, Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- log `eden_log(9).txt`
- user stopped the emulator intentionally when the log became large; not a crash

Aggregate alias-sync result:

- copies 194,396
- sameFrame 59,722
- sameDraw 0
- consecutiveFrame 111,202
- sameSrcTick 0
- advancedSrcTick 190,823
- regressedSrcTick 0
- sameSignature 190,823
- sameStateSignature 0
- regions 194,396
- maxRegions 1
- tableOverflow 0

Conclusion — CONFIRMED:

Repeated alias pair/region requests are not trivial unchanged-state duplicates. Every tracked recurrence advances source `modification_tick`; there are zero same-source-tick + same-region candidates. Do not implement simple alias-copy dedupe from this evidence.

The established path remains:

`Draw Configure -> FillImageViews -> PrepareImage -> SynchronizeAliases -> CopyImage -> direct Vulkan copy -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

## 2026-08-27 — exact dc95 graphics Uniform source analysis

Motivation:

Steady TOTK gameplay continues to show roughly 10k–12k tiny graphics Uniform upload requests per frame, while alias trivial dedupe is now closed.

Exact source facts — CONFIRMED:

1. Vulkan `BufferCacheParams::HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
2. Generic graphics Uniform binding begins with `dirty = ~0U`; the persistent dirty-binding mask is only consumed when the policy enables persistent Uniform bindings.
3. Every visited graphics Uniform increments `uniform_cache_shots[0]`.
4. Classic cached path calls `SynchronizeBuffer()`.
5. `SynchronizeBuffer()` returns true when `ForEachUploadRange()` yields zero upload bytes, and returns false after a real `UploadMemory()`.
6. `uniform_cache_hits[0]` therefore counts classic cached visits that required zero upload bytes.
7. `TickFrame()` uses recent hit/shot history to toggle `uniform_buffer_skip_cache_size`.
8. Exact dc95 Vulkan fast graphics Uniform path calls `BindMappedUniformBuffer()`, which performs `staging_pool.Request(size, MemoryUsage::Upload)` and descriptor insertion; generic code then copies guest bytes with `device_memory.ReadBlockUnsafe()`.

Interpretation — CONFIRMED DESIGN FACT:

The fast path is a stall-avoidance re-stream path, not persistent payload reuse.

## 2026-08-27 — Uniform stream/reuse runtime

Branch:

`exp/x1-uniform-stream-reuse`

Authorized build:

- workflow `Build dc95 X1 Uniform Stream Reuse`
- run `33037180003`
- job `98402328028`
- attempt 1
- build HEAD `8f33dc37c98afa134ad5efbbf14ab85df388ee42`
- result success
- artifact `Eden-dc95-X1-uniform-stream-reuse`
- artifact id `9633005533`
- SHA-256 `03491e648026bf0226f2bbd3817d4a979040cc027991af45f9117c2a68564860`

Runtime result — CONFIRMED:

- fast Uniform path dominates gameplay Uniform processing
- representative matched gameplay aggregate previously measured over frame 1200–1680: 9,762,092 fast streams out of 9,927,196 visits (98.34%)
- fastAlignment = 0 in gameplay; fast path selection was entirely adaptive skip policy (`fastSkip`)
- classic cached path was mostly clean: 154,847 clean out of 165,104 cached visits (93.79%)
- exact fast key `(stage,index,device_addr,size)` repeated heavily across Draws
- `sameDraw = 0`; repetition is cross-Draw, not duplicate calls inside one Draw

Conclusion:

The prior tiny Uniform `uploadReq` explosion is overwhelmingly caused by the adaptive fast mapped-stream policy rather than by classic cached dirty uploads.

## 2026-08-27 — Uniform payload fingerprint runtime

Branch:

`exp/x1-uniform-payload-fingerprint`

Authorized build:

- workflow `Build dc95 X1 Uniform Payload Fingerprint`
- run `33040377420`
- job `98412364840`
- attempt 1
- build HEAD `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- result success
- artifact `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id `9634160587`
- size 31,299,993 bytes
- SHA-256 `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

Matched runtime:

- log `eden_log(20260827-052251).txt`
- TOTK 1.4.2
- exact Eden identification `HEAD-dc95cd09ee-HEAD`
- Adreno X1-85, driver 512.863.0, Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- test reached >3000 frames and user intentionally stopped the emulator; end `ForceStop` is not treated as a crash

Instrumentation:

- deterministic 1/16 key sampling
- fingerprint computed from the already-copied mapped staging span; no additional guest-memory read
- fixed bounded sample table
- observation only; no Uniform skip/reuse/batching or dirty-state change

Gameplay aggregate used for conclusion: report frames 1320–3000 inclusive (15 x 120-frame reports = 1800 frames).

Uniform path aggregate:

- visits: **41,733,585**
- fast: **41,188,346** = **98.69%**
- fastAlignment: **0**
- fastSkip: **41,188,346**
- cached: **545,239**
- cachedClean: **513,129** = **94.11% of cached**
- cachedUpload: **32,110**
- average fast payload: **410.46 bytes**
- fast streams/frame: **22,882.4** in this route
- tracked fast-key repeats dominate: 40,257,355 repeat vs 236,970 unique; table overflow exists and therefore the repeat ratio is a lower-bound style observation, not a perfect census

Payload-sample aggregate:

- samples: **1,890,393**
- uniqueSamples: **14,526**
- repeatSamples: **1,835,334**
- sameFingerprint: **1,792,196**
- changedFingerprint: **43,138**
- sampleOverflow: **40,533**
- among tracked repeat samples, **97.65% had the same payload fingerprint** and **2.35% changed**
- same-frame repeat classification: 1,445,069 same vs 12,119 changed; **99.17% of classified same-frame repeats had the same fingerprint**

Representative report blocks:

- frame 1440: 69,863 repeat samples; 67,489 same fingerprint vs 2,374 changed = 96.60% same
- frame 1560: 49,705 repeat; 47,453 same vs 2,252 changed = 95.47% same
- frame 2400: 148,365 repeat; 144,858 same vs 3,507 changed = 97.64% same
- frame 2880: 159,729 repeat; 156,906 same vs 2,823 changed = 98.23% same

Conclusion — STRONG RUNTIME EVIDENCE:

The dominant fast Uniform path repeatedly streams not only the same `(stage,index,address,size)` identity but, for sampled repeated keys, overwhelmingly the same payload fingerprint. The effect is especially strong within the same frame.

This does **not** yet justify blindly reusing the previous staging allocation: staging lifetime, descriptor identity and in-flight GPU use must remain correct. A 64-bit fingerprint is also evidence of payload equality, not mathematical byte-for-byte proof.

The safest next A/B is therefore **not** a custom skip/dedupe. It is to expose a Qualcomm/X1 diagnostic control that disables the adaptive small-Uniform skip-cache policy and routes those Uniforms through Eden's existing classic cached path, while leaving alignment-required streaming untouched. This reuses existing dirty tracking and lifetime semantics and directly tests whether the fast-stream policy is causing the ~20 FPS ceiling or whether the cached path simply moves the cost into stalls/freezes.

No such A/B build has been started yet. Fresh explicit authorization remains required for each ARM64 attempt.
