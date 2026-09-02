# CURRENT HANDOFF — Eden ARM64 / Adreno X1 Exclusive + Producer Attribution

Updated: 2026-09-02 KST

## Source of truth / hard rules

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:
`exp/x1-arm64-exclusive-pc-attribution`

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
Do not hardcode runtime TIDs/module bases/raw guest addresses as durable knowledge; normalize addresses to `module+offset`.
No broad/all-thread profiling.
No scheduler/priority/affinity/yield/wait/signal/GPU/QueueBuffer/cadence behavior changes by default.
Do not create Stage L merely to add stack depth.

## Read these current records first

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_NONCOMMON_OWNER_MAPPING_COMPLETE.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_READ_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_ATTRIBUTION_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`

The 2026-09-02 records supersede older handoff statements about unresolved non-common owners, old cadence-frame IDs, or the older Stage K branch.

## Current repository state

Branch:
`exp/x1-arm64-exclusive-pc-attribution`

Branch HEAD before the 2026-09-02 runtime/static documentation commits:
`ba1db576ced97264ff8be3369d0bc90eb90b3be1`

The final HEAD must be re-read from GitHub after these documentation-only commits.

No source, persistent-workflow, or baseline behavior change is part of the 2026-09-02 documentation update.

## Latest authorized Windows ARM64 build — SUCCESS

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

The temporary one-shot dispatcher was removed immediately after dispatch. Current ARM authorization is again **NONE**.

## Latest runtime source

User log:
`eden_log(20260902-043629).txt`

Confirmed runtime identity:

- Eden `HEAD-dc95cd09ee-HEAD`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- Vulkan
- Qualcomm Adreno X1-85
- main build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- sdk build ID `B9046C31EB5D31271BE970FE732D38DF49C6AA21`
- main runtime base `0x80e1f000`, size `0x472b000`
- sdk runtime base `0x85bf3000`, size `0xdd9000`

Raw bases are observational only; durable knowledge below uses `module+offset`.

Actual cadence for this run:

- report frames `480..1800`: `swap=2`
- report frames `1920..2400`: `swap=3`

Do not reuse old-run frame numbers.

## Exact local NSO dumps used for static analysis

Exact archive remained available locally during the 2026-09-02 analysis:
`sdk-B9046C31EB5D31271BE970FE732D38DF49C6AA21(1).zip`

Required exact modules:

- main: `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- sdk: `B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Dump layout already validated:

`module+X -> NSO file offset X + 0x100`

The dumped module images are already decompressed. Do not decompress them again.

## Stage K non-common owner mapping — CLOSED

All recurring non-common work-target pairs are semantically mapped:

1. `main+0x96e2a8 -> main+0x26936d0`
   = **gsys::SystemTask internal work/phase dispatcher**
2. `main+0x86bc04 -> main+0x2ada93c`
   = **EventModuleSubWorker**
3. `main+0x244fc20 -> main+0x2ad6b20`
   = **ActorAIGroupMgr::Job**

Runtime correlation keeps SystemTask and EventModuleSubWorker higher priority than ActorAIGroupMgr::Job.

Do not reopen these owner identities merely to add stack depth.

## ARM64 Dynarmic exclusive path — established implementation fact

For exact dc95 ARM64 Dynarmic, guest exclusive memory operations use callback paths rather than x64-style inline fastmem exclusive handling.

The project added observation-only selected-producer attribution for:

- STXR attempts/success/failure/time;
- LDXR `ReadAndMark` attempts/time/size distribution;
- sampled exact 32-bit LDXR guest PCs via Dynarmic IR location descriptors.

Existing exact totals and sampled PC attribution are separate.

## STXR runtime — CLOSED

Evidence excludes the initial retry-storm hypothesis:

- STXR failure rate stays low;
- no dramatic per-call STXR latency increase in slow windows;
- STXR callback by itself is only a minority of selected-producer CPU time.

Do not reopen STXR retry storm without new evidence.

## LDXR + STXR total cost — CLOSED

Prior exact runtime established:

- LDXR `ReadAndMark` is about **47%** of measured exclusive read+write time;
- combined selected-producer exclusive read+write aggregate CPU increased from roughly `3.458 ms/frame` to `4.571 ms/frame`, about **1.322x**;
- this is aggregate producer CPU, not serial frame stall;
- the principal amplification is operation-count growth, not a large single-operation latency spike;
- roughly **94-96%** of measured exclusive time is 32-bit traffic;
- representative slow windows place exclusive read+write around `10-12%` of selected-producer CPU wall.

Thus total exclusive cost is material but is not the sole slowdown owner.

## Exact 32-bit guest-PC runtime attribution — CLOSED

The latest build adds `[X1-XEXCLPC]`:

- selected Stage F producers only;
- 32-bit LDXR only;
- exact guest PC from `ImmCurrentLocationDescriptor()`;
- 1/16 sampling;
- fixed bounded table;
- top 12 sites / 120-frame report;
- existing exact `[X1-XEXCL]` totals unchanged.

## Dominant Nintendo SDK sites — EXACTLY IDENTIFIED

The dominant sampled runtime addresses normalize to:

- `sdk+0x131754`
- `sdk+0x13181c`

Exact SDK dynamic-symbol reconstruction proves:

- `sdk+0x131734` = `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x131804` = `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`

Therefore:

- `sdk+0x131754` is the `LDAXR` loop inside `Enter()`
- `sdk+0x13181c` is the `LDAXR` loop inside `Leave()`

Exact SDK exports:

- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

The static path is therefore:

`nn::os::LockMutex -> InternalCriticalSectionImplByHorizon::Enter -> sdk+0x131754`

`nn::os::UnlockMutex -> InternalCriticalSectionImplByHorizon::Leave -> sdk+0x13181c`

Slow windows contain substantially more samples at these SDK sites. This proves increased synchronization-operation density, **not** lock-contention root causation.

## gsys::SystemTask child-work synchronization — DIRECTLY CLOSED

Two main-module LDXR sites rise sharply at the swap2 -> swap3 transition:

- `main+0x9715e0`
- `main+0x98245c`

Representative sample jump:

frame 1800 / swap2:

- `main+0x9715e0`: P0 `515`, P1 `353`
- `main+0x98245c`: P0 `560`, P1 `370`

frame 1920 / swap3:

- `main+0x9715e0`: P0 `1994`, P1 `1825`
- `main+0x98245c`: P0 `1948`, P1 `1784`

SystemTask Stage K work ticks rise at the same transition:

frame 1800 / swap2:

- P0 `2,437,847`
- P1 `2,550,047`

frame 1920 / swap3:

- P0 `4,371,820`
- P1 `4,608,639`

Exact main static call chain:

`gsys::SystemTask main+0x96e2a8`
` -> main+0x96e674`
` -> main+0x970160`
` -> internal child-work processing`

`main+0x9715e0` is inside the SystemTask child-work branch reached through `main+0x9713d0`; it atomically updates a child-work `+0x58` 32-bit shared index/counter.

`main+0x98245c` is inside the branch reached through `main+0x981248`; it atomically updates a child-work `+0xb8` 32-bit progress/index counter.

Thus the slow-emergent main atomic sites are **statically proven SystemTask descendants**. SystemTask is no longer merely a high-level runtime owner label; a concrete child-work distribution/progress synchronization mechanism is identified.

## SystemTask also reaches SDK LockMutex/UnlockMutex

Within the same `main+0x970160` subtree:

- `main+0x970e28` = BL LockMutex
- `main+0x970e5c` = BL UnlockMutex
- `main+0x970e9c` = BL LockMutex
- `main+0x970ed0` = BL UnlockMutex
- `main+0x9711a8` = BL LockMutex
- `main+0x9711e8` = BL UnlockMutex

Therefore SystemTask definitely contributes to the SDK critical-section traffic.

Still unresolved: what fraction of the total dominant SDK `Enter/Leave` traffic comes from SystemTask versus EventModuleSubWorker or other callers.

## Shared dependency dispatcher — exact LockMutex address correction

Exact disassembly supersedes older off-by-four documentation.

Correct BL instruction addresses:

- `main+0x86a52c` = `nn::os::LockMutex`
- `main+0x86a5ec` = `nn::os::UnlockMutex`
- `main+0x86a674` = `nn::os::LockMutex`
- `main+0x86a7c0` = `nn::os::UnlockMutex`

Older references to `main+0x86a530` and `main+0x86a678` as the BL sites are incorrect.

Nearby shared-dispatcher LDXR PCs:

- `main+0x86a510`
- `main+0x86a558`
- `main+0x86a65c`
- `main+0x86a698`

Their sampled counts remain comparatively flat across the cadence transition. Therefore the increase in dominant SDK critical-section traffic cannot be assigned entirely to this dispatcher.

## Other observed atomic sites

- `main+0x7d3648` = **ActorAIGroupMgr::Job downstream** atomic-counter path.
- `main+0xddea3c` = secondary atomic site in `main+0xdde8e0`, direct caller `main+0x7837f0`; exact semantic owner still unresolved.
- `main+0x22468ac` / `main+0x224697c` = generic/shared function region with many reconstructed function-pointer references; do not assign a unique owner without proof.

## Current causal frontier

The strongest currently proven chain is:

GPU command starvation
-> selected producer CPU growth
-> SystemTask + EventModuleSubWorker are the high-priority producer work owners
-> slow windows contain more 32-bit exclusive operations
-> dominant shared primitive is Nintendo SDK InternalCriticalSection Enter/Leave
-> SystemTask's own child-work progress/index atomics rise sharply at cadence slowdown
-> the same SystemTask subtree directly reaches SDK LockMutex/UnlockMutex
-> **remaining frontier: partition dominant SDK critical-section traffic by external higher-level caller/owner**.

Do not simplify this to “lock contention is the root cause.” STXR failure evidence argues against a retry storm. The proven effect is increased work/synchronization-operation density.

## Immediate next action

Current ARM64 authorization:
**NONE**

Do offline design/static validation only.

Design the narrowest caller-attribution layer for dominant SDK `InternalCriticalSection::Enter` / `nn::os::LockMutex` traffic, limited to the two existing selected producers.

Target output should partition sampled SDK lock traffic into durable higher-level `module+offset` callers so a future single authorized runtime can distinguish:

- gsys::SystemTask contribution;
- EventModuleSubWorker contribution;
- ActorAIGroupMgr::Job contribution;
- other callers.

A promising exact-SDK stack-layout lead is that at the hot Enter LDAXR the external `nn::os::LockMutex` caller LR may be recoverable from guest Enter-SP + `0x38`. This must be statically proved before implementation; do not assume it from arithmetic alone.

Do not build ARM64 until fresh authorization is explicitly given.

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
