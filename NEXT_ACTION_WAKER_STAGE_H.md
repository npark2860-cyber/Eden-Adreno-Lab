# NEXT ACTION — Waker Stage H Runtime

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_BUILD.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-h-module-callpath-mapping`

Never change the exact Eden baseline without explicit approval.

## Stage H build state — COMPLETE

The single authorized Stage H ARM64 attempt succeeded.

- workflow: `Build dc95 X1 Waker Stage H`
- run: `33246620972`
- job: `99085091095`
- attempt: `1`
- event: `workflow_dispatch`
- build HEAD: `1c8b699ccc51ff7bca28fc57bf654c1e18fbd5f2`
- exact dc95 verification: success
- Stage A-G reconstruction / Stage H pre-configure verification: success
- MSYS2 / configure / ARM64 compile / package / upload: success
- conclusion: success
- retry/rerun/additional ARM attempt: none

Canonical artifact metadata from two consecutive direct GitHub artifact API queries:

- name: `Eden-dc95-X1-waker-stage-h`
- artifact ID: `9713380302`
- size: `31,419,464` bytes
- SHA-256: `ff166f3f39c695c1e8e879a7ecbfeca2916028f3318802123bed584775fe4d90`
- created: `2026-08-29T10:24:24Z`
- expires: `2026-09-12T10:24:22Z`

The one-shot dispatcher used to issue the approved dispatch was removed immediately afterward. Dispatcher cleanup commit: `135d13a57d434e23d7f68928d0f335ed959d0892`. Later documentation-only commits move branch HEAD further. Persistent ARM workflow remains `workflow_dispatch` only.

A follow-up `ㄱㄱ` received while run `33246620972` was still active was **not** consumed as authorization for another ARM attempt.

Current ARM64 authorization: **NONE**.

## Immediate next action — runtime only

Use artifact:

`Eden-dc95-X1-waker-stage-h`

Run the same TOTK 1.2.1 gameplay capture used for Stage G.

Keep behavior-changing A/B experiments OFF. Capture enough continuous gameplay to obtain multiple clean 120-frame windows in both:

- pure swap2;
- pure swap3.

Upload the resulting Eden log.

No ARM rebuild is needed for this action.

## Required runtime evidence

Analyze together:

- `[X1-WAKERH]` module ranges;
- `[X1-WAKERG]` selected-producer top saved PC/LR contexts;
- `[X1-WAKERF]` producer CPU/Waiting trend;
- raw QueueBuffer cadence.

Run:

`tools/adreno_lab/analyze_x1_waker_stage_h_module_mapping.py <eden_log>`

Canonical cross-run identity is `module+offset`; raw absolute PC/LR remains audit evidence only.

Stage G's saved PC is a scheduler slice-end execution context, not proof that all attributed CPU time was spent in that single instruction.

## Runtime decision map

A. Dominant saved PCs normalize to a shared runtime/synchronization module and a small LR caller set:

> map those caller offsets to exact guest runtime/source semantics before adding caller depth.

B. Dominant contexts normalize to producer-specific game module work paths:

> map exact module offsets to guest work semantics before considering optimization.

C. PC is a generic runtime/SVC endpoint and LR is still insufficient:

> add only the smallest selected-producer-only caller-depth evidence; do not broaden to all threads.

D. The 64-slot overflow still prevents the dominant normalized family from being identified:

> only then redesign the fixed histogram representation/slot budget.

Keep these branches distinct until direct evidence joins them:

1. producer CPU growth;
2. producer Arbitration recursion;
3. separate Stage D dynamic-waker CPU growth.

No optimization is justified yet.

## ARM64 gate

No build/rebuild/rerun is authorized now.

Any future ARM64 attempt requires a new explicit user authorization after the runtime evidence is analyzed. One authorization still means exactly one attempt, with no automatic retry or rerun.
