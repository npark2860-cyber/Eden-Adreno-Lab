# Handoff Prompt — Eden Adreno X1 swap-interval cadence result

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
4. `NEXT_ACTION_SWAP_INTERVAL_3_AB.md`
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
- Uniform classic-cache fallback A/B did not break the gameplay ceiling and moved cost into copy/outside-RP/synchronization

Frame-cadence build — SUCCESS, exactly one authorized attempt:

- workflow `Build dc95 X1 Frame Cadence Attribution`
- run `33060773960`
- job `98478699166`
- attempt 1
- build HEAD `d49d5a20b17a4e6861aad036474600697ac14fc8`
- artifact `Eden-dc95-X1-frame-cadence-attribution`
- artifact id `9642483710`
- SHA-256 `b9140318047ac09462751ad5c6dc1d598122cc82c2ea78bfe03a5c33fc91f870`

Runtime log:

`eden_log(20260827-104943).txt`

CONFIRMED runtime result:

- stable guest QueueBuffer frames 562-910 use `swap=2`
- that regime has median queue interval 33.352 ms and effective rate ~29.42 FPS
- stable guest QueueBuffer frames 911-1758 use `swap=3`
- that regime has median queue interval 49.985 ms and effective rate ~17.48 FPS because additional 3-tick opportunities are missed
- main acquire median follows the same pattern: ~33.506 ms for swap 2, ~50.044 ms for swap 3
- VI compositor itself remains ~60 Hz: median ~16.6 ms
- WaitForComposite is not the continuous missing interval; median 0 ms in gameplay and only four >1 ms events in the stable swap-3 segment

Critical meaning:

> The user's '30 FPS title / almost always <=20 FPS gameplay / rarely 22-23' observation is explained by the main guest BufferQueue raw swap interval changing from 2 to 3. swap 2 gives nominal 60/2=30 FPS opportunities; swap 3 gives nominal 60/3=20 FPS opportunities; misses only lower FPS further.

Exact dc95 source ownership is also confirmed:

- `QueueBufferInput` contains `s32 swap_interval`
- it is directly read from the guest `InputParcel` via `parcel.ReadFlattened(*this)`
- `BufferQueueProducer::QueueBuffer()` assigns that value directly to `item.swap_interval`
- HardwareComposer honors it for main-layer acquire spacing and release-frame bookkeeping
- this raw 3 is therefore already present before host Vulkan Present; do not blame Qualcomm Vulkan, Mailbox, or Target_60 for creating the 20-FPS step

Still unknown:

- why TOTK selects/sends swap interval 3 in this runtime
- whether it is purely a symptom of missing the 30-FPS budget
- whether Eden's acquire/release policy helps create a feedback ceiling once raw 3 is active

NEXT ACTION:

Read `NEXT_ACTION_SWAP_INTERVAL_3_AB.md`.

The next diagnostic is **proposal only**: a main non-overlay A/B that preserves/logs raw guest interval 3 but, when enabled, uses an effective composer acquire/release interval 2 only for raw interval exactly 3.

Purpose: distinguish `swap=3 is only a symptom` from `swap=3 also participates in a feedback ceiling`.

Do not implement or build this A/B without fresh explicit user approval. No current ARM64 build authorization exists.
