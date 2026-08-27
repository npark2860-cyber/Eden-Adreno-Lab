# CURRENT HANDOFF — Eden Adreno X1 frame-cadence attribution

Updated: 2026-08-27 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment: `exp/x1-frame-cadence-attribution`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Closed / retained facts

### Alias

Repeated alias copy pair/region traffic is not trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse
- gameplay fast selection was almost entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached Uniform path is mostly clean
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint; 99.17% of classified same-frame repeats same fingerprint
- same key/fingerprint does not by itself make an old staging allocation safe to reuse; descriptor/staging lifetime and in-flight GPU use remain correctness boundaries

## Uniform cache A/B — completed runtime result

Branch: `exp/x1-uniform-cache-ab`

Checkbox: `X1 A/B: Disable Adaptive Uniform Fast Stream`

- OFF: established adaptive fast-stream behavior
- ON on Qualcomm proprietary Vulkan: alignment-required stream preserved; adaptive fastSkip falls through to existing classic cached `SynchronizeBuffer()` path
- no custom cache/dedupe, previous staging reuse, scheduler/barrier/render-pass/alias/dirty-state/lifetime/persistent-binding change

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
- expires 2026-09-10
- attempts 1, reruns 0

That authorization is consumed.

### ON runtime

Log: `eden_log(20260827-083649).txt`

- setting true
- fast = 0 / fastSkip = 0 / cached = visits
- report windows ending 960–1440, 600 frames:
  - visits 9,449,653
  - cachedClean 8,913,714 = 94.33%
  - cachedUpload 535,939 = 5.67%
- coarse frame 960→1440 rate ~18.1 FPS
- no gameplay ceiling break
- frame-1440 representative cost: ~122.8k Uniform copies, ~484.7 MiB copied data, ~87.9k Uniform outside-RP operations, scheduler wait ~6504 ms / 120 frames
- ForceStop was intentional, not a crash

Conclusion: wholesale classic-cache fallback is not an optimization. It replaces adaptive staging-request pressure with explicit copy/outside-RP/synchronization pressure.

### Paired OFF runtime

Log: `eden_log(20260827-085340).txt`

Matched environment:

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- exact Eden identification `HEAD-dc95cd09ee-HEAD`
- setting false

User observation and log wall-time agree on two regimes:

- title/light: ~30 FPS; frame 1453→1557 ~29.7 FPS
- gameplay: almost always <=20 FPS; frame 2640→2880 ~19.48 FPS and 2880→3120 ~19.59 FPS
- 22–23 FPS is unusually rare subjectively

Gameplay scheduler wait examples:

- frame 2640: ~2693 ms / 120 frames
- frame 2880: ~3353 ms / 120 frames
- frame 3120: ~2586 ms / 120 frames

Existing Vulkan swapchain `pacing` totals in the same kind of reports are only fractions of a millisecond per 120 frames. Explicit `Target_60` resource pacing is therefore not consuming the missing ~16.7 ms/frame.

Do **not** call this a proven hardcoded 20-FPS cap yet.

## Exact dc95 cadence source facts — confirmed

### `src/core/hle/service/vi/conductor.cpp`

- `FrameNs = 1e9 / 60`
- `ScreenComposition` starts from this 60-Hz base
- `ProcessVsync()` calls composition then signals VSync
- period calculation uses `m_swap_interval` and speed scale

### `src/core/hle/service/nvnflinger/hardware_composer.cpp`

- reads layer `item.swap_interval`
- uses it for acquire/release bookkeeping
- nevertheless ends `ComposeLocked()` with `m_frame_number += 1; return 1;`
- it does not directly return 2 or 3 to select 30/20 Hz
- calls `nvdisp.WaitForComposite()` before framebuffer processing
- calls `nvdisp.Composite(...)` only when a new buffer was acquired

### `src/core/hle/service/nvdrv/devices/nvdisp_disp0.cpp`

