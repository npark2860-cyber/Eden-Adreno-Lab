# CURRENT HANDOFF — Eden Adreno X1 frame-cadence attribution

Updated: 2026-08-27 KST

## Fixed baseline

- Lab repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Current experiment branch: `exp/x1-frame-cadence-attribution`

**Never change the Eden source baseline without the explicit baseline-change procedure.**

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Immediate predecessor — Uniform cache A/B

Branch: `exp/x1-uniform-cache-ab`

Authorized build:

- workflow: `Build dc95 X1 Uniform Cache AB`
- run: `33045572814`
- job: `98428654028`
- attempt: 1
- build HEAD: `8e8351953d966a1c7677940b7a926aae902969d1`
- result: **success**
- artifact: `Eden-dc95-X1-uniform-cache-ab`
- artifact id: `9636118096`
- size: 31,302,610 bytes
- SHA-256: `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`
- expires: 2026-09-10
- build attempts: exactly 1
- reruns: 0

That build authorization is consumed.

### A/B semantics

Checkbox:

`X1 A/B: Disable Adaptive Uniform Fast Stream`

- OFF: existing payload-fingerprint/adaptive fast-stream behavior
- ON on Qualcomm proprietary Vulkan only: alignment-required streaming remains, adaptive `fastSkip` falls through to existing classic cached `SynchronizeBuffer()` path
- no custom payload cache/dedupe
- no previous staging reuse
- no scheduler/barrier/render-pass/alias/dirty-state/lifetime/persistent-binding change

## Paired A/B runtime result

Matched environment:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- exact Eden identification `HEAD-dc95cd09ee-HEAD`

### ON log

`eden_log(20260827-083649).txt`

- setting true
- fast = 0
- fastSkip = 0
- cached = visits
- report windows 960–1440, 600 frames:
  - visits 9,449,653
  - cachedClean 8,913,714 = 94.33%
  - cachedUpload 535,939 = 5.67%
- coarse rate over frame 960→1440: ~18.1 FPS
- no ceiling break
- frame-1440 classic-path cost included ~122.8k Uniform copies, ~484.7 MiB Uniform copied data, ~87.9k Uniform outside-RP operations and scheduler wait ~6504 ms / 120 frames
- end ForceStop intentional, not crash

Conclusion: the switch works, and most redirected Uniforms are clean, but forcing adaptive Uniforms into classic cache is not an optimization. Cost migrates into explicit copy/outside-RP/synchronization pressure.

### OFF paired log

`eden_log(20260827-085340).txt`

- setting false
- same built artifact / same runtime environment
- user observation: title/light screen reaches ~30 FPS, gameplay feels pinned at or below 20 FPS; 22–23 FPS is unusually rare
- log wall-time supports two distinct stable regimes:
  - light/title-like segment around frame 1453–1557: ~29.7 FPS
  - gameplay frame 2640→2880: ~19.48 FPS
  - gameplay frame 2880→3120: ~19.59 FPS
- in-game scheduler wait is large, e.g.:
  - frame 2640 report: ~2693 ms / 120 frames
  - frame 2880 report: ~3353 ms / 120 frames
  - frame 3120 report: ~2586 ms / 120 frames
- existing Vulkan swapchain profiler `pacing` totals remain tiny (fractions of a millisecond per 120 frames), so explicit `Target_60` swapchain resource pacing is not consuming an extra ~16.7 ms each frame

Do **not** call this a proven hardcoded 20-FPS cap. The measured shape is consistent with cadence quantization and needs attribution.

## New source-level cadence facts — exact dc95

### VI conductor

`src/core/hle/service/vi/conductor.cpp`

- base `FrameNs = 1e9 / 60`
- `ScreenComposition` is scheduled from that 60-Hz base
- `ProcessVsync()` calls `ComposeOnDisplay()` then signals VSync
- period is derived from `m_swap_interval`, speed scale and speed limit

### Nvnflinger HardwareComposer

`src/core/hle/service/nvnflinger/hardware_composer.cpp`

- reads each layer `item.swap_interval`
- uses normalized interval for framebuffer acquire/release bookkeeping
- nevertheless `ComposeLocked()` ends with `m_frame_number += 1; return 1;`
- therefore dc95 does not directly return 2 or 3 from this compositor to select 30 or 20 Hz
- `nvdisp.WaitForComposite()` occurs at the start of each active compose
- a host composite is requested only when a **new buffer was acquired**

### nvdisp / GPU composite hand-off

`src/core/hle/service/nvdrv/devices/nvdisp_disp0.cpp`

- `WaitForComposite()` delegates to `system.GPU().WaitForComposite()`
- `Composite()` delegates to `system.GPU().RequestComposite(...)`, then reports frame interval / speed limiting / perf frame boundary

