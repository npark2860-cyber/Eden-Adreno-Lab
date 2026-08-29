# NEXT ACTION — Waker Stage H ARM Build / Runtime

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-h-module-callpath-mapping`

Stage H base repository HEAD:

`59cbc61cafe8c1ae7360dc7e04e6f884c7a74512`

Never change the exact Eden baseline without explicit approval.

## Stage H implementation state

Implementation and Ubuntu/static validation are complete.

Stage H shape:

1. exact dc95 loader emits one bounded `[X1-WAKERH] module/base/end/size` line per loaded application NSO under the existing address-arbiter diagnostic setting;
2. existing loader module-map insertion behavior is preserved;
3. Stage G scheduler/hot path is unchanged;
4. Stage G `ContextSlotCount=64` is unchanged;
5. offline analyzer joins `[X1-WAKERH]` ranges to `[X1-WAKERG]` top raw PC/LR and emits canonical `module+offset` identities while retaining raw addresses.

No runtime-observed TID, promoted address, PC or LR is hardcoded.

Ubuntu validation:

- workflow: `Validate dc95 X1 Waker Stage H`
- run: `33246317401`
- job: `99084287770`
- attempt: `1`
- validation HEAD: `d39bfa3a814467f3b009202d626d4ee872db73f5`
- conclusion: `success`

Temporary Ubuntu workflow was deleted after success.

Persistent ARM workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current prepared workflow name:

`Build dc95 X1 Waker Stage H`

Trigger:

`workflow_dispatch` only.

Future artifact name:

`Eden-dc95-X1-waker-stage-h`

Stage H ARM64 attempts so far: `0`.

Current ARM64 authorization: **NONE**.

## Immediate next action

Do nothing until the user supplies a fresh explicit ARM64 authorization.

A fresh `ㄱㄱ` after the Stage H implementation/static report means:

> trigger exactly one Stage H ARM64 attempt using the persistent manual workflow on `exp/x1-waker-stage-h-module-callpath-mapping`.

Rules:

- one authorization = exactly one ARM64 attempt;
- no retry;
- no rerun;
- no second attempt after failure without another fresh authorization;
- do not reinterpret older approvals;
- do not change the exact Eden baseline.

## After a successful authorized ARM build

Record:

- workflow run ID;
- job ID;
- attempt number;
- build HEAD;
- exact dc95 verification result;
- Stage G reconstruction/precheck result;
- Stage H pre-configure verification result;
- conclusion;
- artifact name / ID / size / SHA-256;
- explicit retry/rerun state.

Then run the same TOTK 1.2.1 gameplay capture with behavior-changing A/Bs OFF and enough 120-frame windows to separate pure swap2 and pure swap3.

Analyze together:

- `[X1-WAKERH]` module ranges;
- `[X1-WAKERG]` producer top PC/LR contexts;
- `[X1-WAKERF]` producer CPU/Waiting trend;
- raw QueueBuffer cadence.

Run:

`tools/adreno_lab/analyze_x1_waker_stage_h_module_mapping.py <eden_log>`

Canonical cross-run identity is `module+offset`; raw absolute PC/LR remains audit evidence only.

## Runtime decision map

A. Dominant saved PCs normalize to a shared runtime/synchronization module and a small LR caller set:

> map those caller offsets to exact guest runtime/source semantics before adding caller depth.

B. Dominant contexts normalize to producer-specific game module work paths:

> map exact module offsets to guest work semantics before considering optimization.

C. PC is a generic runtime/SVC endpoint and LR is still insufficient:

> add only the smallest selected-producer-only caller-depth evidence; do not broaden to all threads.

D. The 64-slot overflow still prevents the dominant normalized family from being identified:

> only then redesign the fixed histogram representation/slot budget.

Keep the producer CPU branch, producer Arbitration branch, and separate Stage D dynamic-waker CPU branch distinct until direct evidence joins them.

No optimization is justified yet.
