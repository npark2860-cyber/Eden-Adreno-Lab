# DEBUG HISTORY — Eden Adreno X1-85

Updated: 2026-08-27 KST

This file records confirmed experiment outcomes. Exact Eden baseline remains:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Do not reconstruct missing facts from chat when the GitHub documents are available.

## 2026-08-27 — alias synchronization redundancy runtime

Branch: `exp/x1-alias-sync-redundancy`

Authorized build:

- run `33024690895`
- job `98363162523`
- attempt 1
- build HEAD `804f394c5db280f842a01113e6ca92f7ad57d219`
- artifact `Eden-dc95-X1-alias-sync-redundancy`
- artifact id `9628554127`
- SHA-256 `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

Matched TOTK 1.4.2 runtime aggregate:

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

Repeated alias pair/region traffic is not trivial unchanged-state duplication. Every tracked recurrence advances source `modification_tick`; same-source-tick + same-region candidates are zero. Do not implement simple alias-copy dedupe.

Established route remains:

`Draw Configure -> FillImageViews -> PrepareImage -> SynchronizeAliases -> CopyImage -> direct Vulkan copy -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

## 2026-08-27 — exact dc95 graphics Uniform source analysis

Confirmed source facts:

1. Vulkan `BufferCacheParams::HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
2. Vulkan revisits enabled graphics Uniform bindings rather than preserving an OpenGL-style persistent dirty binding mask.
3. Classic cached Uniform path calls `SynchronizeBuffer()`.
4. `SynchronizeBuffer()` can return clean with no physical upload when no upload range exists.
5. `uniform_cache_hits` therefore counts classic-cache clean/no-upload outcomes.
6. Adaptive small-Uniform path uses `BindMappedUniformBuffer()` and requests upload staging / descriptor insertion, then copies guest bytes again.
7. The fast path is a stall-avoidance re-stream path, not persistent payload reuse.

## 2026-08-27 — Uniform stream/reuse runtime

Branch: `exp/x1-uniform-stream-reuse`

Authorized build:

- workflow `Build dc95 X1 Uniform Stream Reuse`
- run `33037180003`
- job `98402328028`
- attempt 1
- build HEAD `8f33dc37c98afa134ad5efbbf14ab85df388ee42`
- artifact `Eden-dc95-X1-uniform-stream-reuse`
- artifact id `9633005533`
- SHA-256 `03491e648026bf0226f2bbd3817d4a979040cc027991af45f9117c2a68564860`

Runtime result — CONFIRMED:

- representative frame 1200–1680 aggregate: 9,762,092 fast streams / 9,927,196 visits = 98.34%
- gameplay `fastAlignment = 0`
- gameplay fast selection was adaptive `fastSkip`
- classic cached path: 154,847 clean / 165,104 cached = 93.79%
- exact `(stage,index,device_addr,size)` fast keys repeat heavily across Draws
- `sameDraw = 0`

Conclusion:

The prior tiny Uniform upload-request explosion is overwhelmingly produced by adaptive mapped re-stream policy, not classic-cache dirty uploads.

## 2026-08-27 — Uniform payload fingerprint runtime

Branch: `exp/x1-uniform-payload-fingerprint`

Authorized build:

- workflow `Build dc95 X1 Uniform Payload Fingerprint`
- run `33040377420`
- job `98412364840`
- attempt 1
- build HEAD `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- artifact `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id `9634160587`
- size 31,299,993 bytes
- SHA-256 `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

Matched runtime:

- log `eden_log(20260827-052251).txt`
- TOTK 1.4.2
- Adreno X1-85 / Qualcomm 512.863.0 / Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- end ForceStop intentional, not crash

Gameplay aggregate frame 1320–3000 = 1800 frames:

- visits 41,733,585
- fast 41,188,346 = 98.69%
- fastAlignment 0
- fastSkip 41,188,346
- cached 545,239
- cachedClean 513,129 = 94.11%
- cachedUpload 32,110
- average fast payload 410.46 bytes
- fast streams/frame 22,882.4

Payload samples:

- samples 1,890,393
- uniqueSamples 14,526
- repeatSamples 1,835,334
- sameFingerprint 1,792,196
- changedFingerprint 43,138
- sampleOverflow 40,533
- tracked repeated samples: 97.65% same fingerprint
- classified same-frame repeats: 99.17% same fingerprint

Conclusion — STRONG RUNTIME EVIDENCE:

Dominant adaptive fast Uniform traffic repeatedly streams not only the same key identity but overwhelmingly the same sampled payload fingerprint. This does not prove that a previous staging allocation is safe to reuse; descriptor identity, staging lifetime and in-flight GPU use remain correctness boundaries.

