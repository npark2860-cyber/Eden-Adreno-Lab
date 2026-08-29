# DEBUG HISTORY — 2026-08-29 Waker Stage I SDK Disassembly

## Scope

Offline analysis of the exact Nintendo SDK NSO dumped from the Stage H TOTK 1.2.1 runtime. No ARM64 build/rebuild/rerun was performed.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage H runtime source:

`eden_log(20260829-103238).txt`

Uploaded dump set:

- `main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`
- `rtld-7501ABFE55FA41CFFEB46BD619BDCBF45B9CAE3A.nso`
- `sdk-B9046C31EB5D31271BE970FE732D38DF49C6AA21.nso`
- `subsdk0-A6BB7C6FFA9673769FA74ED3D7B054191F25D29C.nso`

Current ARM64 authorization remains **NONE**.

## Binary shape / symbol recovery

The dumped `sdk` is the exact dc95 flattened decompressed NSO image produced by `PatchManager::PatchNSO()`. Its SDK image contains a usable MOD0/dynamic table and dynamic symbol table, so exact Nintendo SDK symbol names and function extents can be recovered without guessing.

Primary Stage H canonical endpoints:

- `sdk+0x158528`
- `sdk+0x158420`

Observed Stage G LR sites:

- `sdk+0x124a8c`
- `sdk+0x124b40`
- `sdk+0x127058`
- `sdk+0x13178c`

Secondary Stage D LR observation:

- `sdk+0x13f364`

## Exact SVC endpoints

### `sdk+0x158528`

Disassembly:

```asm
158524: d4000681  svc #0x34
158528: d65f03c0  ret
```

Therefore `sdk+0x158528` is the saved return PC immediately after Nintendo SDK's `svc #0x34` wrapper.

Exact dc95 maps SVC `0x34` to AddressArbiter `WaitForAddress` semantics. The historical Stage E runtime already established the observed promoted path as `WaitIfEqual`, value `1`, timeout `-1`.

### `sdk+0x158420`

Disassembly:

```asm
15841c: d4000341  svc #0x1a
158420: d65f03c0  ret
```

Therefore `sdk+0x158420` is the saved return PC immediately after Nintendo SDK's `svc #0x1a` wrapper.

Exact dc95 maps this operation to `ArbitrateLock`, which blocks through `KConditionVariable::WaitForAddress` when lock arbitration is required.

## Exact SDK caller functions

### `sdk+0x124a40`, size `0x148`

Recovered symbol:

`nn::os::WaitLightEvent(nn::os::LightEventType*)`

Both recurring Stage G LR sites `sdk+0x124a8c` and `sdk+0x124b40` are inside this same function.

First observed site:

```asm
mov x0, x19
mov w1, #2
mov w2, #1
mov x3, #-1
bl  0x158524
124a8c: ...
```

Second observed site:

```asm
mov x3, #-1
mov x0, x19
mov w1, #2
mov w2, #1
124b3c: bl 0x158524
124b40: ...
```

Thus both contexts are exact:

`nn::os::WaitLightEvent -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`.

### `sdk+0x126ea0`, size `0x270`

Recovered symbol:

`nn::os::ReceiveLightMessageQueue(unsigned long*, nn::os::LightMessageQueueType*)`

Observed LR `sdk+0x127058` follows:

```asm
mov x0, x22
mov w1, #2
mov w2, #1
mov x3, x23
bl  0x158524
127058: ...
```

The function prologue establishes `x23 = -1`, so this is exact:

`nn::os::ReceiveLightMessageQueue -> WaitForAddress(WaitIfEqual, value=1, timeout=-1)`.

### `sdk+0x131734`, size `0x98`

Recovered symbol:

`nn::os::detail::InternalCriticalSectionImplByHorizon::Enter()`

Observed LR `sdk+0x13178c` follows:

```asm
and w0, w8, #0xbfffffff
mov x1, x19
mov w2, w20
bl  0x15841c
13178c: ...
```

Thus this context is exact:

`InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`.

### `sdk+0x13f330`, size `0x5c`

Recovered symbol:

`nn::sf::hipc::SendSyncRequest(nn::svc::Handle, void*, unsigned long)`

Observed Stage D LR `sdk+0x13f364` is the convergence/return path after calls into SVC stubs at `sdk+0x158454` / `sdk+0x15845c` (`svc #0x21` / `svc #0x22`).

Important Stage D caveat: Stage D reports one `latest_pc` plus an independent LR histogram. Its `pc` and `lr0..lr3` are **not correlated PC/LR pairs**. Therefore `sdk+0x13f364` must not be claimed as the caller of the Stage D `sdk+0x158528` PC; it is only a same-window waker LR observation.

## Stage G interpretation after disassembly

