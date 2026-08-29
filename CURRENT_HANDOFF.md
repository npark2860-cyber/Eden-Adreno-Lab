# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-30 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-k-grandparent-depth`
- Stage K branch base: `c16d4b77209d1f82738138af7657ad16429ce9e6`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Failure does not authorize retry/rerun. Current authorization: NONE.**

Ubuntu/static validation does not consume ARM64 authorization.

Runtime-observed TIDs, guest addresses, promoted keys, module bases, PC/LR/caller addresses are observations only and must not be hardcoded.

No broad/all-thread profiling. No behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

## Primary records

- Stage B runtime: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- Stage F runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- Stage G runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- Stage H implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`
- Stage H ARM build: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_BUILD.md`
- Stage H runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- Stage I SDK disassembly: `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- Stage J implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_J_IMPLEMENTED.md`
- Stage J ARM build: `DEBUG_HISTORY_20260829_WAKER_STAGE_J_BUILD.md`
- Stage J runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- Stage K implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- Stage K failed build / scope fix / strengthened static gate: `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`
- current next action: `NEXT_ACTION_WAKER_STAGE_K.md`

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current workflow name:

`Build dc95 X1 Waker Stage K`

Trigger remains exactly:

`workflow_dispatch` only.

The persistent workflow was retargeted to Stage K before the single authorized Stage K ARM attempt. It remains manual-only; no push-triggered ARM build is enabled.

Current ARM64 authorization: **NONE**.

## Latest successful ARM64 build — Stage J SUCCESS

Exactly one fresh user authorization was consumed for exactly one Stage J Windows ARM64 attempt.

- workflow: `Build dc95 X1 Waker Stage J`
- run: `33249991294`
- job: `99093918714`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `516162fd94ee751b7ac54ff68986f867329dcca7`
- exact dc95 checkout: success
- retained A-H reconstruction / invariants: success
- Stage J application / pre-configure safety verification: success
- MSYS2 / configure / ARM64 compile / package / analyzer metadata / upload: success
- conclusion: **SUCCESS**
- retry/rerun/additional ARM attempt: none

One-shot dispatcher lifecycle:

- creation commit `516162fd94ee751b7ac54ff68986f867329dcca7`
- deletion commit `0e0ebc6d68cee6261c31d2b9daaa3c351f26c4dd`

Canonical Stage J artifact:

- name: `Eden-dc95-X1-waker-stage-j`
- artifact ID: `9714363715`
- size: `31,423,548` bytes
- SHA-256: `27b250b40b879eeeea0a33e8ded66d3e0e229aef22d67f4027715bedf240f7b8`
- created: `2026-08-29T11:50:01Z`
- expires: `2026-09-12T11:49:58Z`

## Stage K Windows ARM64 attempt — FAILED

Exactly one fresh user authorization was consumed for exactly one Stage K Windows ARM64 attempt.

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33254495504`
- job: `99105748612`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- exact dc95 checkout: success
- retained chain reconstruction through Stage J: success
- Stage K snapshot/application: success
- Stage K verify before configure: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- `Build dc95 ARM64 X1 Stage K`: **FAILED**
- package / analyzer metadata / upload: skipped after compile failure
- artifact count: **0**
- retry/rerun/additional ARM attempt: **none**

One-shot dispatcher lifecycle:

- creation/dispatch commit: `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- deletion commit: `4193038f9901ecaa897b799cf037cadb99599d18`

The failed attempt does not authorize a retry. Current ARM64 authorization remains **NONE**.

### Stage K compile-failure root cause — FIXED, not ARM-retested

The earlier simple enum-name mismatch hypothesis is rejected. Exact build-head Stage J/K sources use the expected nested names:

- Stage J header/transplant: `ParentStatus`
- Stage K header/transplant: `GrandparentStatus`

Read-only generated-source inspection identified a deterministic C++ lexical-scope defect in the Stage K transplant:

- Stage J created `x1_stage_j_memory` inside a local `else` block;
- Stage K was appended after that block;
- Stage K attempted to initialize `x1_stage_k_memory` from the now-out-of-scope `x1_stage_j_memory`.

The minimal source fix is:

```diff
- auto& x1_stage_k_memory = x1_stage_j_memory;
+ auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
```

Fix commit:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

A local minimal Clang C++20 reproduction rejects the old lexical structure and accepts the corrected structure.

The fix has passed strengthened Ubuntu/static validation but has **not** been tested by another Windows ARM64 build. No retry/rerun was performed.

## Closed historical chain

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplicates; blind dedupe rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path = adaptive mapped fast stream/re-stream.
- classic-cache fallback did not break gameplay ceiling.
- QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS; VI ~= 60 Hz.
- raw3->effective2 clamp did not improve upstream frame generation.
- DFPS not root.
- BufferQueue free-slot/backpressure not primary owner.
- GPU worker predominantly waits for command supply.
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint not missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation closed for both dynamic-waker and producer slowdown.