## 2026-08-27 — Uniform cache A/B build and runtime

Branch: `exp/x1-uniform-cache-ab`

A/B control:

`X1 A/B: Disable Adaptive Uniform Fast Stream`

Semantics:

- OFF = established adaptive fast-stream behavior
- ON on Qualcomm proprietary Vulkan only = alignment-required streaming unchanged; adaptive fastSkip eligibility falls through to existing classic cached `SynchronizeBuffer()` path
- no custom dedupe/cache
- no prior staging reuse
- no scheduler/barrier/render-pass/alias/dirty-state/lifetime/persistent-binding change

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Uniform Cache AB`
- run `33045572814`
- job `98428654028`
- attempt 1
- build HEAD `8e8351953d966a1c7677940b7a926aae902969d1`
- artifact `Eden-dc95-X1-uniform-cache-ab`
- artifact id `9636118096`
- size 31,302,610 bytes
- SHA-256 `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`
- exactly one build attempt; no rerun

### ON runtime

Log: `eden_log(20260827-083649).txt`

- `x1_ab_disable_adaptive_uniform_fast_stream = true`
- fast = 0
- fastSkip = 0
- cached = visits
- report windows ending 960–1440, 600 frames total:
  - visits 9,449,653
  - cachedClean 8,913,714 = 94.33%
  - cachedUpload 535,939 = 5.67%
- coarse frame 960→1440 wall rate ~18.1 FPS
- no gameplay ceiling break
- representative frame-1440 Uniform cost:
  - ~122,803 copies
  - ~484.7 MiB copied data
  - ~87,863 outside-RP operations
- frame-1440 scheduler wait ~6504 ms / 120 frames

Conclusion — CONFIRMED:

The A/B switch worked exactly as designed, and most redirected visits are clean, but wholesale fallback to classic cache is not an optimization. The adaptive staging-request storm is exchanged for explicit buffer-copy/outside-RP/synchronization pressure.

### Paired OFF runtime

Log: `eden_log(20260827-085340).txt`

- same built artifact
- `x1_ab_disable_adaptive_uniform_fast_stream = false`
- same TOTK 1.4.2 / Adreno X1-85 / driver 512.863.0 / Vulkan 1.3.295 / Win11 25H2 environment

Important user observation:

- title/light screen reaches ~30 FPS
- gameplay is nearly always at or below 20 FPS
- intermediate 22–23 FPS is unusually rare; it feels pinned

Log wall-time supports distinct regimes:

- frame 1453→1557: ~29.7 FPS
- frame 2640→2880: ~19.48 FPS
- frame 2880→3120: ~19.59 FPS

Gameplay scheduler wait examples:

- frame 2640 report: ~2693 ms / 120 frames
- frame 2880 report: ~3353 ms / 120 frames
- frame 3120 report: ~2586 ms / 120 frames

Existing Vulkan swapchain `pacing` totals in these reports are only fractions of a millisecond per 120 frames. Therefore the explicit `Target_60` swapchain resource-pacing wait is not the missing ~16.7 ms/frame.

Conclusion at that time:

Do not describe this as a proven hardcoded 20-FPS cap. The 30→~20 step was consistent with a 60-Hz cadence transition (new game frame every second vs every third composition opportunity), but the layer where that cadence first appeared still needed attribution.

## 2026-08-27 — exact dc95 cadence source analysis

Source facts — CONFIRMED:

### VI conductor

`src/core/hle/service/vi/conductor.cpp`

- `FrameNs = 1e9 / 60`
- `ScreenComposition` is scheduled from this 60-Hz base
- `ProcessVsync()` composes displays and signals VSync
- timing period uses `m_swap_interval` / speed scale

### HardwareComposer

`src/core/hle/service/nvnflinger/hardware_composer.cpp`

- layer `item.swap_interval` is read and used for acquire/release bookkeeping
- `ComposeLocked()` still ends with `m_frame_number += 1; return 1;`
- it does not directly return 2 or 3 to select 30/20 Hz
- `nvdisp.WaitForComposite()` is called before acquire/release processing
- `nvdisp.Composite(...)` is called only when a new buffer was acquired

### nvdisp / GPU

`src/core/hle/service/nvdrv/devices/nvdisp_disp0.cpp`

- `WaitForComposite()` -> `system.GPU().WaitForComposite()`
- `Composite()` -> `system.GPU().RequestComposite(...)`

`src/video_core/gpu.cpp`

- composite request is queued as a GPU sync operation
- guest acquire fences may defer renderer composite
- the next `WaitForComposite()` waits on the prior pending sync-operation fence when present

## 2026-08-27 — frame cadence attribution static preparation

Branch: `exp/x1-frame-cadence-attribution`

Created from predecessor HEAD:

`2e8f339a2338c5538f2c4af5cb8b1b135498a148`

Prepared:

- `tools/adreno_lab/transplant_dc95_frame_cadence_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-frame-cadence-attribution.yml`
- `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`

Observation records:

- `[X1-CADENCE][QUEUE]`: successful guest QueueBuffer timestamp / queue core / guest frame / slot / swap interval
- `[X1-CADENCE][ACQUIRE]`: compositor new-buffer acquire timestamp / compositor tick / consumer / main-overlay / frame / swap interval
- `[X1-CADENCE][VI]`: active compositor tick timestamp / new-main count / `WaitForComposite` duration / total compose duration

All timestamps use host `steady_clock`.

Safety:

- cadence transplant edits only `buffer_queue_producer.cpp` and `hardware_composer.cpp` in the temporary Eden checkout
- workflow hashes and requires no cadence change to VI conductor, GPU core, Vulkan swapchain, Vulkan scheduler or nvhost_ctrl
- workflow rejects newly-added sleeps, new wait calls, schedule changes, swap-interval assignments, speed-limit changes, new composite requests and alternate numeric cadence returns

## 2026-08-27 — frame cadence attribution build and runtime

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- size 31,305,699 bytes
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`
- exactly one build attempt; no rerun

