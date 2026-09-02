# CURRENT HANDOFF — Eden ARM64 / Adreno X1 Exclusive Caller Attribution

Updated: 2026-09-02 KST

## Source of truth / hard rules

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:
`exp/x1-arm64-exclusive-caller-attribution`

Immutable Eden baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Immutable control branch:
`lab/dc95-arm64-baseline`

Persistent Windows ARM64 workflow:
`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:
`Build dc95 X1 Waker Stage K`

Persistent trigger:
`workflow_dispatch` only.

### Windows ARM64 authorization — ABSOLUTE

- no Windows ARM64 build/rebuild/rerun without fresh explicit user authorization;
- one authorization = exactly one attempt;
- failure does not authorize retry;
- no automatic retry;
- current ARM64 authorization: **NONE**.

Ubuntu/static validation and offline NSO analysis do not consume ARM authorization.

Never change the exact baseline without explicit approval.
Do not hardcode runtime TIDs or raw ASLR module bases as durable knowledge; use `module+offset`.
No broad/all-thread profiling.
No scheduler/priority/affinity/yield/wait/signal/GPU/QueueBuffer/cadence behavior changes by default.
Do not create Stage L merely to add stack depth.

## Read these current records first

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_IMPLEMENTED.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`

These 2026-09-02 records supersede older handoff statements about unresolved Stage K owners, old cadence frame IDs, and the previous exclusive-PC branch.

## Current repository state

Branch:
`exp/x1-arm64-exclusive-caller-attribution`

Base before caller implementation:
`9e60061e6821ea0e4293dd04095c4707bcb1da24`

Caller implementation/static validation was completed on this branch. Re-read actual branch HEAD at the start of the next tab because documentation commits follow the source commits.

Final caller implementation diff before documentation contains exactly:

- `src/core/x1_arm64_exclusive_caller_profiler.h`
- `tools/adreno_lab/analyze_x1_arm64_exclusive_caller_attribution.py`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_caller_attribution.py`
- minimal caller-chain extension in `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`

No temporary validator workflow remains.
No persistent ARM workflow diff remains.
No baseline change occurred.

## Latest authorized Windows ARM64 runtime build — SUCCESS

This is still the exclusive-PC runtime build; no caller build has been authorized yet.

- workflow run: `33532663563`
- job: `99939361617`
- attempt: `1`
- event: `workflow_dispatch`
- workflow head: `cf592457de3b657549c3e11e8dd41d03a5a47965`
- result: **SUCCESS**
- retry/rerun: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9811512280`
- size: `31,447,663` bytes
- SHA-256: `d36a856e8e9905e185bebfe0db8f2aeb2be6e78d76733cf332a0d8c7773b8505`

The one-shot dispatcher was removed after dispatch. Current ARM authorization is **NONE**.

## Exact runtime / module identity

Latest PC-attribution runtime log:
`eden_log(20260902-043629).txt`

Confirmed:

- Eden `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- Vulkan
- Qualcomm Adreno X1-85
- main build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- SDK build ID `B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Exact dumped main and SDK NSOs were used for static disassembly. Dump mapping remains:

`module+X -> NSO file offset X + 0x100`

The dumped module images are already decompressed.

Actual cadence for the latest PC runtime:

- report frames `480..1800`: `swap=2`
- report frames `1920..2400`: `swap=3`

Never reuse cadence frame numbers blindly across runs.

## Stage K semantic owners — CLOSED

All recurring non-common work-target pairs are mapped:

1. `main+0x96e2a8 -> main+0x26936d0`
   = **gsys::SystemTask internal work/phase dispatcher**
2. `main+0x86bc04 -> main+0x2ada93c`
   = **EventModuleSubWorker**
3. `main+0x244fc20 -> main+0x2ad6b20`
   = **ActorAIGroupMgr::Job**

Do not reopen these identities merely to add stack depth.

## ARM64 Dynarmic exclusive implementation — CLOSED FACT

Exact dc95 ARM64 Dynarmic exclusive reads/writes are callback based rather than x64-style inline fastmem-exclusive handling.

Observed path includes:

- LDXR-family -> ARM64 callback trampoline -> global monitor `ReadAndMark`
- STXR-family -> ARM64 callback trampoline -> global monitor `DoExclusiveOperation` -> Eden exclusive memory callback / host atomic CAS

Current upstream ARM64 Dynarmic also retains callback-only exclusive handling.

## Exclusive total-cost runtime — CLOSED

STXR-only and LDXR+STXR runtime established:

- no STXR retry storm;
- no dramatic STXR single-call latency explosion;
- LDXR `ReadAndMark` accounts for roughly 47% of measured exclusive read+write time;
- selected-producer combined exclusive aggregate CPU increases roughly `1.32x` in slow windows;
- principal amplification is operation-count growth, not per-operation latency growth;
- roughly 94-96% of measured exclusive time is 32-bit traffic;
- representative slow windows place exclusive read+write near 10-12% of selected-producer CPU wall.

Exclusive handling is a material shared cost but not by itself the sole slowdown owner.

## Exact 32-bit LDXR PC attribution — CLOSED

`[X1-XEXCLPC]` runtime used:

- two selected Stage F producers only;
- 32-bit LDXR only;
- exact guest PC from Dynarmic location descriptor;
- 1/16 sampling;
- bounded top-N report every 120 frames;
- exact `[X1-XEXCL]` totals kept separate.

### Dominant SDK sites

Exact static identities:

