# DEBUG HISTORY — ARM64 Exclusive Caller Runtime Final

Date: 2026-09-02 KST

## Purpose

This document closes the current Eden Windows ARM64 / Snapdragon X Elite / Adreno X1-85 Dynarmic exclusive-attribution investigation and preserves the results for reuse from another tab/project, especially the separate Windows ARM64 NCE work.

Repository: `npark2860-cyber/Eden-Adreno-Lab`

Branch: `exp/x1-arm64-exclusive-caller-attribution`

Immutable Eden baseline: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current Windows ARM64 authorization after the run: **NONE**.

No additional ARM build is authorized by this document.

## Final caller-attribution ARM build

Authorized persistent workflow run:

- run: `33603651504`
- workflow: `Build dc95 X1 Waker Stage K`
- event: `workflow_dispatch`
- run attempt: `1`
- build head: `27c23fcd18a5d38f068d942b6953da295dd23784`
- conclusion: **SUCCESS**
- retry/rerun: none

The one-shot dispatcher was removed after the single persistent run was created.

The persistent workflow remained `workflow_dispatch` only.

## Final runtime source

User runtime log:

`eden_log(20260902-083624).txt`

Confirmed runtime identity:

- Eden `HEAD-dc95cd09ee-HEAD`
- Windows 11 25H2 build `26220.9223`
- CPU backend: Dynarmic
- TOTK `1.2.1`
- title ID `0100F2C0115B6000`
- Vulkan
- Qualcomm Adreno X1-85
- Adreno driver `512.863.0`
- Vulkan `1.3.295`
- main build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- SDK build ID `B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Runtime module bases for this run:

- `main = 0x80e16000 .. 0x85541000`
- `sdk  = 0x85bea000 .. 0x869c3000`

Durable documentation must continue using `module+offset`, not these ASLR runtime addresses.

## Cadence windows used for comparison

The same log shows:

- report frames `480, 600, 720, 840`: stable `swap=2`
- report frame `960`: first `swap=3` transition window; excluded from stable comparison
- report frames `1080, 1200, 1320, 1440`: stable `swap=3`

Do not reuse these frame numbers for another run without re-reading that run's cadence records.

## Final exclusive-cost conclusion

Across the stable windows above, the main change is **exclusive operation count**, not single-callback latency.

Producer 0:

- write attempts: about `3.67x` higher in stable swap3
- read attempts: about `3.59x` higher
- write callback average: only about `1.067x` higher
- read callback average: only about `1.062x` higher
- STXR failure rate: about `0.91% -> 2.25%`

Producer 1:

- write attempts: about `3.70x` higher
- read attempts: about `3.63x` higher
- write callback average: about `1.012x` higher
- read callback average: about `1.036x` higher
- STXR failure rate: about `0.97% -> 2.31%`

Depending on slightly different clean-window selection, the same result is approximately `3.5-3.7x` operation-count amplification.

Therefore the final interpretation is:

1. there is no STXR retry storm;
2. there is no several-times single-callback latency explosion;
3. slow cadence causes the guest to execute roughly 3.5-3.7 times more exclusive operations on the selected producers;
4. Dynarmic ARM64 callback-only exclusive handling converts that guest synchronization growth into a large host CPU tax.

The Dynarmic ARM64 exclusive path is therefore a **performance amplifier**, not proven to be the original game-side cause of the extra synchronization work.

## Exact SDK hot primitive — CLOSED

Exact SDK static mapping remains:

- `sdk+0x131754` = first `LDAXR` in `nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`
- `sdk+0x13181c` = `LDAXR` in `nn::os::detail::InternalCriticalSectionImplByHorizon::Leave()`
- `sdk+0x127e20` = `nn::os::LockMutex`
- `sdk+0x127ee0` = `nn::os::UnlockMutex`

Thus the dominant shared 32-bit exclusive sites are real Nintendo SDK critical-section operations.

This proves synchronization-operation density growth. It does **not** by itself prove lock contention as the root cause.

## Caller attribution result

`[X1-XEXCLCALL]` successfully recovered the higher-level `nn::os::LockMutex` caller LR by sampling the exact SDK Enter LDAXR and reading the statically proven `guest SP + 0x38` slot.

The two recurring shared-dependency caller return addresses are:

- `main+0x86a530`
- `main+0x86a678`

These are the return addresses immediately after the exact BL instructions:

- `main+0x86a52c` = `BL nn::os::LockMutex`
- `main+0x86a674` = `BL nn::os::LockMutex`

This runtime result confirms the previously mapped shared dependency dispatcher really contributes SDK critical-section traffic on both selected producers.

However, these two callers stay broadly flat between stable swap2 and swap3 and therefore **do not explain the total 3.5-3.7x exclusive-operation increase**.

Representative aggregate caller samples:

Producer 0, stable swap2 -> stable swap3:

- `main+0x86a678`: `436 -> 409`
- `main+0x86a530`: `375 -> 401`
- `main+0x7efd30`: `22 -> 182` (`8.27x`)
- `main+0x7ef838`: `17 -> 174` (`10.24x`)
- `main+0x7f028c`: `11 -> 168` (`15.27x`)
- `main+0x7f07f0`: `20 -> 167` (`8.35x`)
- `main+0x7f00a8`: `26 -> 164` (`6.31x`)
- `main+0xa81e20`: `0 -> 384` in the selected top-N records
- `main+0xa5a360`: `0 -> 102`
- `main+0x9be4b4`: `0 -> 56`

Producer 1:

- `main+0x86a678`: `373 -> 377`
- `main+0x86a530`: `371 -> 345`
- `main+0x7efd30`: `17 -> 127` (`7.47x`)
- `main+0x7f07f0`: `9 -> 116` (`12.89x`)
- `main+0x7f00a8`: `13 -> 112` (`8.62x`)
- `main+0x7f028c`: `12 -> 110` (`9.17x`)
- `main+0x7ef838`: `25 -> 89` (`3.56x`)
- `main+0x9be4b4`: `0 -> 88`
- `main+0x9be380`: `0 -> 84`
- `main+0xa5a360`: `0 -> 28`

These addresses are the main unresolved slow-emergent caller families if the Dynarmic investigation is ever resumed.

### Important caller-profiler limitation

The caller table reached `occupied=255/256` or `256/256` in some slow windows and recorded dropped samples. Therefore the caller top-N data is sufficient to identify real slow-emergent families, but **must not be used as an exhaustive percentage partition of all lock traffic**.

Do not claim that one listed family owns all additional SDK lock traffic.

## gsys::SystemTask connection — CLOSED

Earlier exact NSO mapping remains valid:

- `main+0x96e2a8 -> main+0x26936d0` = `gsys::SystemTask` internal work/phase dispatcher
- slow-emergent `main+0x9715e0` = SystemTask child-work `+0x58` shared index/counter atomic update
- slow-emergent `main+0x98245c` = SystemTask child-work `+0xb8` progress/index atomic update

The SystemTask subtree also directly calls `nn::os::LockMutex/UnlockMutex`.

Therefore SystemTask is genuinely part of the synchronization growth picture, but caller-attribution runtime does not support assigning all added SDK lock traffic to SystemTask.

Other previously closed owners remain:

- `main+0x86bc04 -> main+0x2ada93c` = EventModuleSubWorker
- `main+0x244fc20 -> main+0x2ad6b20` = ActorAIGroupMgr::Job

## Optimization implication

There is real optimization headroom in Dynarmic ARM64 exclusive handling because exact dc95 ARM64 remains callback based:

- LDXR-family -> callback trampoline -> global monitor `ReadAndMark`
- STXR-family -> callback trampoline -> global monitor `DoExclusiveOperation`

The measurements show this callback path is material, but its cost is primarily amplified by **guest operation count growth**, not a catastrophic per-call regression.

If Dynarmic optimization is revisited, the highest-value prototype is a safe 32-bit ARM64 exclusive fast path/common-case specialization or equivalent reduction in callback/global-monitor overhead.

Do not promise that this alone restores 20/30 FPS; current data does not support that claim.

## Relation to separate Windows ARM64 NCE work

A separate Windows ARM64 NCE effort has already started outside this branch/tab.

For that work, this investigation should be treated as a diagnostic baseline:

- Dynarmic ARM64 has a measured callback-only exclusive tax;
- slow cadence can drive guest exclusive volume to roughly 3.5-3.7x the stable swap2 level;
- dominant shared primitive is Nintendo SDK `InternalCriticalSection` / `LockMutex`;
- SystemTask child-work synchronization is one proven contributor;
- multiple other slow-emergent lock caller families remain unresolved.

If NCE bypasses or materially reduces the Dynarmic exclusive callback/global-monitor path, compare the same TOTK scene/cadence against this baseline. A meaningful FPS/cadence improvement together with disappearance/reduction of this host-side exclusive tax would directly validate NCE's value on Windows ARM64.

## Decision / stop condition

The current Dynarmic attribution branch is considered **documented and parked**.

Do not spend another ARM build merely to name every remaining caller.

Resume this branch only if one of the following becomes useful:

1. NCE A/B results require a Dynarmic baseline explanation;
2. a concrete Dynarmic 32-bit exclusive fast-path prototype is ready for measurement;
3. new evidence specifically requires mapping one unresolved slow-emergent caller family.

Otherwise move active performance work to the separate Windows ARM64 NCE track.

Current ARM64 authorization: **NONE**.
