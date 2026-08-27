# Handoff Prompt — Eden Adreno X1 frame cadence attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-frame-cadence-attribution`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `LAB_BOOTSTRAP.md`
4. `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`
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
- gameplay fast Uniform selection was almost entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached Uniform path is mostly clean
- sampled repeated fast Uniform payloads were 97%+ same fingerprint; same-frame classified repeats were 99%+ same fingerprint
- the Uniform cache A/B build succeeded once and only once
- A/B ON completely removed adaptive fast streams but did not break the ~20 FPS gameplay ceiling; cost migrated into classic buffer copy/outside-RP/synchronization
- paired OFF runtime shows a distinct ~30 FPS light/title regime and ~19.5–19.6 FPS gameplay regime
- do not call this a proven hardcoded 20-FPS cap yet
- existing Vulkan swapchain Target_60 pacing time is tiny in the ~20 FPS regime, so do not blame that pacing path without new evidence

Exact dc95 frame-cadence source facts already checked:

- VI `Conductor` is based on 60-Hz `FrameNs`
- `HardwareComposer::ComposeLocked()` reads layer `item.swap_interval` but ends with `m_frame_number += 1; return 1;`
- a host composite is requested only when a new framebuffer is acquired
- `nvdisp_disp0::WaitForComposite()` delegates to `system.GPU().WaitForComposite()`
- `nvdisp_disp0::Composite()` delegates to `system.GPU().RequestComposite(...)`

Current diagnostic purpose:

Find where the nominal ~50-ms gameplay cadence first appears by recording, on the same host steady clock:

- `[X1-CADENCE][QUEUE]`: successful guest QueueBuffer production
- `[X1-CADENCE][ACQUIRE]`: new main/overlay framebuffer acquisition by Nvnflinger
- `[X1-CADENCE][VI]`: each active compositor tick and WaitForComposite/ComposeLocked duration

Prepared files:

- `tools/adreno_lab/transplant_dc95_frame_cadence_attribution.py`
- `tools/adreno_lab/analyze_x1_frame_cadence.py`
- `.github/workflows/build-dc95-x1-frame-cadence-attribution.yml`
- `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`

Workflow:

`Build dc95 X1 Frame Cadence Attribution`

It is `workflow_dispatch` only. Static preparation must have zero Actions runs before authorization.

The cadence transplant is observation-only and may modify only:

- `src/core/hle/service/nvnflinger/buffer_queue_producer.cpp`
- `src/core/hle/service/nvnflinger/hardware_composer.cpp`

The workflow hashes and requires no cadence-transplant change to:

- VI conductor
- GPU core composite path
- Vulkan swapchain
- Vulkan scheduler
- nvhost_ctrl syncpoint event path

Do not change VSync, speed limiter, Mailbox, Target_60, swap interval, scheduling, fences, waits, barriers, render-pass behavior, alias behavior, or game mods for this diagnostic.

NEXT ACTION:

Read `NEXT_ACTION_FRAME_CADENCE_ATTRIBUTION.md`, then stop before Actions unless the user gives a fresh explicit build authorization. If authorized, run exactly one attempt of `Build dc95 X1 Frame Cadence Attribution`. If successful, test one run containing both the ~30-FPS title/light segment and steady ~20-FPS gameplay with X1 present logging enabled, then analyze with `analyze_x1_frame_cadence.py`.
