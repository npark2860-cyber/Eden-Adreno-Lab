# DEBUG HISTORY — Waker Stage K Offline Semantic Mapping

Date: 2026-08-31 KST

## Scope

This record closes the offline/static part of Stage K grandparent attribution against the exact dumped TOTK 1.2.1 main NSO.

Fixed Eden baseline remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

No Windows ARM64 build, rebuild, rerun, or new runtime attempt was performed for this work. Current ARM64 authorization remains **NONE**. No Stage L was created.

All addresses below are ASLR-normalized `module+offset`. Raw runtime VAs are not durable knowledge.

## Binary provenance

Exact dumped main image:

`main-9B4E43650501A4D4489B4BBFDB740F26AF3CF85.nso`

The dump is an NSO header followed by the already-decompressed module memory image. Static analysis therefore used the dumped memory image and applied the image's `R_AARCH64_RELATIVE` relocations for vtable/pointer reconstruction. The original compressed-segment metadata in the NSO header was not treated as a second compression layer.

## Exact Stage K grandparent mapping

| Captured grandparent LR | Exact enclosing function | LR-producing instruction | Classification |
|---|---|---|---|
| `main+0x86a490` | `main+0x86a464` | `main+0x86a48c: BL main+0x86a4ac` | concrete shared dependency-worker callback into job dispatcher |
| `main+0x86bc9c` | `main+0x86bc04` | `main+0x86bc98: BL main+0x86bd40` | `EventModuleSubWorker` virtual coordination/execution path |
| `main+0x2a2d958` | `main+0x2a2d8a0` | `main+0x2a2d954: BLR x8` | indirect virtual thread/message-dispatch frontier |
| `main+0x86a530` | `main+0x86a4ac` | `main+0x86a52c: BL main+0x2b17270` | shared dispatcher LockMutex site A |
| `main+0x86a678` | `main+0x86a4ac` | `main+0x86a674: BL main+0x2b17270` | shared dispatcher LockMutex site B |

Exact imported targets used by this mapping include:

- `main+0x2b17270` = `nn::os::LockMutex`
- `main+0x2b17280` = `nn::os::UnlockMutex`
- `main+0x2b17b50` = `nn::os::WaitLightEvent`
- `main+0x2b17c50` = `nn::os::SignalLightEvent`
- `main+0x2b183d0` = `nn::os::ReceiveLightMessageQueue`

## Shared dependency-worker branch

`main+0x86a464` is a concrete virtual callback reached from the common light-message worker loop `main+0x2a90478`.

For message value `1`, `main+0x86a464` calls `main+0x86a4ac` and then signals its light event. The same concrete worker implementation is reused by worker pools named:

- `ModuleSystemWorker`
- `NavMeshDepWorker`
- `NavMeshCAStepDepWorker`
- `phive::DepWorker`

Therefore `main+0x86a464` is not a single gameplay subsystem owner. It is shared dependency-worker infrastructure.

`main+0x86a4ac` is the synchronization-heavy dispatcher. Relevant exact sites include:

- `main+0x86a52c` -> `nn::os::LockMutex`
- `main+0x86a674` -> the same `nn::os::LockMutex` import
- `main+0x86a81c` -> `nn::os::WaitLightEvent`
- `main+0x86a988` -> queued work-object virtual execution

Thus Stage K grandparent families `main+0x86a490`, `main+0x86a530`, and `main+0x86a678` converge on one shared dependency-worker scheduler/dispatcher rather than three independent owners.

## EventModuleSubWorker branch

The vtable/constructor/registration path for `main+0x86bc04` resolves to the concrete subsystem name:

`EventModuleSubWorker`

The exact path is:

`EventModuleSubWorker -> main+0x86bc04 -> main+0x86bd40 -> selected-object virtual operation -> nn::os::WaitLightEvent`

This gives a concrete semantic owner to Stage K grandparent `main+0x86bc9c`.

## Generic message-loop branch

`main+0x2a2d954` is exactly `BLR x8`. The runtime path reaches common virtual method `main+0x2a90478`, which receives from a light message queue and dispatches a concrete callback through the next virtual slot.

Therefore `main+0x2a2d958` is a generic indirect thread/message-dispatch frontier, not final game work.

## `main+0x86a988` work-object pointer flow

The scheduler insertion routine is `main+0x7eea44`.

The descriptor work-object pointer is copied into scheduler node `[0]`, later popped by `main+0x86a4ac`, and invoked at `main+0x86a988` through work-object `vtable+0x10`.

For ModuleSystem components, every `vtable+0x10` resolves to common shim:

`main+0x2af1230`

That shim performs gating and tail-dispatches to the component-specific method at:

`vtable+0x60`

So the concrete ModuleSystem execution path is:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

## Complete ModuleSystem callback map

`main+0x11d1b14` constructs a 41-slot ModuleSystem component list. Component names are obtained from the component vtable name getter (`+0xc8`; secondary short names where present). The two unnamed slots deliberately return an empty string and execute the same no-op `RET`; no semantic name is invented for them.