Stage G records the saved guest PC/LR at scheduler switch-out and assigns the completed scheduler slice's exact `tick_diff` to that context.

The two dominant saved PCs are now known to be the `ret` immediately following blocking SVC instructions. This is consistent with a thread entering a blocking synchronization operation and switching out with its saved PC advanced past the SVC.

It does **not** mean the measured CPU time was spent executing the `ret` or the SVC wrapper. The measured CPU time covers the active guest execution slice leading up to that blocking endpoint.

## Per-slice fast -> slow change

Using Stage H fast windows `600,720,840`, slow windows `1080,1200,1320`, and the canonical 19.2 MHz Stage G tick domain:

### Producer 0

- `WaitLightEvent / 0x124a8c`: slices `3658 -> 2979`, CPU/slice `0.2280 -> 0.7420 ms` (`3.25x`)
- `InternalCriticalSection::Enter / 0x13178c`: slices `2110 -> 2754`, CPU/slice `0.0725 -> 0.4918 ms` (`6.78x`)
- `WaitLightEvent / 0x124b40`: slices `1153 -> 1246`, CPU/slice `0.1751 -> 0.7678 ms` (`4.39x`)
- `ReceiveLightMessageQueue / 0x127058`: slices `1440 -> 1438`, CPU/slice `0.1966 -> 0.2666 ms` (`1.36x`)

### Producer 1

- `WaitLightEvent / 0x124a8c`: slices `3676 -> 3024`, CPU/slice `0.2225 -> 0.6502 ms` (`2.92x`)
- `InternalCriticalSection::Enter / 0x13178c`: slices `1946 -> 2992`, CPU/slice `0.0785 -> 0.4299 ms` (`5.48x`)
- `WaitLightEvent / 0x124b40`: slices `1277 -> 1093`, CPU/slice `0.1348 -> 0.4230 ms` (`3.14x`)
- `ReceiveLightMessageQueue / 0x127058`: slices `1440 -> 1439`, CPU/slice `0.1118 -> 0.1853 ms` (`1.66x`)

The visible CPU growth is therefore not explained by simply issuing more WaitLightEvent/queue waits. WaitLightEvent counts fall or stay similar while the CPU duration of slices ending at those blockers rises strongly. Critical-section slices show both higher count and much longer per-slice CPU duration.

This remains separate from the already-measured increase in kernel Arbitration waiting duration. Current evidence supports two parallel slow-path effects:

1. longer kernel Arbitration waiting;
2. longer active guest CPU slices before reaching the synchronization blocker.

The exact active instruction owner within those longer slices is not yet identified.

## Static reverse-call exhaustion

The uploaded `main` image was also inspected before requesting deeper runtime evidence.

Recovered imports / PLT targets show:

- direct calls from `main` to `nn::os::WaitLightEvent`: **73 call sites**
- direct calls from `main` to `nn::os::ReceiveLightMessageQueue`: **4 call sites**

Therefore static reverse-call analysis cannot uniquely identify which game-side caller owns the dynamically selected producer slowdown, especially for `WaitLightEvent`.

## Frame-pointer evidence for the minimal next step

The three relevant Nintendo SDK functions preserve AArch64 frame pointer `x29` and caller LR in the standard `[x29+8]` position:

- `WaitLightEvent`
- `ReceiveLightMessageQueue`
- `InternalCriticalSectionImplByHorizon::Enter`

Exact dc95 `Svc::ThreadContext` exposes saved `fp` directly, and exact dc95 `Core::Memory::Memory` supports virtual-range validation plus `Read64`.

Therefore the smallest remaining evidence is selected-producer-only caller-of-caller sampling:

- reuse Stage F's already dynamically selected producer pair;
- at the existing Stage G switch-out point, read saved `fp` only for selected producers;
- validate `[fp+8, fp+16)` in application memory;
- read one 64-bit parent LR from `fp+8`;
- attribute the same exact scheduler `tick_diff` to `(pc, lr, parent_lr)` in a bounded fixed table;
- report only at the existing 120-frame cadence;
- no all-thread profiling, no per-switch logging, no behavior mutation.

No observed runtime PC/LR/TID is to be hardcoded.

## Decision

Stage I is complete.

The dominant Stage G contexts are concrete Nintendo SDK synchronization endpoints:

- `WaitLightEvent -> WaitForAddress`
- `ReceiveLightMessageQueue -> WaitForAddress`
- `InternalCriticalSectionImplByHorizon::Enter -> ArbitrateLock`

Offline binary analysis exhausted the available first-level caller evidence but cannot uniquely select the game-side owner because the relevant SDK primitive has many callers.

Proceed to the smallest selected-producer-only caller-depth Stage J. Do not widen the Stage G 64-slot table yet and do not optimize yet.

Current ARM64 authorization remains **NONE**.
