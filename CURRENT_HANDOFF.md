# CURRENT HANDOFF — Eden Adreno X1 Diagnostic Harness

Updated: 2026-08-27 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-diagnostic-harness`
- predecessor branch: `exp/x1-swap-interval-3-to-2-ab`
- predecessor cleanup HEAD: `9822e0017ca07da8c8aa0545339230efab6d4967`

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/re-run without fresh explicit user authorization. One authorization = exactly one attempt.**

## Retained closed facts

### Alias

Repeated alias pair/region traffic is not trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not implement simple alias-copy dedupe or suppress required outside-RP `vkCmdCopyImage` work.

### Uniform

- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse
- gameplay fast selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached Uniform path is mostly clean
- payload-fingerprint runtime: 97.65% of tracked repeated samples same fingerprint
- classified same-frame repeats: 99.17% same fingerprint
- wholesale classic-cache fallback A/B did not break the gameplay ceiling and moved cost into explicit copy/outside-RP/synchronization work

Do not blindly reuse old staging allocations or enable persistent Uniform bindings.

## Uniform cache A/B — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Uniform Cache AB`
- run `33045572814`
- job `98428654028`
- attempt 1
- build HEAD `8e8351953d966a1c7677940b7a926aae902969d1`
- artifact `Eden-dc95-X1-uniform-cache-ab`
- artifact id `9636118096`
- SHA-256 `b3ec51f770f5ea664a0d277bbc2ede3952f6e6cfea9fef0f14f52f98be84dd6e`

ON result:

- adaptive fast / fastSkip = 0
- redirected classic-cache visits ~94.33% clean
- gameplay still ~18 FPS
- cost migrated into explicit copy / outside-RP / synchronization

Conclusion: wholesale classic-cache fallback is not an optimization.

## Frame cadence attribution — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`

Matched TOTK 1.4.2 runtime confirmed:

- stable raw `swap=2`: QueueBuffer median ~33.352 ms, nominal 30-FPS cadence
- stable raw `swap=3`: QueueBuffer median ~49.985 ms, nominal 20-FPS cadence
- main acquire follows ~33.5 ms vs ~50.0 ms
- VI remains ~60 Hz
- `WaitForComposite` is normally near 0 ms
- transition observed directly at QueueBuffer raw `swap=2 -> 3`

Confirmed meaning:

> The discrete 30 -> <=20 shape is encoded in the guest/main BufferQueue cadence: raw 2 gives nominal 60/2=30 opportunities and raw 3 gives nominal 60/3=20 opportunities.

Raw `swap_interval` originates in guest `QueueBufferInput`, is stored unchanged by `BufferQueueProducer`, and is not created by Qualcomm Vulkan, Mailbox, or Target_60.

## Swap interval 3 -> effective 2 A/B — completed

Authorized build — SUCCESS:

- workflow `Build dc95 X1 Swap Interval 3 To 2 AB`
- run `33066726140`
- job `98498505964`
- attempt 1
- build HEAD `c196cd1c61e6385009c136b3fb810d5ed9807615`
- artifact `Eden-dc95-X1-swap-interval-3-to-2-ab`
- artifact id `9644858627`
- size 31,305,925 bytes
- SHA-256 `e3b4b71b59812f9c39a9bb8f637cf2b227aa1b9eef623615497f62a65241a7cb`
- exactly one attempt, no rerun

Runtime log:

`eden_log.txt` uploaded 2026-08-27 12:06 KST.

ON was confirmed:

- `x1_ab_clamp_main_swap_interval_3_to_2 = true`
- raw main `swap=3` records were acquired as `effective=2`
- the A/B therefore executed correctly

Result:

- raw QueueBuffer production in the long gameplay `swap=3` regime remained around the ~50-ms / ~19-FPS class
- main acquire rate remained around the same class
- effective interval 2 created some 2-tick acquire opportunities, but the producer did not supply enough new buffers to break the gameplay ceiling

Conclusion — CLOSED:

> HardwareComposer interval-3 acquire/release gating is not the primary cause of the <=20-FPS gameplay ceiling. `swap=3` is a cadence signal/symptom; forcing effective 2 cannot create upstream frames that are not being queued.

Do not repeat a simple producer/composer `3 -> 2` number clamp as the next optimization.

## Exact dc95 BufferQueue backpressure path — source analysis

`BufferQueueCore` on HOS has:

- `use_async_buffer = false`
- `max_acquired_buffer_count = 0`
- `default_max_buffer_count = 2`

`BufferQueueProducer::DequeueBuffer()` calls `WaitForFreeSlotThenRelock()`.

If no free slot exists, or too many buffers are outstanding, that helper can block in `WaitForDequeueCondition()` until the consumer acquires/releases and calls `SignalDequeueCondition()`.

Therefore the unresolved ~50-ms producer interval should be split into:

1. previous QueueBuffer -> next DequeueBuffer entry
2. DequeueBuffer entry -> free-slot selection / return
3. DequeueBuffer return -> next QueueBuffer

Interpretation:

- long #1 => guest/game pacing before requesting the next buffer
- long #2 => BufferQueue free-slot/backpressure
- long #3 => guest rendering/GPU production after dequeue

## Current experiment — runtime-selectable X1 Diagnostic Harness

Branch:

`exp/x1-diagnostic-harness`

Purpose:

Stop paying one ARM64 build per attribution question. Recreate the complete proven diagnostic chain in one binary and select logging/A-B behavior at runtime.

Existing controls remain available, including:

- X1 upload/barrier/full-flow logs
- X1 pipeline/shader logs
- X1 present/frame logs
- X1 scheduler/sync logs
- X1 descriptor-ring log
- Draw/Dispatch exact-signature A/B controls
- `X1 A/B: Disable Adaptive Uniform Fast Stream`
- `X1 A/B: Clamp Main Swap Interval 3 To 2`

New independent controls:

- `X1 Log: Frame Cadence`
- `X1 Log: Dequeue Attribution`

Both new controls default OFF.

### Frame Cadence

Controls:

- `[X1-CADENCE][QUEUE]`
- `[X1-CADENCE][ACQUIRE]`
- `[X1-CADENCE][VI]`

This is now separate from the older `x1_present_frame_log`.

### Dequeue Attribution

Observation-only.

Records:

- `[X1-DEQUEUE][BEGIN]`
- `[X1-DEQUEUE][SLOT]`
- `[X1-DEQUEUE][END]`

`SLOT` reports:

- time before the free-slot helper
- time spent inside `WaitForFreeSlotThenRelock()`

`END` reports total DequeueBuffer service time.

When Dequeue Attribution is ON, QueueBuffer records are also retained automatically even if Frame Cadence is OFF, because the analyzer needs Queue/Dequeue pairing.

No new wait, sleep, fence, buffer-count, swap-interval, scheduler, VI, present, barrier, render-pass, Uniform, alias, or GPU policy is added by the harness pass.

Prepared files:

- `tools/adreno_lab/transplant_dc95_diagnostic_harness.py`
- `tools/adreno_lab/analyze_x1_dequeue_attribution.py`
- `.github/workflows/build-dc95-x1-diagnostic-harness.yml`
- `NEXT_ACTION_X1_DIAGNOSTIC_HARNESS.md`

Workflow:

`Build dc95 X1 Diagnostic Harness`

Trigger:

`workflow_dispatch` only.

The workflow recreates the full existing diagnostic chain through the swap-clamp A/B, snapshots that state, then applies only the harness pass.

Harness-only allowed temporary Eden checkout changes:

- `src/common/settings.h`
- `src/yuzu/configuration/configure_debug.h`
- `src/yuzu/configuration/configure_debug.cpp`
- `src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

The workflow hashes and requires no harness change to:

- VI conductor
- GPU core
- Vulkan swapchain
- Vulkan scheduler
- nvhost_ctrl
- generic buffer cache
- Vulkan buffer cache

The harness transplant also requires the complete existing `WaitForFreeSlotThenRelock()` helper text to remain byte-for-byte unchanged.

## Recommended first runtime matrix after a future successful build

Use the same TOTK 1.4.2 save / route / settings.

Run A — pure attribution:

- `X1 Log: Frame Cadence` ON
- `X1 Log: Dequeue Attribution` ON
- swap clamp OFF
- Uniform cache A/B OFF
- unrelated heavy logs OFF unless needed

Run B — same attribution with clamp:

- cadence ON
- dequeue ON
- swap clamp ON
- Uniform cache A/B OFF

Primary question:

> In the raw `swap=3` gameplay regime, where does the ~50 ms first appear: before Dequeue entry, inside free-slot selection/wait, or after Dequeue returns?

## What NOT to do

- no ARM64 Actions without fresh explicit permission
- no automatic rerun
- do not modify raw guest QueueBuffer data
- no VSync / Mailbox / Target_60 / speed-limit changes for this attribution
- no scheduler/fence/barrier/render-pass changes
- no buffer-count modification before measuring the baseline
- no alias trivial dedupe
- no blind persistent Uniform binding
- no blind previous staging allocation reuse
- do not treat intentional ForceStop as a crash

## NEXT ACTION

Read:

`NEXT_ACTION_X1_DIAGNOSTIC_HARNESS.md`

Static preparation is complete. **Stop before Actions.**

A fresh explicit user authorization is required for exactly one attempt of:

`Build dc95 X1 Diagnostic Harness`

If it fails, stop. No retry without another fresh explicit authorization.

## Build authorization state

- current branch: `exp/x1-diagnostic-harness`
- diagnostic-harness ARM64 build attempts: 0
- reruns: 0
- current ARM64 build authorization: **none**
- gameplay optimization promoted: none