| Slot | Component identity | Concrete `vtable+0x60` target | Note |
|---:|---|---|---|
| 0 | `System` | `main+0x26a7fc0` | no-op `RET` |
| 1 | `DenguModule` | `main+0x2ae7b14` | |
| 2 | `Resource` | `main+0x249d114` | |
| 3 | `RSDB` | `main+0x2afafb8` | |
| 4 | `Graphics` | `main+0xc9f1e4` | |
| 5 | `Ltk` | `main+0x2af178c` | |
| 6 | `Visualize` | `main+0x2b01094` | |
| 7 | `Controller` | `main+0xd1d3f8` | |
| 8 | `Rumble` | `main+0xc0eaa4` | |
| 9 | `Actor` | `main+0xa85380` | |
| 10 | `Transceiver` | `main+0x12c1304` | |
| 11 | `Banc` | `main+0x2460bcc` | |
| 12 | `Scene` | `main+0x9370e8` | |
| 13 | `AS` | `main+0x2adc5f4` | |
| 14 | `AI` | `main+0x2adbb54` | |
| 15 | `Physics` | `main+0x2af2ba0` | |
| 16 | `ProgramHotReloadModule` (`PHR`) | `main+0x26a7fc0` | no-op `RET` |
| 17 | unnamed component | `main+0x26a7fc0` | name getters return empty string; no-op `RET` |
| 18 | `Event` | `main+0x2488cf8` | |
| 19 | `EventModuleWorker` | `main+0x2488e04` | |
| 20 | `EventModuleSubWorker` | `main+0x2488fc0` | |
| 21 | `EventModuleSubWorker` | `main+0x2488fc0` | same primary vtable as slot 20 |
| 22 | `UI` | `main+0x869624` | |
| 23 | `Effect` | `main+0xc1c28c` | |
| 24 | `Sound` | `main+0x9bc044` | |
| 25 | `XLink` | `main+0xd51f6c` | |
| 26 | `Reaction` | `main+0xbd1b68` | |
| 27 | `Terrain` | `main+0x12b6d4c` | |
| 28 | `ECppModule` (`EC++`) | `main+0x2af1554` | |
| 29 | `SpyLog` | `main+0x2afc46c` | |
| 30 | `GameData` | `main+0xee96cc` | |
| 31 | `Blackboard` | `main+0x9143f4` | |
| 32 | `LuaModule` (`Lua`) | `main+0x26a7fc0` | no-op `RET` |
| 33 | `Tool` | `main+0x1219f54` | |
| 34 | `Camera` | `main+0x1015ffc` | |
| 35 | `REC` | `main+0x2af1648` | |
| 36 | `LOD` | `main+0x77fa74` | |
| 37 | unnamed component | `main+0x26a7fc0` | name getters return empty string; no-op `RET` |
| 38 | `Bake` | `main+0xf6a020` | |
| 39 | `Rail` | `main+0x2af3cbc` | |
| 40 | `PlayReport` | `main+0xad231c` | |

There are 41 slots and 36 unique `vtable+0x60` targets.

## Strict Stage K cadence correlation

Use only Res1X pure cadence windows:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Observed family growth:

- shared DepWorker callback `main+0x86a490`: P0 `2.130x`, P1 `2.164x`
- `EventModuleSubWorker` family `main+0x86bc9c`: P0 `5.590x`, P1 `2.961x`
- generic ReceiveLightMessageQueue frontier `main+0x2a2d958`: P0 `1.232x`; P1 approximately `1.179x` using only three visible slow windows because frame 1560 is top-4 censored
- shared dispatcher LockMutex site `main+0x86a530`: P1 `4.870x`; P0 slow/fast is greater than `3.684x` because frame 960 is top-4 censored
- recurring LockMutex site `main+0x86a678`: visible in slow cadence but cannot be given an exact strict aggregate from top-4-censored data

The generic queue-entry family grows far less than the EventModuleSubWorker and shared-dispatch synchronization families.

## Stage K decision

The requested offline grandparent mapping is complete.

Durable classification:

1. `main+0x86bc9c` has a concrete semantic owner: **EventModuleSubWorker**.
2. `main+0x86a490`, `main+0x86a530`, and `main+0x86a678` converge on **shared dependency-worker / ModuleSystem scheduling infrastructure**.
3. The concrete ModuleSystem work targets reachable through `main+0x86a988` are now fully enumerated, but the existing Stage K runtime record does not contain the work-object/vtable identity needed to decide which component owned each expensive shared-worker slice.
4. `main+0x2a2d958` is a generic indirect message-loop dispatch frontier and is not a final owner.

Therefore no arbitrary deeper stack stage is justified, and **Stage L must not be created merely to add depth**.

If another runtime attribution is later approved, the narrow useful identity is the resolved ModuleSystem work target at `main+0x86a988` / `main+0x2af1230 -> vtable+0x60`, not a global stack widening. That future ARM attempt still requires fresh explicit authorization and must remain one authorization = one attempt.

No optimization is justified from this record alone.