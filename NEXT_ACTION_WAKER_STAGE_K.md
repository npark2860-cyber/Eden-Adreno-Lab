# NEXT ACTION — Waker Stage K Dynamic Grandparent Attribution

Updated: 2026-08-29 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current source branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM build/rebuild/rerun is authorized by this document.

## Stage J result — COMPLETE

Stage J parent-LR capture is valid for essentially all selected-producer CPU ticks and reconciles with Stage G/F accounting.

Dominant canonical triples:

- `sdk+0x158528 / sdk+0x124a8c / main+0x86a820`
- `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54`
- `sdk+0x158528 / sdk+0x124b40 / main+0x86be08`
- `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc`

Visible top-four triples explain about `61% / 54%` of producer 0 / producer 1 CPU-growth delta. Overflow remains material but does not prevent dominant-family identification.

Offline reverse-call analysis is exhausted at this depth:

- function containing `main+0x86a820`: 2 direct callers;
- function containing `main+0x86be08`: 1 direct caller, then indirect/callback frontier;
- function containing `main+0x2a904cc`: 0 direct BL callers;
- `nn::os::LockMutex` main import: 6,201 direct BL call sites.

## Stage K implementation/static — COMPLETE

Stage K adds exactly one more frame-record level for only the two Stage F dynamically selected producers.

Files:

- `src/core/x1_waker_stage_k_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`
- `tools/adreno_lab/analyze_x1_waker_stage_k_grandparent_depth.py`

At the existing selected-producer switch-out block:

1. reuse Stage J saved `fp` and parent status/LR;
2. if Stage J parent is valid, range-validate `[fp, fp+8)`;
3. read `parent_fp = [fp]` exactly once;
4. require nonzero, aligned, monotonic `parent_fp > fp`, and no `+8` overflow;
5. range-validate `[parent_fp+8, parent_fp+16)`;
6. read `grandparent_lr = [parent_fp+8]` exactly once;
7. attribute the same scheduler `tick_diff` to `(pc, lr, parent_lr, grandparent_lr)`;
8. keep 2 producers / 64 fixed slots / top4 / 120-frame reporting.

This is one additional frame-record level, not arbitrary stack scanning.

Stage K adds exactly 2 read sites. Combined Stage J+K selected-producer block contains exactly 3 `Read64` sites total.

## Ubuntu validation — SUCCESS

Workflow:

`Validate dc95 X1 Waker Stage K`

- run `33253036148`
- job `99101891663`
- attempt `1`
- event `push`
- validation HEAD `53defe670df0665554626430aaf4660cd70aa7b4`
- result **SUCCESS**

Validated exact dc95 -> A-J reconstruction, Stage K anchors, read/range counts, saved-FP reuse, monotonic ancestry check, unchanged F/G/J/H invariants, no hardcoded observations, no behavior mutation, and synthetic four-level module normalization.

Temporary validator was deleted after success; deletion commit:

`c08c9cf36203936e8d430532115ae08a5f59ebfc`

## Persistent ARM workflow state

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

It currently still names/builds Stage J and remains:

`workflow_dispatch` only.

This was intentionally left untouched because the current authorization covered Stage K implementation + Ubuntu/static validation only.

Stage K Windows ARM64 run count: **0**.

## Immediate next action — fresh ARM authorization required

A fresh explicit user authorization is required before exactly one Stage K Windows ARM64 attempt.

A fresh `ㄱㄱ` received after this ready state means:

> retarget the persistent manual workflow from Stage J to Stage K without changing the exact dc95 baseline or manual-only trigger, verify the workflow and branch HEAD, then dispatch exactly one Windows ARM64 Stage K attempt.

One authorization = exactly one ARM attempt. Failure does not authorize retry/rerun.

Before dispatch verify:

- current Stage K branch HEAD;
- fixed Eden baseline remains exact dc95;
- persistent workflow remains `workflow_dispatch` only after retargeting;
- Stage K workflow includes K profiler copy/transplant/pre-configure checks/analyzer/artifact naming;
- Stage K Windows ARM64 run count is still 0.

## Runtime decision after a successful Stage K build

Use the same TOTK 1.2.1 conditions and enough clean swap2/swap3 120-frame windows.

A. Grandparent LR collapses dominant families to a small stable `main/subsdk0` owner set:

> map exact module offsets offline and determine whether the producer CPU-growth branch can finally be assigned to concrete game work.

B. A major family still lands in generic SDK code:

> resolve that wrapper offline first; do not automatically add another depth.

C. Grandparent frame validity degrades materially for a specific family:

> stop frame walking and inspect exact frame/prologue/unwind semantics; do not introduce broad stack scanning.

D. Grandparent is stable but bounded overflow still contains most unexplained CPU growth:

> only then reconsider bounded histogram representation for selected producers.

Do not optimize merely from synchronization function names.