- `sdk+0x131754` = first `LDAXR` inside `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x13181c` = `LDAXR` inside `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`
- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

Thus the largest shared 32-bit exclusive sites are real Nintendo SDK critical-section operations.

This proves synchronization-operation density growth, not lock-contention root causation.

## gsys::SystemTask child-work synchronization — DIRECTLY CONNECTED

Slow-emergent main-module LDXR sites:

- `main+0x9715e0`
- `main+0x98245c`

Exact static chain:

`gsys::SystemTask main+0x96e2a8`
` -> main+0x96e674`
` -> main+0x970160`
` -> child-work processing`

- `main+0x9715e0` atomically updates child-work `+0x58` shared index/counter.
- `main+0x98245c` atomically updates child-work `+0xb8` shared progress/index counter.

These sites rise sharply at the same swap2 -> swap3 transition as SystemTask Stage K work ticks.

The same SystemTask subtree directly calls `nn::os::LockMutex/UnlockMutex`, so SystemTask definitely contributes to dominant SDK critical-section traffic.

Do not claim it owns all SDK traffic until caller partition is observed.

## Shared dependency dispatcher correction

Correct exact BL instruction addresses:

- `main+0x86a52c` = LockMutex
- `main+0x86a5ec` = UnlockMutex
- `main+0x86a674` = LockMutex
- `main+0x86a7c0` = UnlockMutex

Older `main+0x86a530` / `main+0x86a678` BL labels were off by four bytes.

Nearby local LDXR sites are comparatively flatter than dominant SDK Enter/Leave growth, so added SDK traffic is not all attributable to this shared dispatcher.

## Exclusive caller attribution — IMPLEMENTED / STATICALLY VALIDATED

New runtime prefix:
`[X1-XEXCLCALL]`

### Exact stack proof

For exact SDK build `B9046C31...`:

- `nn::os::LockMutex` saves the higher-level external LR at `LockMutex-SP + 0x8`.
- the path into `InternalCriticalSectionImplByHorizon::Enter()` preserves that LR.
- `Enter()` lowers SP by `0x30` before the first LDAXR at `sdk+0x131754`.

Therefore, exactly at that target LDAXR:

`guest SP + 0x38 = higher-level nn::os::LockMutex caller LR`

### Guest-SP transport

No IR opcode or x64 backend modification was required.

Exact dc95 ARM64 maintains guest SP in `A64JitState::sp`. The caller layer adds one diagnostic load of this field into callback argument X3 before the exclusive-read relocation. The existing ARM64 exclusive trampoline preserves the argument while replacing X0 with UserConfig and tail-branching to the callback function.

### Sampling scope

- existing two selected producers only;
- only 32-bit exclusive read;
- only exact target `sdk+0x131754`;
- independent `1/64` sample;
- only after target + sample gates, one guarded `Read64(SP+0x38)`;
- stack range checked first;
- 256 fixed caller slots / producer;
- probe limit 8;
- top 12 caller LRs / 120 frames;
- invalid-stack and dropped-sample accounting;
- runtime SDK range registered dynamically;
- existing exact totals and 1/16 PC samples unchanged.

### Exact-dc95 Ubuntu validation

Temporary validator run history:

- `33595304786`: fixture failed before caller transform because synthetic Stage F lacked the accessor normally inserted by Stage G.
- `33595436819`: temporary workflow YAML parse failure; no job executed.
- `33595564876`: **SUCCESS**.

Successful validation confirmed unchanged `ReadAndMark` / `DoExclusiveOperation` shape, one guest-SP load, one target test, one guarded stack read path, one SDK range registration, Python syntax, and no behavior-changing scheduling/GPU/cadence tokens.

Temporary validator workflow was deleted after success.

## Immediate next action

Current ARM64 authorization:
**NONE**

Stop here until a fresh explicit authorization is provided.

If authorized, perform exactly one Windows ARM64 build/run attempt from:

`exp/x1-arm64-exclusive-caller-attribution`

Expected runtime evidence:

- `[X1-XEXCLCALL]`
- `[X1-XEXCLPC]`
- `[X1-XEXCL]`
- `[X1-WAKERH]`
- Stage K work records
- cadence records from the same run

Use `analyze_x1_arm64_exclusive_caller_attribution.py` with explicit fast/slow frame lists from that run.

Normalize dominant caller LRs to `module+offset`, statically map them with the exact main NSO, then partition SDK Enter/LockMutex traffic among:

- gsys::SystemTask
- EventModuleSubWorker
- ActorAIGroupMgr::Job
- other callers

If one family dominates slow-added lock traffic, descend only into that family. If traffic is broad across unrelated owners, treat callback/global-monitor exclusive handling as a shared ARM64 amplification tax rather than inventing one game-side owner.

Do not auto-build.
Do not rerun on failure.
Do not create Stage L.
Do not implement behavior-changing optimization before this caller partition is known.

## Closed historical findings — do not reopen without new evidence

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplicates; blind dedupe rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path = adaptive mapped fast stream/re-stream.
- classic-cache fallback did not break gameplay ceiling.
- QueueBuffer swap2 ~= nominal 30 FPS opportunity; swap3 ~= nominal 20 FPS; VI ~= 60 Hz.
- raw3->effective2 clamp did not improve upstream frame generation.
- DFPS not root.
- BufferQueue free-slot/backpressure not primary owner.
- GPU worker predominantly waits for command supply.
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint are not the missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation closed as primary owner for selected-producer slowdowns.
