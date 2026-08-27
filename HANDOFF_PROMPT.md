# Handoff Prompt — Eden Adreno X1 Diagnostic Harness

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-diagnostic-harness`

Do not reconstruct state from old chat. First read these GitHub documents and treat them as source of truth:

1. `CURRENT_HANDOFF.md`
2. `DEBUG_HISTORY.md`
3. `LAB_BOOTSTRAP.md`
4. `NEXT_ACTION_X1_DIAGNOSTIC_HARNESS.md`
5. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD and Actions state against the documents before doing anything else.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Hard build rule:

- never start or rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one build attempt
- if that attempt fails, stop; no retry without another explicit authorization

Retain the closed facts in `CURRENT_HANDOFF.md`, especially:

- alias trivial dedupe is closed
- adaptive Uniform fast stream is mapped staging re-stream; wholesale classic-cache fallback did not fix gameplay
- raw main BufferQueue `swap=2 -> 3` explains the discrete 30 -> <=20 cadence shape
- raw swap originates in guest QueueBuffer input, not Qualcomm Vulkan Present
- the raw-3/effective-2 HardwareComposer A/B executed correctly but did not break the gameplay ceiling
- therefore HardwareComposer interval-3 gating is not the primary cause; upstream producer timing must be split

Current work is the runtime-selectable X1 Diagnostic Harness.

It keeps the existing diagnostic/A-B controls in one binary and adds:

- `X1 Log: Frame Cadence`
- `X1 Log: Dequeue Attribution`

Dequeue attribution is observation-only and splits:

1. previous Queue -> Dequeue BEGIN
2. Dequeue service/free-slot helper
3. Dequeue END -> next Queue

Prepared files:

- `tools/adreno_lab/transplant_dc95_diagnostic_harness.py`
- `tools/adreno_lab/analyze_x1_dequeue_attribution.py`
- `.github/workflows/build-dc95-x1-diagnostic-harness.yml`
- `NEXT_ACTION_X1_DIAGNOSTIC_HARNESS.md`

Workflow:

`Build dc95 X1 Diagnostic Harness`

It is `workflow_dispatch` only.

NEXT ACTION:

Read `NEXT_ACTION_X1_DIAGNOSTIC_HARNESS.md` and stop before Actions.

No current ARM64 build authorization exists. A fresh explicit user authorization is required for exactly one build attempt.