- `WaitForComposite()` -> `system.GPU().WaitForComposite()`
- `Composite()` -> `system.GPU().RequestComposite(...)`

### `src/video_core/gpu.cpp`

- `RequestComposite()` queues a GPU sync operation and tracks guest acquire fences
- `WaitForComposite()` waits on the previous pending sync-operation fence when present

Current source-backed hypothesis:

> VI still provides 60-Hz composition opportunities. The visible 30→~20 step is more plausibly created by when new game framebuffers become available/completed relative to those opportunities, or by a composite hand-off stall, than by a direct `swap_interval=3` or host swapchain pacing sleep.

This remains a hypothesis to test.

## Current experiment — static preparation complete

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

Branch Actions runs at the latest preparation check: **0**.

### New observation records

`[X1-CADENCE][QUEUE]`

- successful guest `BufferQueueProducer::QueueBuffer`
- host `steady_clock` timestamp
- queue-core identity
- guest frame number / slot / swap interval

`[X1-CADENCE][ACQUIRE]`

- new Nvnflinger framebuffer acquisition
- same host clock
- compositor tick / consumer identity / main-overlay flag / guest frame / swap interval

`[X1-CADENCE][VI]`

- each active compositor tick
- same host clock
- new-main/new-overlay counts
- `WaitForComposite()` duration
- total `ComposeLocked()` duration

All new logging is gated by the already-existing `x1_present_frame_log` setting.

### Safety boundary

The cadence transplant may edit only temporary Eden checkout files:

- `src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

The workflow hashes and requires no cadence-transplant change to:

- `src/core/hle/service/vi/conductor.cpp`
- `src/video_core/gpu.cpp`
- `src/video_core/renderer_vulkan/vk_swapchain.cpp`
- `src/video_core/renderer_vulkan/vk_scheduler.cpp`
- `src/core/hle/service/nvdrv/devices/nvhost_ctrl.cpp`

It rejects newly-added sleeps, wait calls, schedule changes, swap-interval assignments, speed-limit changes, new composite requests and alternate numeric cadence returns.

The branch itself adds/changes only lab workflow/tool/doc files; it does not directly edit the retained Eden source hooks.

## Future runtime interpretation

- QueueBuffer ~50 ms + acquire every 3 compositor ticks -> cadence already upstream/game-produced
- QueueBuffer ~33 ms + acquire every 3 ticks -> consumer/compositor delays ready buffers
- VI tick wall cadence ~50 ms or WaitForComposite repeatedly ~16/33 ms -> composite/GPU hand-off stalls VI
- QueueBuffer + acquire ~33 ms while visible/runtime remains ~20 -> loss occurs after acquisition; investigate renderer composite/present completion

## What NOT to do next

- no ARM64 Actions without fresh explicit permission
- previous Uniform A/B authorization cannot be reused
- no claim of a proven literal 20-FPS cap yet
- do not blame Mailbox/Target_60 without new evidence
- no VSync/speed-limiter/swap-interval/scheduler/fence/wait behavior changes in this attribution experiment
- no scheduler/barrier/render-pass suppression
- no alias trivial dedupe
- no blind persistent Uniform binding
- no blind previous staging allocation reuse
- do not treat ForceStop as a crash

## NEXT ACTION

Read `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`.

**Stop before Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Frame Cadence Attribution`

If a future authorized build succeeds, run one TOTK 1.4.2 session containing both the ~30-FPS title/light regime and the steady ~20-FPS gameplay regime with X1 present logging enabled, then analyze with `tools/adreno_lab/analyze_x1_frame_cadence.py`.

## Build authorization state

- current branch: `exp/x1-frame-cadence-attribution`
- frame-cadence Actions runs: 0
- frame-cadence build attempts: 0
- frame-cadence build authorization: **not granted**
- previous Uniform cache A/B authorization: consumed
- gameplay optimization promoted: none
