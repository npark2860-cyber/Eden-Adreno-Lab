# DEBUG HISTORY — 2026-08-29 Waker Stage K Implemented / Ubuntu Static Validation

## Scope

Implement exactly one additional AArch64 frame-record caller level for only the two Stage F dynamically selected producer threads, on top of the already-validated Stage J parent-LR capture.

No Windows ARM64 build/rebuild/rerun was performed.

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Branch base:

`c16d4b77209d1f82738138af7657ad16429ce9e6`

Current ARM64 authorization: **NONE**.

## Source-of-truth input

Stage J runtime established essentially complete saved-x29 parent-LR validity and stable parent triples:

- `sdk+0x158528 / sdk+0x124a8c / main+0x86a820`
- `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54`
- `sdk+0x158528 / sdk+0x124b40 / main+0x86be08`
- `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc`

Offline reverse-call analysis was exhausted before Stage K:

- two direct callers for the function containing `main+0x86a820`;
- one direct caller for the function containing `main+0x86be08`, with an indirect/callback frontier above it;
- zero direct BL callers for the function containing `main+0x2a904cc`;
- `nn::os::LockMutex` main import fanout = 6,201 direct BL call sites.

The exact dumped SDK/main inspection already showed standard AArch64 frame records in the relevant visible parent paths. Stage K therefore remains a bounded one-level frame walk rather than arbitrary stack scanning.

## Implementation files

- `src/core/x1_waker_stage_k_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`
- `tools/adreno_lab/analyze_x1_waker_stage_k_grandparent_depth.py`

Runtime marker:

`[X1-WAKERK]`

## Exact memory-read shape

Stage K is inserted inside the existing Stage F selected-producer guard used by Stage G/J.

It reuses:

- Stage G saved context;
- Stage J saved `fp`;
- Stage J parent-LR result/status;
- Stage J `ApplicationMemory()` reference.

Only if Stage J parent status is valid:

1. validate `[fp, fp+8)`;
2. read exactly one `parent_fp = [fp]`;
3. require `parent_fp != 0`;
4. require natural `u64` alignment;
5. require `parent_fp > fp` for monotonic AArch64 frame ancestry;
6. guard `parent_fp + 8` overflow;
7. validate `[parent_fp+8, parent_fp+16)`;
8. read exactly one `grandparent_lr = [parent_fp+8]`.

Therefore Stage K adds exactly **two** memory-read sites. Together with Stage J's existing parent-LR read, the selected-producer block contains exactly **three** `Read64` sites total.

No non-selected thread performs these reads.

## Bounded accounting

Stage K attributes the same scheduler `tick_diff` to:

`(pc, lr, parent_lr, grandparent_lr)`

Limits remain:

- producer count: 2
- fixed context slots: 64 per producer
- top report count: 4
- report cadence: 120 frames

No slot widening was performed.

Grandparent status accounting distinguishes:

- valid
- Stage J parent unavailable
- invalid current-frame FP range
- zero parent FP
- bad/unaligned/non-monotonic/overflowing parent FP
- invalid grandparent LR range
- zero grandparent LR

## Hard limits preserved

Stage K does **not**:

- hardcode observed TIDs, absolute addresses, PC/LR/parent values or module bases;
- rediscover threads;
- sample non-selected threads;
- walk more than one additional frame record;
- scan arbitrary stack memory;
- add per-switch logging;
- alter Stage F/G/J profiler tables;
- alter priority, affinity, core placement, yield, reschedule, waits, signals, GPU work, QueueBuffer, swap interval, cadence or A/B behavior.

## Ubuntu static validation

Temporary workflow:

`Validate dc95 X1 Waker Stage K`

Run:

`33253036148`

Job:

`99101891663`

Event:

`push`

Validation HEAD:

`53defe670df0665554626430aaf4660cd70aa7b4`

Result:

**SUCCESS** on attempt 1.

Validated:

- exact dc95 checkout;
- retained non-scheduler patches;
- full A-J reconstruction;
- Stage K transplant anchors;
- `git diff --check`;
- Python syntax for J/K transplants and analyzers;
- exact saved `fp` / memory API prerequisites;
- `[X1-WAKERK]` profiler marker;
- exactly 2 Stage K `Read64` sites;
- exactly 2 Stage K range-validation sites;
- exactly 3 total `Read64` sites in the selected-producer block including Stage J;
- exactly one direct saved `x1_stage_g_context.fp` use;
- monotonic `parent_fp > fp` enforcement;
- one Stage K scheduler record call / init / frame-end hook;
- unchanged Stage F/G/J profiler headers and Stage H loader mapping;
- no observation-address hardcodes;
- no behavior-changing scheduler/GPU tokens;
- synthetic four-level module+offset analyzer normalization.

Temporary validation workflow was deleted after success at commit:

`c08c9cf36203936e8d430532115ae08a5f59ebfc`

## Static conclusion

Stage K is implemented and Ubuntu-static validated with the intended narrow observation-only shape.

No ARM64 run has been created for Stage K.

The persistent ARM workflow still names/builds Stage J and remains `workflow_dispatch` only. It was intentionally not retargeted or dispatched under this implementation-only authorization.

A future Stage K Windows ARM64 attempt requires a fresh explicit user authorization. On that authorization, retarget the persistent manual workflow to Stage K, verify it remains `workflow_dispatch` only, then dispatch exactly one attempt. Failure does not authorize retry/rerun.
