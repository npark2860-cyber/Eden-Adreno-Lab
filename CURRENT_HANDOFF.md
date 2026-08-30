# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-30 KST

## Fixed baseline / rules

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Immutable control branch:

`lab/dc95-arm64-baseline`

Current experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Failure does not authorize retry/rerun. Current authorization: NONE.**

Ubuntu/static validation does not consume ARM64 authorization.

Runtime TIDs, guest addresses, promoted keys, module bases, PC/LR/caller addresses are observations only. Never hardcode them.

No broad/all-thread profiling. No behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

## Read these records first

- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`

Do not reconstruct project state from chat guesses when these documents can be checked.

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

No push-triggered ARM build is enabled.

Current ARM64 authorization: **NONE**.

## Stage K build history

### First Windows ARM64 attempt — FAILED before fix

- run: `33254495504`
- job: `99105748612`
- attempt: `1`
- build/source HEAD: `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- exact dc95 checkout: success
- retained chain reconstruction through Stage J: success
- Stage K apply / pre-configure verification: success
- configure: success
- C++ build: **FAILED**
- artifact: none
- retry/rerun: none

Root cause was a deterministic C++ lexical-scope defect in the Stage K transplant:

```diff
- auto& x1_stage_k_memory = x1_stage_j_memory;
+ auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
```

Fix commit:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

The earlier enum-name mismatch theory is rejected.

### Scope-fix Ubuntu regression gate — SUCCESS

- workflow: `Validate dc95 X1 Waker Stage K Scope Fix`
- run: `33279373418`
- job: `99171791300`
- validation HEAD: `3f0843208512d2878f8f02a8c7938216bf5ecf21`
- result: **SUCCESS**

This gate reconstructed exact dc95 A-J, applied K, reran structural checks, verified the generated initializer, and added a C++20 syntax-only scope regression probe.

Temporary validator cleanup:

`404a14af5a607762bd121dd98190d63c5c4466c0`

### Post-fix Windows ARM64 attempt — SUCCESS

A new explicit authorization was consumed for exactly one attempt.

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- exact dc95 checkout: success
- A-J reconstruction: success
- Stage K apply / pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 C++ build: **SUCCESS**
- package: success
- analyzer/metadata: success
- upload: success
- retry/rerun/additional ARM attempt: none

One-shot dispatcher lifecycle:

- creation/dispatch commit: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- removal commit: `112541623742853bdb1c6114959f5bb5317cde89`

Canonical Stage K artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- size: `31,427,618` bytes
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- created: `2026-08-30T02:50:02Z`
- expires: `2026-09-13T02:49:59Z`

The Stage K compile blocker is closed.

## Stage K runtime capture 1 — Res2X abnormal rendering

Log:

`eden_log(20260830-025816).txt`

SHA-256:

`89784845234bd896149c61b9a856ab3b8b720b6588d6a9bb6a38b34a5755d2cf`

Environment:

- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- Dynarmic
- `Renderer.resolution_setup: Res2X`
- FSR filter
- behavior-changing X1 A/B toggles off

User observation:

- image showed only approximately the upper-left quarter;
- one earlier launch terminated before normal game operation; that terminated process is not represented by this surviving log, so the crash cause is not established.

Full-log rendering-error count:

- unsupported D32_FLOAT scaling: `12,091`
- unsupported D16_UNORM scaling: `7,685`
- total `BlitScaleHelper` unsupported-scaling errors: **19,776**

This is the first clearly abnormal rendering observation in the long attribution chain, but do not assign it to Stage K frame walking merely from chronology.

Stage K itself continued producing bounded records without widespread grandparent validity failure.

## Stage K runtime capture 2 — Res1X primary capture

Log:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

The log records:

`Renderer.resolution_setup: Res1X`

Full-log A/B result:

- Res2X `BlitScaleHelper` unsupported-scaling errors: **19,776**
- Res1X `BlitScaleHelper` unsupported-scaling errors: **0**
- `VK_ERROR_UNKNOWN`: 2 occurrences in both captures; not a new Stage K-only signature
- no fatal/unhandled/crash text found in the Res1X log

The user supplied this Res1X capture after the requested A/B. The chat contains no explicit textual confirmation that the visible image returned to normal; do not invent that visual observation. The log-level fact is that the massive Res2X depth-scaling error stream disappears completely at Res1X.

## Stage K runtime validity

Res1X late windows show healthy grandparent capture.

Frame `1200`:

- P0: `3511` slices / `3509` valid
- P1: `3351` slices / `3350` valid
- both: `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`

Frame `1560`:

- P0: `4190` slices / `4189` valid
- P1: `4023` slices / `4022` valid
- both: `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`

Only tiny sporadic `parentUnavailable` remains. No material Stage K frame-walk validity collapse is observed.

## Strict Stage K cadence windows

Use only pure QueueBuffer cadence windows in the Res1X capture:

- fast / pure swap2: `960`, `1080`
- slow / pure swap3: `1320`, `1440`, `1560`, `1680`

Mixed windows such as `840` and `1200` are not primary evidence.

## Stage K normalized grandparent result

Final Res1X module ranges:

- main: `0x800c1000-0x847ec000`
- subsdk0: `0x847ec000-0x84e95000`
- sdk: `0x84e95000-0x85c6e000`

Recurring principal quadruples normalize to:

1. `sdk+0x158528 / sdk+0x124a8c / main+0x86a820 / main+0x86a490`
2. `sdk+0x158528 / sdk+0x124b40 / main+0x86be08 / main+0x86bc9c`
3. `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc / main+0x2a2d958`
4. `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54 / main+0x86a530`

The LockMutex family also shows recurring `main+0x86a678`; keep it separate until exact static mapping.

This is the main Stage K advance: the dominant Stage J synchronization families now reach concrete `main` grandparent return addresses.

Do not yet call these final game-work owners. They require exact enclosing-function and call-site mapping against the dumped TOTK 1.2.1 main NSO.

## Known semantic chain through Stage J

Exact Stage I SDK mapping remains authoritative:

- `sdk+0x158528`: return after `svc #0x34` = `WaitForAddress`
- `sdk+0x158420`: return after `svc #0x1a` = `ArbitrateLock`
- `sdk+0x124a8c / +0x124b40`: `WaitLightEvent`
- `sdk+0x127058`: `ReceiveLightMessageQueue`
- `sdk+0x13178c`: `InternalCriticalSectionImplByHorizon::Enter`
- `sdk+0x127e54`: `LockMutex`

Stage J parents were:

- `main+0x86a820`
- `main+0x86be08`
- `main+0x2a904cc`
- `sdk+0x127e54`

Stage K now supplies the next main-side caller layer listed above.

## Closed historical findings — do not reopen without new evidence

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
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint are not the missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation is closed as primary owner for dynamic-waker and selected-producer slowdowns.

## Current causal frontier

Measured chain remains:

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two selected producer threads
-> producer CPU growth + producer Arbitration growth
-> exact Nintendo SDK blocker semantics
-> Stage J main/LockMutex parent
-> Stage K concrete main grandparent return addresses.

Slow cadence still has both longer active guest CPU slices before blocker and longer kernel Arbitration.

No optimization is justified yet.

## Resolution-scaling caveat

The earlier subjective observation that 2x resolution caused little slowdown must **not** be promoted as proof of a CPU-only ceiling.

The Res2X run had abnormal quarter-screen output and 19,776 unsupported depth-scaling errors. It has not been proven that the intended 2x workload rendered and presented correctly.

Durable rule:

> Do not use resolution-insensitivity as GPU-vs-CPU evidence until the scaling path is verified healthy and the actual increased rendering workload is confirmed.

This caveat does not erase the independently measured CPU/synchronization causal chain.

## Immediate next action — OFFLINE ONLY, no new ARM build

Current ARM64 authorization: **NONE**.

Do not build, rerun, or add Stage L now.

Use the exact dumped TOTK 1.2.1 main NSO and map these Stage K grandparent offsets:

- `main+0x86a490`
- `main+0x86bc9c`
- `main+0x2a2d958`
- `main+0x86a530`
- recurring `main+0x86a678`

For each:

1. locate the exact enclosing function / prologue boundary;
2. identify the call whose return address equals the captured grandparent LR;
3. classify concrete work vs generic wrapper vs job/callback/indirect frontier;
4. correlate that family with strict swap2 vs swap3 Stage K CPU-tick growth;
5. retain module+offset normalization, never raw VA.

Only after this offline mapping decide whether Stage K is sufficient or whether one further narrowly bounded attribution is justified.

## New-tab startup instruction

On a fresh tab:

1. use GitHub docs above as source of truth; do not reconstruct from prior chat;
2. verify branch is `exp/x1-waker-stage-k-grandparent-depth`;
3. verify persistent ARM workflow remains `Build dc95 X1 Waker Stage K` / `workflow_dispatch` only;
4. verify current ARM64 authorization is NONE;
5. read `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md` and `NEXT_ACTION_WAKER_STAGE_K.md`;
6. begin immediately with offline main-NSO mapping of the five Stage K grandparent offsets.
