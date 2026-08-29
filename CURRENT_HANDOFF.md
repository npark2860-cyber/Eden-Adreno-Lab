# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-j-caller-depth`

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
- active next action: `NEXT_ACTION_WAKER_STAGE_K.md`

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current workflow name:

`Build dc95 X1 Waker Stage J`

Trigger remains exactly:

`workflow_dispatch` only.

No ARM64 attempt is currently authorized.

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

Canonical Stage J artifact from the dedicated Actions artifact query:

- name: `Eden-dc95-X1-waker-stage-j`
- artifact ID: `9714363715`
- size: `31,423,548` bytes
- SHA-256: `27b250b40b879eeeea0a33e8ded66d3e0e229aef22d67f4027715bedf240f7b8`
- created: `2026-08-29T11:50:01Z`
- expires: `2026-09-12T11:49:58Z`
- expired: false

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

Stage I also showed slow-cadence CPU/slice grows strongly even when WaitLightEvent counts fall or remain similar. Therefore two parallel effects remain:

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

Current module map:

- rtld `0x80ede000-0x80ee2000`
- main `0x80ee2000-0x8560d000`
- subsdk0 `0x8560d000-0x85cb6000`
- sdk `0x85cb6000-0x86a8f000`

Strict primary windows:

- fast: frames `720,840` — pure swap2
- slow: frames `1200,1320,1440,1560` — pure swap3
- excluded startup/first-armed/transition/identity-transition windows.

### Stage J validity / accounting

Parent-LR frame-record reads are effectively complete:

- P0 valid slice coverage fast `99.97%`, slow `99.98%`; valid tick coverage `99.95% / 99.92%`
- P1 valid slice coverage fast `100%`, slow `99.93%`; valid tick coverage `100% / 99.88%`
- `fpZero=0`, `parentZero=0`, `badStatus=0`

Stage J `cpuTicks` equal Stage G `cpuTicks`; aggregate Stage J CPU again reconciles with Stage F to around 0.002 ms or better.

### Producer slowdown reproduces

P0 fast -> slow:

- CPU `0.998 -> 3.603 ms`, `+2.606`
- Waiting `5.398 -> 7.489`, `+2.091`
- Arbitration `5.192 -> 7.187`, `+1.995`
- runnable-unscheduled `0.306 -> 0.672`, only `+0.366`

P1:

- CPU `1.012 -> 3.922 ms`, `+2.910`
- Waiting `5.728 -> 8.993`, `+3.264`
- Arbitration `5.513 -> 8.672`, `+3.159`
- runnable-unscheduled `0.370 -> 0.592`, only `+0.221`

Mixed producer CPU + Arbitration branch is reproduced again.

### Dynamic waker remains separate

Same strict windows:

- CPU `5.908 -> 18.093 ms`
- runnable-unscheduled `0.159 -> 0.212`
- Arbitration `5.218 -> 27.092`

Host scheduler starvation remains rejected. Do not merge waker CPU/Arbitration and producer CPU/Arbitration causal ownership without direct joining evidence.

### Canonical Stage J parent triples

Stable visible family:

1. `sdk+0x158528 / sdk+0x124a8c / main+0x86a820`
2. `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54`
3. `sdk+0x158528 / sdk+0x124b40 / main+0x86be08`
4. `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc`

The new SDK parent `sdk+0x127e54` resolves exactly to:

`nn::os::LockMutex(nn::os::MutexType*)`

Thus critical chain is:

`LockMutex -> InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`.

Visible top-four triples explain about:

- P0: `61.3%` of CPU-growth delta
- P1: `54.2%`

Overflow is material but does not block dominant-family identification; do not widen histogram yet.

### Offline reverse mapping after Stage J

Exact dumped main/sdk binaries were exhausted before requesting more instrumentation.

- `main+0x86a820` lies in function around `main+0x86a4ac`; only 2 direct callers.
- `main+0x86be08` lies in function around `main+0x86bd40`; exactly 1 direct caller (`main+0x86bc98`), while the containing caller function around `main+0x86bc04` has no direct BL caller.
- `main+0x2a904cc` lies in function around `main+0x2a90478`; direct BL callers = 0, indicating dynamic/indirect owner evidence is needed rather than a guessed static owner.
- `sdk+0x127e54` = `nn::os::LockMutex`; its main import/PLT target has **6,201 direct BL callers**, so static reverse-call analysis cannot narrow this critical branch.

Stage J decision is therefore mixed A/B:

- A: visible WaitLightEvent / ReceiveLightMessageQueue parents reach concrete `main` code;
- B: critical-section parent reaches stable generic `nn::os::LockMutex`.
- C rejected: parent validity is excellent.
- D not selected: overflow exists but the dominant family is visible.

## Current causal frontier

GPU starvation
-> submitter/waker / promoted arbiter handshake
-> two selected producer threads
-> known Nintendo SDK synchronization primitives
-> Stage J identifies concrete main parent sites for WaitLightEvent/queue and LockMutex for critical section
-> slow cadence still has longer active CPU slices before blocker + longer kernel Arbitration.

The remaining question is the **dynamic caller-of-caller owner** for these selected-producer slices, especially indirect/callback entries and the extremely broad LockMutex fanout.

No optimization is justified yet.

## Immediate next action

Read:

`NEXT_ACTION_WAKER_STAGE_K.md`

The smallest remaining evidence, if the user chooses to continue, is one additional validated frame-record caller level for only the already-selected producer pair. It must not become broad stack scanning and must not hardcode observed addresses.

Stage K is not yet authorized for ARM64.

Current ARM64 authorization: **NONE**.