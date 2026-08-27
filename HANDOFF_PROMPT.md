# Handoff Prompt — Eden Adreno X1 swap interval 3 -> 2 A/B

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-swap-interval-3-to-2-ab`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `LAB_BOOTSTRAP.md`
4. `NEXT_ACTION_SWAP_INTERVAL_3_TO_2_AB.md`
5. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain these confirmed facts:

- alias direct CopyImage/outside-RP traffic is not trivial unchanged-state duplication; simple alias dedupe is closed
- exact dc95 Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- adaptive small-Uniform fast path is mapped staging re-stream, not payload reuse
- gameplay fast Uniform selection is almost entirely adaptive `fastSkip`; `fastAlignment=0`
- Uniform classic-cache fallback A/B did not break the gameplay ceiling and moved cost into copy/outside-RP/synchronization

Frame-cadence build succeeded in exactly one authorized attempt:

- run `33060773960`
- job `98478699166`
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`

Cadence runtime `eden_log(20260827-104943).txt` confirmed:

- stable raw `swap=2` frames 562-910: median QueueBuffer 33.352 ms, ~29.42 FPS
- stable raw `swap=3` frames 911-1758: median QueueBuffer 49.985 ms, ~17.48 FPS due additional misses
- main acquire medians ~33.506 ms vs ~50.044 ms
- VI compositor remains ~60 Hz
- WaitForComposite median 0 ms in stable swap=3 gameplay
- transition occurs at QueueBuffer frame 910 `swap=2` -> frame 911 `swap=3`

Critical meaning:

> The discrete 30 -> <=20 cadence is explained by the main guest BufferQueue raw interval changing 2 -> 3. raw 2 gives nominal 60/2=30 FPS opportunities; raw 3 gives nominal 60/3=20 FPS opportunities; missed opportunities only lower FPS further.

Exact source ownership:

- `QueueBufferInput` carries raw `s32 swap_interval` from guest `InputParcel`
- `BufferQueueProducer::QueueBuffer()` stores it unchanged as `item.swap_interval`
- HardwareComposer uses it for main acquire spacing and release-frame bookkeeping
- Qualcomm Vulkan / Mailbox / Target_60 do not create the raw 3

Current A/B static preparation is complete.

Checkbox:

`X1 A/B: Clamp Main Swap Interval 3 To 2`

Default OFF.

ON behavior in the dedicated Windows ARM64 Vulkan X1 diagnostic build:

- preserve raw guest parcel / `item.swap_interval`
- preserve QUEUE raw swap logging
- main non-overlay raw exactly 3 uses effective acquire/release interval 2
- overlays unchanged
- all other raw intervals unchanged
- ACQUIRE log reports both `swap=<raw>` and `effective=<composer>`

Prepared files:

- `tools/adreno_lab/transplant_dc95_swap_interval_3_to_2_ab.py`
- updated `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-swap-interval-3-to-2-ab.yml`
- `NEXT_ACTION_SWAP_INTERVAL_3_TO_2_AB.md`

Workflow:

`Build dc95 X1 Swap Interval 3 To 2 AB`

It is `workflow_dispatch` only. Static safety checks preserve raw QueueBuffer producer, VI conductor, GPU, Vulkan swapchain/scheduler, nvhost_ctrl and buffer-cache paths.

NEXT ACTION:

Read `NEXT_ACTION_SWAP_INTERVAL_3_TO_2_AB.md` and stop before Actions.

A fresh explicit user authorization is required for exactly one ARM64 build attempt. No current build authorization exists.