Runtime log:

`eden_log(20260827-104943).txt`

Matched runtime:

- TOTK 1.4.2
- Adreno X1-85 / Qualcomm 512.863.0 / Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- exact Eden identification `HEAD-dc95cd09ee-HEAD`
- `x1_present_frame_log = true`
- Uniform cache A/B OFF

### Stable swap=2 regime — CONFIRMED

Guest QueueBuffer frames 562-910:

- 349 queue records
- 11.830372 s
- effective 29.416 FPS
- median QueueBuffer interval 33.352 ms
- main-buffer acquire median 33.506 ms
- acquire tick delta 2 for 344 / 348 adjacent acquires
- VI tick median ~16.609 ms
- zero `WaitForComposite > 1 ms` events in the segment

### Stable swap=3 gameplay regime — CONFIRMED

Guest QueueBuffer frames 911-1758:

- 848 queue records
- 48.44955 s
- effective 17.482 FPS because 3-tick opportunities are sometimes additionally missed
- median QueueBuffer interval 49.985 ms
- main-buffer acquire median 50.044 ms
- acquire tick delta 3 for 726 adjacent acquires; remaining misses are mostly 4+ ticks
- VI tick median ~16.586 ms / mean ~16.667 ms
- `WaitForComposite` median 0 ms; only 4 VI ticks exceeded 1 ms

Critical transition:

- frame 910 QueueBuffer: `swap=2`
- frame 911 QueueBuffer: `swap=3`
- final gameplay remains `swap=3` through frame 1758

Conclusion — CONFIRMED:

The discrete 30 -> <=20 behavior is explained by the main guest BufferQueue interval changing from 2 to 3:

- swap 2 -> nominal 60 / 2 = 30 FPS opportunity
- swap 3 -> nominal 60 / 3 = 20 FPS opportunity

With swap 3 active, missing a presentation opportunity only lowers FPS further. This is why 22-23 FPS is normally absent and gameplay feels pinned at 20 or below.

This cadence is already visible at guest `QueueBuffer`; it is not created later by Vulkan Present, Mailbox or `Target_60` pacing.

### Raw interval ownership — CONFIRMED SOURCE FACT

Exact dc95:

- `QueueBufferInput` contains `s32 swap_interval`
- its constructor directly `parcel.ReadFlattened(*this)` from the guest input parcel
- `BufferQueueProducer::QueueBuffer()` deflates that value and writes `item.swap_interval = swap_interval`
- HardwareComposer honors it for main-layer acquire spacing and release-frame bookkeeping
- compositor/VI itself continues on the 60-Hz base

Therefore raw `swap=3` originates before host Vulkan presentation, in the guest QueueBuffer request path.

Still unknown:

- why TOTK selects/sends interval 3 in this runtime
- whether interval 3 is purely a symptom of already missing the 30-FPS budget
- whether Eden main-layer acquire/release timing participates in a feedback ceiling once interval 3 is active

Next proposal is documented in `NEXT_ACTION_SWAP_INTERVAL_3_AB.md`.

No new ARM64 build is authorized. The proposed main-layer raw-3/effective-2 clamp is an attribution A/B only and must not be implemented or built without fresh explicit user approval.
