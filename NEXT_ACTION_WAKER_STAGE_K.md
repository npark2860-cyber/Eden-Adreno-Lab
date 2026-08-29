# NEXT ACTION — Waker Stage K Dynamic Grandparent Attribution

Updated: 2026-08-30 KST

## Source of truth

Read first:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`

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

## Stage K implementation — COMPLETE

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

## Original Ubuntu validation — SUCCESS

Workflow:

`Validate dc95 X1 Waker Stage K`

- run `33253036148`
- job `99101891663`
- attempt `1`
- event `push`
- validation HEAD `53defe670df0665554626430aaf4660cd70aa7b4`
- result **SUCCESS**

This gate validated structural invariants but did not actually compile the generated C++ integration and therefore failed to catch the later lexical-scope defect.

Temporary validator deletion commit:

`c08c9cf36203936e8d430532115ae08a5f59ebfc`

## First Stage K Windows ARM64 attempt — FAILED

Exactly one fresh authorization was consumed for one Stage K Windows ARM64 attempt:

- workflow: `Build dc95 X1 Waker Stage K`
- run `33254495504`
- job `99105748612`
- attempt `1`
- event `workflow_dispatch`
- build/source HEAD `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- exact dc95 checkout: success
- A-J reconstruction: success
- Stage K application / pre-configure verification: success
- configure: success
- C++ build: **FAILED**
- artifact count: `0`
- retry/rerun: none

The failed attempt did not authorize a retry.

## Compile-blocking root cause — FIXED

The simple enum-name mismatch hypothesis was rejected. Exact build-head J/K sources use the expected `ParentStatus` / `GrandparentStatus` names.

The actual deterministic integration defect was lexical scope:

- Stage J declared `x1_stage_j_memory` inside a local `else` block;
- Stage K was appended outside that block;
- Stage K attempted `auto& x1_stage_k_memory = x1_stage_j_memory;` after the J local had gone out of scope.

Minimal fix:

```diff
- auto& x1_stage_k_memory = x1_stage_j_memory;
+ auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
```

Fix commit:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

No Stage F/G/J logic or behavior-changing scheduler/GPU path was changed.

## Scope-fix Ubuntu regression validation — SUCCESS

Temporary Ubuntu-only validator:

`Validate dc95 X1 Waker Stage K Scope Fix`

- run `33279373418`
- job `99171791300`
- attempt `1`
- event `push`
- validation HEAD `3f0843208512d2878f8f02a8c7938216bf5ecf21`
- result **SUCCESS**

In addition to the original structural checks, this gate verifies the actual generated Stage K initializer and runs a C++20 syntax-only scope regression probe so the out-of-scope reuse cannot silently pass again.

Temporary validator cleanup commit:

`404a14af5a607762bd121dd98190d63c5c4466c0`

## Persistent ARM workflow state

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current workflow name:

`Build dc95 X1 Waker Stage K`

Trigger remains:

`workflow_dispatch` only.

No push-triggered ARM build is enabled.

## Immediate next action — fresh explicit ARM64 authorization required

Current ARM64 authorization: **NONE**.

The compile-blocking scope defect is fixed and the strengthened Ubuntu/static gate passes, but that does not prove a full Windows ARM64 build will succeed.

Do not dispatch, retry, or rerun Stage K ARM64 from a generic continuation command. A new Stage K Windows ARM64 attempt requires a fresh explicit authorization that clearly approves **one ARM64 build attempt**.

When that authorization is received, perform exactly one attempt:

1. verify current Stage K branch HEAD;
2. verify fixed Eden baseline is still exact dc95;
3. verify persistent workflow is still `Build dc95 X1 Waker Stage K` and `workflow_dispatch` only;
4. verify the Stage K scope fix is present;
5. dispatch exactly one Windows ARM64 Stage K attempt;
6. do not retry/rerun if it fails without another fresh authorization.

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
