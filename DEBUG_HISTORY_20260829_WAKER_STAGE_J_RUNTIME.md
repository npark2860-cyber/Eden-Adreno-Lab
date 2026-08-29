# DEBUG HISTORY — 2026-08-29 Waker Stage J Runtime

## Scope

Runtime validation of Stage J selected-producer one-level parent-LR attribution on the exact Stage J ARM64 build.

Runtime log:

`eden_log(20260829-115839).txt`

SHA-256:

`d9045854c80b57eae904c62753b46713fa374df3ada385c8fc2094e3b256e952`

Environment:

- TOTK `1.2.1`
- Windows 11 25H2 build `26220.9223`
- Qualcomm Adreno X1-85
- Vulkan driver `512.863.0`
- Vulkan `1.3.295`
- behavior-changing A/B controls off
- `dump_nso=true`

Fixed Eden source remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current ARM64 authorization: **NONE**.

## Stage H module truth in this run

- `rtld`: `0x80ede000-0x80ee2000`
- `main`: `0x80ee2000-0x8560d000`
- `subsdk0`: `0x8560d000-0x85cb6000`
- `sdk`: `0x85cb6000-0x86a8f000`

The raw Stage G/J address family moved again with ASLR while canonical module offsets remained stable.

## Cadence selection

QueueBuffer 120-frame windows:

- 120: 110 swap2 / 10 swap3 — startup mixed
- 240: 119 swap2 / 1 swap3 — producers not armed
- 360: 90 swap2 / 30 swap3 — mixed
- 480: 120 swap2 — first armed window; Stage G missing-start / Stage F tracking transition, excluded
- 600: 113 swap2 / 7 swap3 — near-clean, not primary
- 720: 120 swap2 — strict clean
- 840: 120 swap2 — strict clean
- 960: 78 swap2 / 42 swap3 — transition, excluded
- 1080: 120 swap3 — cadence pure but identity transition inherited from prior swap, excluded from strict comparison
- 1200: 120 swap3 — strict clean
- 1320: 120 swap3 — strict clean
- 1440: 120 swap3 — strict clean
- 1560: 120 swap3 — strict clean

Primary comparison:

- fast: frames `720,840`
- slow: frames `1200,1320,1440,1560`

## Stage J parent-read validity

The saved-x29 standard frame-record assumption is strongly validated.

Producer 0:

- fast: 6034 / 6036 valid slices (`99.97%`), valid tick coverage `99.95%`
- slow: 14890 / 14893 valid slices (`99.98%`), valid tick coverage `99.92%`
- `fpZero=0`, `parentZero=0`
- only 2 fp-bad fast; 2 fp-bad + 1 range-bad slow

Producer 1:

- fast: 6445 / 6445 valid slices (`100%`), valid tick coverage `100%`
- slow: 15427 / 15438 valid slices (`99.93%`), valid tick coverage `99.88%`
- `fpZero=0`, `parentZero=0`
- only 10 fp-bad + 1 range-bad slow

`badStatus=0` throughout strict windows.

Stage J `cpuTicks` equal Stage G `cpuTicks` per window.

Aggregate Stage J CPU versus Stage F CPU:

| producer | J fast | F fast | J slow | F slow |
|---|---:|---:|---:|---:|
| 0 | 0.998294 ms | 0.997715 ms | 3.604694 ms | 3.603302 ms |
| 1 | 1.011686 ms | 1.012226 ms | 3.922328 ms | 3.922171 ms |

Instrumentation accounting remains essentially exact.

## Stage F mixed branch reproduction

Interval-weighted strict fast -> slow:

### Producer 0

- inter-signal `6.498 -> 11.393 ms`
- Waiting `5.398 -> 7.489`, `+2.091`
- residual `1.100 -> 3.903`, `+2.804`
- CPU `0.998 -> 3.603`, `+2.606`
- runnable-unscheduled `0.306 -> 0.672`, `+0.366`
- Arbitration `5.192 -> 7.187`, `+1.995`