## Causal chain through Stage H

Measured chain:

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dynamically selected producer threads
-> producer Arbitration growth + producer CPU growth
-> recurring slice-end synchronization context family.

Stage G exact scheduler `cpuTicks` reconcile essentially exactly with Stage F CPU. Saved PC/LR is a scheduler switch-out execution endpoint, not literal instruction-residency duration.

Stage H normalized recurring contexts to Nintendo `sdk`:

- `sdk+0x158528 / sdk+0x124a8c`
- `sdk+0x158420 / sdk+0x13178c`
- `sdk+0x158528 / sdk+0x124b40`
- `sdk+0x158528 / sdk+0x127058`

Absolute addresses move with ASLR; module+offset is stable.

## Stage I semantic mapping — COMPLETE

Exact dumped SDK recovered:

- `sdk+0x158528`: return after `svc #0x34` -> `WaitForAddress`
- `sdk+0x158420`: return after `svc #0x1a` -> `ArbitrateLock`
- `sdk+0x124a8c` / `+0x124b40`: `nn::os::WaitLightEvent -> WaitForAddress(WaitIfEqual,1,-1)`
- `sdk+0x127058`: `nn::os::ReceiveLightMessageQueue -> WaitForAddress(WaitIfEqual,1,-1)`
- `sdk+0x13178c`: `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`

Stage I showed slow-cadence CPU/slice grows strongly even when WaitLightEvent counts fall or remain similar. Therefore two parallel effects remain:

1. longer kernel Arbitration waiting;
2. longer active guest CPU slices before reaching the blocker.

Static first-level reverse calls were too broad: 73 direct main WaitLightEvent call sites and 4 ReceiveLightMessageQueue call sites.

## Stage J runtime — COMPLETE

Runtime log:

`eden_log(20260829-115839).txt`

SHA-256:

`d9045854c80b57eae904c62753b46713fa374df3ada385c8fc2094e3b256e952`

Environment:

- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Adreno X1-85
- Vulkan driver 512.863.0
- Vulkan 1.3.295

Strict primary windows:

- fast: frames `720,840` — pure swap2
- slow: frames `1200,1320,1440,1560` — pure swap3

### Stage J validity / accounting

- P0 valid slice coverage fast `99.97%`, slow `99.98%`; valid tick coverage `99.95% / 99.92%`
- P1 valid slice coverage fast `100%`, slow `99.93%`; valid tick coverage `100% / 99.88%`
- `fpZero=0`, `parentZero=0`, `badStatus=0`
- Stage J `cpuTicks` equal Stage G `cpuTicks`; aggregate Stage J CPU again reconciles with Stage F to around 0.002 ms or better.

### Producer slowdown reproduces

P0 fast -> slow:

- CPU `0.998 -> 3.603 ms`, `+2.606`
- Arbitration `5.192 -> 7.187`, `+1.995`
- runnable-unscheduled `0.306 -> 0.672`, only `+0.366`

P1:

- CPU `1.012 -> 3.922 ms`, `+2.910`
- Arbitration `5.513 -> 8.672`, `+3.159`
- runnable-unscheduled `0.370 -> 0.592`, only `+0.221`

Mixed producer CPU + Arbitration branch is reproduced again.

### Dynamic waker remains separate

- CPU `5.908 -> 18.093 ms`
- runnable-unscheduled `0.159 -> 0.212`
- Arbitration `5.218 -> 27.092`

Host scheduler starvation remains rejected. Do not merge waker CPU/Arbitration and producer CPU/Arbitration causal ownership without direct joining evidence.

### Canonical Stage J parent triples

1. `sdk+0x158528 / sdk+0x124a8c / main+0x86a820`
2. `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54`
3. `sdk+0x158528 / sdk+0x124b40 / main+0x86be08`
4. `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc`

`sdk+0x127e54` resolves exactly to `nn::os::LockMutex(nn::os::MutexType*)`.

Visible top-four triples explain about P0 `61.3%` and P1 `54.2%` of CPU-growth delta. Overflow is material but does not block dominant-family identification; do not widen histogram yet.

### Offline reverse mapping after Stage J

- function containing `main+0x86a820`: 2 direct callers;
- function containing `main+0x86be08`: exactly 1 direct caller, then an indirect/callback frontier;
- function containing `main+0x2a904cc`: direct BL callers = 0;
- `nn::os::LockMutex` main import/PLT fanout = **6,201** direct BL call sites.

Stage J decision = mixed A/B. Parent validity is excellent; broad static reverse-call analysis is exhausted.

## Stage K implementation / static validation — COMPLETE WITH SCOPE-FIX REGRESSION GATE

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Implementation files:

- `src/core/x1_waker_stage_k_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`
- `tools/adreno_lab/analyze_x1_waker_stage_k_grandparent_depth.py`

Stage K adds one and only one additional frame-record level inside the same Stage F selected-producer guard.

Memory-read shape:

- Stage J existing `parent_lr = [fp+8]` remains unchanged;
- Stage K range-validates `[fp, fp+8)` and reads `parent_fp = [fp]` once;
- requires nonzero/aligned `parent_fp`, `parent_fp > fp`, and no `+8` overflow;
- range-validates `[parent_fp+8, parent_fp+16)` and reads `grandparent_lr = [parent_fp+8]` once.

Thus Stage K adds exactly 2 `Read64` sites; Stage J+K selected-producer block has exactly 3 total.

Accounting remains bounded:

- producer count 2
- fixed slots 64
- top4
- 120-frame report
- context `(pc, lr, parent_lr, grandparent_lr)`

No arbitrary stack walk, non-selected sampling, thread rediscovery, slot widening, per-switch logging or behavior mutation.

### Original Ubuntu validation

- workflow: `Validate dc95 X1 Waker Stage K`
- run: `33253036148`
- job: `99101891663`
- attempt: 1
- event: `push`
- validation HEAD: `53defe670df0665554626430aaf4660cd70aa7b4`
- result: **SUCCESS**

It validated structural/read/range/invariant checks but did not compile the generated C++ integration, so it missed the lexical-scope defect exposed by the first ARM build.

Temporary original validator deletion commit:

`c08c9cf36203936e8d430532115ae08a5f59ebfc`

### Scope-fix Ubuntu regression validation

After the one-line scope fix, a second Ubuntu-only validator reconstructed exact dc95 A-J, applied Stage K, reran the original checks, verified the generated initializer, and added a C++20 syntax-only scope regression probe.

- workflow: `Validate dc95 X1 Waker Stage K Scope Fix`
- run: `33279373418`
- job: `99171791300`
- attempt: 1
- event: `push`
- validation HEAD: `3f0843208512d2878f8f02a8c7938216bf5ecf21`
- result: **SUCCESS**

Temporary validator cleanup commit:

`404a14af5a607762bd121dd98190d63c5c4466c0`

No ARM runner was used for the scope-fix validation.

Stage K Windows ARM64 run count remains **1**, result **FAILED during the pre-fix C++ build**. No artifact was produced and no retry/rerun occurred.

## Resolution-scaling observation — UNVERIFIED

- User runtime observation: changing render scale to `2×` / roughly `1440p` did not produce an obvious subjective slowdown in the current workload.
- This is an observation only; no controlled frame-time or GPU-time capture has been performed yet.
- It is consistent with the current hypothesis that the cadence ceiling is upstream of pure pixel/raster throughput — guest CPU / synchronization / submission cadence — but it does **not** prove that hypothesis.
- Required validation before promotion to a finding:
  1. confirm the actual render-target resolution increased;
  2. compare controlled `1×` vs `2×` frame time / FPS;
  3. compare GPU utilization / GPU time;
  4. compare selected-producer CPU and Arbitration timing.
- Do not use this observation alone to close GPU-side hypotheses or justify a behavior-changing optimization.

## Current causal frontier

GPU starvation
-> submitter/waker / promoted arbiter handshake
-> two selected producer threads
-> known Nintendo SDK synchronization primitives
-> Stage J parent sites expose concrete main code / LockMutex
-> static reverse-call frontier becomes indirect or extremely broad
-> Stage K dynamic-grandparent instrumentation is implemented, its identified compile blocker is fixed, and the strengthened Ubuntu/static gate passes
-> no runnable Stage K ARM artifact exists yet
-> slow cadence still has longer active CPU slices before blocker + longer kernel Arbitration.

No optimization is justified yet.

## Immediate next action — fresh explicit Stage K ARM64 authorization required

Current ARM64 authorization: **NONE**.

Do **not** dispatch, retry, or rerun ARM64 from a generic continuation command.

The next Windows ARM64 step is exactly one Stage K attempt only after the user explicitly authorizes **one ARM64 build attempt**.

Before any authorized dispatch:

1. verify current branch HEAD;
2. verify exact Eden baseline remains `dc95cd09eea9749250fe31a3072684d341d19417`;
3. verify persistent workflow remains `Build dc95 X1 Waker Stage K` and `workflow_dispatch` only;
4. verify scope-fix commit `29d4c8ef376448bd7c61d354eb125fc052ac5c0e` is present;
5. dispatch exactly one attempt;
6. if it fails, do not retry/rerun without another fresh explicit authorization.

If the build succeeds, run Stage K under the same TOTK 1.2.1 conditions and compare clean swap2/swap3 120-frame windows. Interpret grandparent attribution according to `NEXT_ACTION_WAKER_STAGE_K.md`.