`src/video_core/gpu.cpp`

- `RequestComposite()` queues a GPU sync operation and handles guest acquire fences
- `WaitForComposite()` waits for the prior pending sync-operation fence when present

Current interpretation:

> VI itself continues to operate from a 60-Hz base. The visible 30→~20 step is more plausibly created by when new game framebuffers become available/completed relative to those 60-Hz composition opportunities, or by a composite hand-off stall, rather than by a literal `swap_interval=3` or explicit host swapchain pacing sleep.

This is a hypothesis to test, not yet a final cause.

## Current experiment — frame cadence attribution

Branch:

`exp/x1-frame-cadence-attribution`

Created from predecessor HEAD:

`2e8f339a2338c5538f2c4af5cb8b1b135498a148`

Prepared files:

- `tools/adreno_lab/transplant_dc95_frame_cadence_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-frame-cadence-attribution.yml`
- `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 Frame Cadence Attribution`

Trigger: `workflow_dispatch` only.

Actions runs on this branch at preparation check: **0**.

### Observation points

`[X1-CADENCE][QUEUE]`

- successful guest `BufferQueueProducer::QueueBuffer`
- host steady-clock timestamp
- queue-core identity
- guest frame number
- swap interval
- queue size

`[X1-CADENCE][ACQUIRE]`

- new Nvnflinger framebuffer acquisition
- same host clock
- compositor tick
- consumer identity
- main/overlay
- guest frame number / swap interval

`[X1-CADENCE][VI]`

- every active compositor tick
- whether a new main buffer was acquired
- `WaitForComposite()` host duration
- total `ComposeLocked()` host duration

Existing `x1_present_frame_log` gates the new records.

### Safety boundary

The cadence transplant is restricted to observation additions in:

- `src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

The workflow snapshots these files and hashes the following as no-change critical files:

- `src/core/hle/service/vi/conductor.cpp`
- `src/video_core/gpu.cpp`
- `src/video_core/renderer_vulkan/vk_swapchain.cpp`
- `src/video_core/renderer_vulkan/vk_scheduler.cpp`
- `src/core/hle/service/nvdrv/devices/nvhost_ctrl.cpp`

Static checks reject newly-added sleeps, waits, scheduling changes, swap-interval assignments, speed-limit changes, new composite requests, or alternate numeric cadence returns.

## Interpretation matrix for the future cadence runtime

- QueueBuffer ~50 ms + main acquire every 3 compositor ticks:
  - cadence already exists upstream / game-frame production side

- QueueBuffer ~33 ms + main acquire every 3 ticks:
  - consumer/compositor acquisition/release side delays ready frames

- VI tick itself stretches toward ~50 ms or `WaitForComposite()` repeatedly costs ~16/33 ms:
  - compositor/GPU hand-off stalls VI

- QueueBuffer and acquire both ~33 ms while displayed/runtime FPS remains ~20:
  - loss is after acquisition; next target becomes renderer composite/present completion

## Retained closed facts

### Alias

Repeated alias copy pair/region traffic is not trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not pursue simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- adaptive small-Uniform fast path is mapped re-stream, not payload reuse
- gameplay fast path was almost entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached path is mostly clean
- payload-fingerprint run showed 97.65% of tracked repeated samples same fingerprint and 99.17% of classified same-frame repeats same fingerprint
- this still does not justify blind previous-staging reuse because descriptor/staging lifetime and in-flight GPU safety remain unresolved

## What NOT to do next

- no ARM64 Actions without fresh explicit permission
- no reuse of the consumed Uniform A/B build authorization
- do not claim a proven literal 20-FPS cap yet
- do not blame Mailbox/Target_60 without new evidence
- do not change VSync, speed limiter, swap interval, scheduling, fences or waits as part of attribution
- no scheduler/barrier/render-pass suppression
- no alias trivial dedupe
- no blind persistent Uniform binding
- no blind previous staging allocation reuse
- do not treat ForceStop as a crash

## NEXT ACTION

**Stop before Actions.**

Read `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`.

A fresh explicit user authorization is required for exactly one build attempt of:

`Build dc95 X1 Frame Cadence Attribution`

If authorized and successful, run TOTK 1.4.2 through both the ~30-FPS title/light regime and the steady ~20-FPS gameplay regime with existing X1 present logging enabled. Then run `analyze_x1_frame_cadence.py` on the produced log.

## Build authorization state

- current branch: `exp/x1-frame-cadence-attribution`
- current branch Actions runs: 0
- frame-cadence build attempts: 0
- frame-cadence build authorization: **not granted**
- previous Uniform cache A/B authorization: consumed
- gameplay optimization promoted: none