### Producer 1

- inter-signal `6.880 -> 13.104 ms`
- Waiting `5.728 -> 8.993`, `+3.264`
- residual `1.152 -> 4.112`, `+2.959`
- CPU `1.012 -> 3.922`, `+2.910`
- runnable-unscheduled `0.370 -> 0.592`, `+0.221`
- Arbitration `5.513 -> 8.672`, `+3.159`

The producer CPU-growth and producer Arbitration-growth branches both reproduce. Runnable-unscheduled remains much smaller and cannot explain the slowdown.

## Dynamic-waker reproduction

Same strict windows, interval-weighted:

- inter-signal `33.888 -> 52.010 ms`
- Waiting `27.866 -> 33.723`
- residual `6.022 -> 18.287`
- CPU `5.908 -> 18.093`
- runnable-unscheduled `0.159 -> 0.212`
- Arbitration `5.218 -> 27.092`
- ConditionVar `21.548 -> 5.485`

Host scheduler starvation remains rejected.

Do not merge dynamic-waker CPU/Arbitration with producer CPU/Arbitration ownership merely because they share SDK synchronization families.

## Canonical Stage J parent triples

Four recurring visible triples are stable across both producers and both cadence regimes.

### 1. WaitLightEvent path A

`sdk+0x158528 / sdk+0x124a8c / main+0x86a820`

Stage I semantics:

`nn::os::WaitLightEvent -> WaitForAddress(WaitIfEqual, 1, -1)`

Stage J now places its parent LR in `main`.

### 2. Critical-section path

`sdk+0x158420 / sdk+0x13178c / sdk+0x127e54`

Exact SDK symbol mapping of the new parent:

`sdk+0x127e54` is inside `nn::os::LockMutex(nn::os::MutexType*)` immediately after its call into `InternalCriticalSectionImplByHorizon::Enter()`.

Canonical chain:

`nn::os::LockMutex -> InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`

The parent remains a generic SDK wrapper.

### 3. WaitLightEvent path B

`sdk+0x158528 / sdk+0x124b40 / main+0x86be08`

This is the second observed branch inside `nn::os::WaitLightEvent`; Stage J places its parent LR in `main`.

### 4. ReceiveLightMessageQueue path

`sdk+0x158528 / sdk+0x127058 / main+0x2a904cc`

Stage I semantics:

`nn::os::ReceiveLightMessageQueue -> WaitForAddress(WaitIfEqual, 1, -1)`

Stage J places its parent LR in `main`.

## Visible CPU-growth contribution

Per interval, strict fast -> slow.

### Producer 0

- critical section / `sdk+0x127e54`: `0.1010 -> 0.7345 ms`, delta `+0.6334`
- WaitLightEvent / `main+0x86a820`: `0.4790 -> 0.9936`, delta `+0.5146`
- WaitLightEvent / `main+0x86be08`: `0.0721 -> 0.4660`, delta `+0.3939`
- Receive queue / `main+0x2a904cc`: `0.1404 -> 0.1944`, delta `+0.0539`
- visible top-four delta: `+1.5959 ms/interval`
- Stage F CPU delta: `+2.6056`
- visible top four explain about `61.3%` of CPU growth

### Producer 1

- WaitLightEvent / `main+0x86a820`: `0.4542 -> 1.1365 ms`, delta `+0.6823`
- critical section / `sdk+0x127e54`: `0.1026 -> 0.7447`, delta `+0.6421`
- WaitLightEvent / `main+0x86be08`: `0.0708 -> 0.2288`, delta `+0.1580`
- Receive queue / `main+0x2a904cc`: `0.1240 -> 0.2194`, delta `+0.0954`
- visible top-four delta: `+1.5778 ms/interval`
- Stage F CPU delta: `+2.9099`
- visible top four explain about `54.2%` of CPU growth

Overflow remains material:

- P0 overflow `0.1293 -> 1.0225 ms/interval`, delta `+0.8933`
- P1 overflow `0.1837 -> 1.4516`, delta `+1.2679`

