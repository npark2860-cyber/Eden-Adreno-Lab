# CURRENT HANDOFF — Eden Windows ARM64 / Dynarmic Exclusive Investigation

Updated: 2026-09-02 KST

## Read this first in a new tab

Primary final record:

- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_RUNTIME_FINAL.md`

Supporting records:

- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_PC_RUNTIME_STATIC_MAPPING.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260902_ARM64_EXCLUSIVE_CALLER_BUILD_VERIFIER_FIX.md`
- `DEBUG_HISTORY_20260901_ARM64_EXCLUSIVE_CALLBACK_RUNTIME.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`

The final runtime record above supersedes older statements that caller runtime was still pending.

## Repository state

Repository:
`npark2860-cyber/Eden-Adreno-Lab`

Current branch:
`exp/x1-arm64-exclusive-caller-attribution`

Branch HEAD before final documentation commits:
`b5043d94da0f827d246cd6bca594548c0b21655a`

Re-read the actual branch HEAD when opening a new tab because documentation commits follow it.

Immutable Eden baseline:
`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Immutable control branch:
`lab/dc95-arm64-baseline`

Persistent Windows ARM64 workflow:
`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Persistent trigger:
`workflow_dispatch` only.

Current Windows ARM64 authorization:
**NONE**

Hard rule: no Windows ARM64 build/rebuild/rerun without a fresh explicit user authorization. One authorization means exactly one attempt; failure does not authorize retry.

## Final authorized caller-attribution build

- workflow run: `33603651504`
- attempt: `1`
- event: `workflow_dispatch`
- build head: `27c23fcd18a5d38f068d942b6953da295dd23784`
- conclusion: **SUCCESS**
- retry/rerun: none
- one-shot dispatcher: removed

## Final runtime identity

Runtime log:
`eden_log(20260902-083624).txt`

Confirmed:

- Eden `HEAD-dc95cd09ee-HEAD`
- Windows 11 25H2 build `26220.9223`
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- CPU backend Dynarmic
- Vulkan / Qualcomm Adreno X1-85
- Adreno driver `512.863.0`
- main build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- SDK build ID `B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Durable addresses use `module+offset`, never raw ASLR runtime addresses.

## Final performance conclusion

The current investigation has established the following.

### 1. Dynarmic ARM64 exclusive handling is a real performance amplifier

Exact dc95 ARM64 Dynarmic uses callback-based exclusive handling:

- LDXR-family -> callback trampoline -> global monitor `ReadAndMark`
- STXR-family -> callback trampoline -> global monitor `DoExclusiveOperation`

The dominant traffic is 32-bit.

### 2. Slow cadence mainly increases operation count, not callback latency

Stable swap2 vs stable swap3 windows in the final runtime show approximately:

- Producer 0 exclusive write count `~3.67x`, read count `~3.59x`
- Producer 1 exclusive write count `~3.70x`, read count `~3.63x`
- per-callback latency changes only by roughly `1-7%`
- STXR failure rate rises to only about `2.25-2.31%`

Therefore there is no evidence of an STXR retry storm or several-times per-call latency collapse.

The guest executes roughly `3.5-3.7x` more exclusive synchronization operations in slow cadence, and the callback-only ARM64 implementation turns that growth into host CPU cost.

### 3. Dominant shared primitive is exactly identified

Exact SDK mapping:

- `sdk+0x131754` = first LDAXR in `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x13181c` = LDAXR in `InternalCriticalSectionImplByHorizon::Leave()`
- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

This proves synchronization-operation density growth, not lock-contention root causation.

### 4. Stage K semantic owners are closed

- `main+0x96e2a8 -> main+0x26936d0` = **gsys::SystemTask internal work/phase dispatcher**
- `main+0x86bc04 -> main+0x2ada93c` = **EventModuleSubWorker**
- `main+0x244fc20 -> main+0x2ad6b20` = **ActorAIGroupMgr::Job**

Do not reopen these identities merely for more stack depth.

### 5. SystemTask is directly tied to increased child-work synchronization

Exact main NSO mapping closed:

- `main+0x9715e0` = SystemTask child-work `+0x58` shared index/counter atomic update
- `main+0x98245c` = SystemTask child-work `+0xb8` progress/index atomic update

These rise with slow cadence and the SystemTask subtree directly reaches `nn::os::LockMutex/UnlockMutex`.

SystemTask is a proven contributor, but not proven to own all added synchronization traffic.

### 6. Caller attribution worked and found additional slow-emergent families

`[X1-XEXCLCALL]` recovered the higher-level LockMutex caller LR.

The shared dependency dispatcher caller return addresses:

- `main+0x86a530`
- `main+0x86a678`

remain relatively flat and do not explain the whole `3.5-3.7x` increase.

Strong slow-emergent caller families include:

- `main+0x7efd30`
- `main+0x7ef838`
- `main+0x7f028c`
- `main+0x7f07f0`
- `main+0x7f00a8`
- `main+0xa81e20`
- `main+0xa5a360`
- `main+0x9be4b4`
- `main+0x9be380`

These are intentionally left as unresolved secondary owner mappings because active work is moving to Windows ARM64 NCE.

Caller table saturation/dropped samples occurred in slow windows, so do not use the top-N caller table as an exhaustive percentage partition.

## Optimization judgment

There is legitimate optimization headroom in Dynarmic ARM64 exclusive handling, especially the 32-bit common path. A future Dynarmic experiment could test a safe exclusive fast path/common-case specialization or other reduction in callback/global-monitor overhead.

However, current evidence does **not** support claiming that this change alone restores 20/30 FPS. The original guest-side reason for the `3.5-3.7x` synchronization-volume increase is not fully closed.

## Windows ARM64 NCE handoff relevance

A separate Windows ARM64 NCE effort is already active outside this branch/tab.

Treat this Dynarmic investigation as an A/B baseline for NCE:

- Dynarmic ARM64 has a measured callback-only exclusive tax;
- slow cadence greatly increases guest exclusive volume;
- dominant shared primitive is Nintendo SDK critical-section / LockMutex;
- SystemTask child-work synchronization is one proven contributor;
- several other slow-emergent lock caller families exist.

If NCE bypasses or reduces the Dynarmic exclusive callback/global-monitor path, compare the same TOTK scene/cadence against this record.

## Stop condition

This Dynarmic attribution branch is now **documented and parked**.

Do not spend another ARM build merely to map every remaining caller.

Resume only when:

1. NCE A/B results need Dynarmic baseline interpretation;
2. a concrete Dynarmic exclusive fast-path prototype is ready to benchmark; or
3. one specific unresolved caller becomes necessary to answer a new question.

Otherwise prioritize the separate Windows ARM64 NCE work.