However, the dominant caller families are now explicit. Do not widen Stage G/J tables yet.

## Per-slice result remains the same causal shape

Representative CPU/slice fast -> slow:

Producer 0:

- critical section / LockMutex parent `0.099 -> 0.421 ms`
- WaitLightEvent / `main+0x86a820` `0.281 -> 0.594`
- WaitLightEvent / `main+0x86be08` `0.376 -> 2.124`
- Receive queue / `main+0x2a904cc` `0.183 -> 0.222`

Producer 1:

- WaitLightEvent / `main+0x86a820` `0.243 -> 0.559 ms`
- critical section / LockMutex parent `0.090 -> 0.364`
- WaitLightEvent / `main+0x86be08` `0.349 -> 0.907`
- Receive queue / `main+0x2a904cc` `0.153 -> 0.218`

The active guest CPU slice leading to the blocking synchronization endpoint becomes much longer in slow cadence. This remains distinct from the separate growth in kernel Arbitration waiting.

## Offline mapping of the new parent sites

The exact previously dumped TOTK `main` and `sdk` images were reused; no new runtime/build was required.

### `main+0x86a820`

The return site follows a call through the `main` PLT/import for `nn::os::WaitLightEvent`.

Enclosing stripped main function begins at approximately:

`main+0x86a4ac`

Direct BL callers of `main+0x86a4ac`:

- `main+0x7edb88`
- `main+0x86a48c`

Only two direct call sites.

The call at `main+0x86a48c` is in a small local wrapper beginning around `main+0x86a464`; that wrapper itself has no direct BL caller and is likely reached indirectly.

The other call is inside a function beginning around `main+0x7edaf8`; that function has 14 direct BL callers.

### `main+0x86be08`

The return site follows the WaitLightEvent import call.

Enclosing stripped function begins around:

`main+0x86bd40`

Direct BL callers of `main+0x86bd40`:

- exactly one: `main+0x86bc98`

That call lies in a function beginning around `main+0x86bc04`. No direct BL caller to `main+0x86bc04` was found, indicating an indirect/callback-style entry is plausible. Do not assign a semantic owner without runtime evidence.

### `main+0x2a904cc`

The return site follows the import call used for `nn::os::ReceiveLightMessageQueue`.

Enclosing stripped function begins around:

`main+0x2a90478`

Direct BL callers of `main+0x2a90478`: **0**.

This is consistent with an indirect/function-pointer/callback entry, but the exact owner is not yet proven.

### `sdk+0x127e54` / LockMutex

The exact SDK symbol is:

`nn::os::LockMutex(nn::os::MutexType*)`

The corresponding main import/PLT target has **6,201 direct BL call sites** in the game text. Static reverse-call analysis therefore cannot narrow this branch further.

## Stage J decision

Stage J yields a mixed decision-map A/B result.

### Case A — achieved for visible WaitLightEvent / queue families

Parent LR reaches concrete `main` code:

- `main+0x86a820`
- `main+0x86be08`
- `main+0x2a904cc`

Static reverse mapping substantially narrows two of these families, but indirect entries remain and runtime ownership is not fully unique.

### Case B — achieved for critical-section family

Parent LR reaches one stable generic SDK wrapper:

`nn::os::LockMutex`

Static reverse-call fanout is enormous and cannot identify the selected-producer game owner.

### Case C — rejected

Parent LR validity is effectively complete; frame-pointer reading is not the problem.

### Case D — not selected

Overflow is material, but a dominant stable family is already identifiable. Histogram widening is not yet justified.

## Conclusion

Stage J successfully moved the producer CPU-growth frontier one caller level above the known synchronization endpoints.

The remaining problem is not identifying the synchronization primitive; it is identifying the dynamic game-side caller chain that leads the selected producer into those primitives while the slow-cadence CPU slice lengthens.

No optimization is justified yet.

A further caller-depth stage, if pursued, should remain selected-producer-only and minimal. Current ARM64 authorization remains **NONE**.