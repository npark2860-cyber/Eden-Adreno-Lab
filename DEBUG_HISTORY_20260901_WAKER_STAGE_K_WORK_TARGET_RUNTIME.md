# DEBUG HISTORY — 2026-09-01 Waker Stage K Work-Target Runtime

Updated: 2026-09-01 KST

## Scope

This record closes the Windows ARM64 build gate for the repaired Stage K x26 work-target resolver and records the first runtime evidence containing normalized `(shim_offset, work_target_offset)` pairs.

No behavior-changing optimization is authorized by this record.

## Fixed baseline / branch

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Persistent ARM workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Persistent trigger remains:

`workflow_dispatch` only.

## Resolver insertion repair preceding successful build

The second ARM compile blocker was repaired by:

`d8d9997cc388c934b21513738a34207fa8d6a364` — `fix: place Stage K resolver before producer declaration`

The compatibility wrapper now inserts the resolver immediately before the complete `x1_stage_g_out_index` producer declaration, instead of locating the insertion point from the inner `GetTrackedProducerIndex(...)` token.

A temporary Ubuntu validator reconstructed exact dc95 through Stage K and verified the resolver placement/invariants. The temporary validator was then removed before the authorized ARM attempt.

## Successful Windows ARM64 attempt

Fresh authorization was consumed for exactly one Windows ARM64 attempt.

Persistent workflow run:

`33475954305`

Job:

`99755146485`

Attempt:

`1`

Event:

`workflow_dispatch`

Workflow head SHA:

`94856d2d8517e76fcd39289e2f3a52560736e6b2`

Result:

**SUCCESS**

The job passed exact dc95 checkout verification, all retained/Stage D-K reconstruction steps, Stage K verification, ARM64 configure, full C++ build, packaging, analyzer/metadata addition, and artifact upload.

No rerun/retry was used.

### Artifact

Name:

`Eden-dc95-X1-waker-stage-k`

Artifact ID:

`9788853936`

Size:

`31,431,536` bytes

SHA-256:

`d782e5f3b575c4c088e4af8be5e86a43b2a3b46b9807c9715a5aac140c55e411`

## One-shot dispatcher cleanup

The temporary one-shot dispatcher used to consume the single authorization was removed after dispatch.

Branch HEAD after dispatcher cleanup, before this documentation update:

`6504731dc6286a740ce57a9a255f5c1f25071bd1`

The persistent ARM workflow remains `workflow_dispatch` only.

Current Windows ARM64 authorization after the successful attempt:

**NONE**

## Runtime source

User-supplied runtime log:

`eden_log.txt`

The log identifies:

- Eden: `HEAD-dc95cd09ee-HEAD`
- game: The Legend of Zelda: Tears of the Kingdom `1.2.1`
- title ID: `0100F2C0115B6000`
- renderer: Vulkan
- device: Qualcomm Adreno X1-85
- resolution: `Res1X`
- `dump_nso: true`

Exact main NSO identity from the log:

- build ID: `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- runtime main base: `0x805d6000`
- runtime main end: `0x84d01000`
- size: `0x472b000`

Raw runtime VAs remain observations only. Durable analysis uses `main+offset`.

## x26 work-target resolver — runtime confirmed

The Stage K output contains nonzero:

- `workResolvedN`
- `workResolvedTicks`
- `workOtherResolvedTicks`
- `workOverflowN/workOverflowTicks`
- resolver-status accounting
- `workTop0..workTop3`

Therefore the x26 runtime work-target identity extension is operational on Windows ARM64.

The emitted pair format is:

`workTopN=<shim_offset>/<work_target_offset>/<ticks>/<count>/<percent>`

## Recurring runtime work-target pairs

The dominant recurring non-common-shim pairs observed in the capture are:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x86bc04 -> main+0x2ada93c`
3. `main+0x244fc20 -> main+0x2ad6b20`

These are the immediate offline semantic-mapping targets.

The already-known common ModuleSystem shim also appears at runtime:

`main+0x2af1230 -> component vtable+0x60 target`

Observed examples include:

- `main+0x2af1230 -> main+0xc1c28c`
- `main+0x2af1230 -> main+0xa5df60`
- `main+0x2af1230 -> main+0x2adbb54`

Do not merge the three non-common-shim pairs into the ModuleSystem mapping merely because they occur in the same selected-producer capture.

## Example strict-window evidence

The existing strict cadence convention remains:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Examples from the new work-target log:

- frame `1080`, producer 0:
  - `0x96e2a8/0x26936d0`: `9,694,853` ticks, `20.71%`
  - `0x86bc04/0x2ada93c`: `5,657,143` ticks, `12.09%`
  - `0x244fc20/0x2ad6b20`: `1,729,871` ticks, `3.70%`
- frame `1320`, producer 1:
  - `0x96e2a8/0x26936d0`: `7,707,685` ticks, `17.44%`
  - `0x86bc04/0x2ada93c`: `2,682,733` ticks, `6.07%`
  - `0x244fc20/0x2ad6b20`: `1,813,780` ticks, `4.10%`
- frame `1440`, producer 0:
  - `0x96e2a8/0x26936d0`: `7,882,811` ticks, `18.98%`
  - `0x86bc04/0x2ada93c`: `7,115,400` ticks, `17.13%`
- frame `1440`, producer 1:
  - `0x96e2a8/0x26936d0`: `9,353,792` ticks, `25.38%`
  - `0x86bc04/0x2ada93c`: `1,750,375` ticks, `4.75%`
- frame `1560`, producer 0:
  - `0x96e2a8/0x26936d0`: `7,075,395` ticks, `17.88%`
  - `0x86bc04/0x2ada93c`: `5,048,660` ticks, `12.76%`
  - `0x244fc20/0x2ad6b20`: `1,161,881` ticks, `2.94%`
- frame `1560`, producer 1:
  - `0x96e2a8/0x26936d0`: `9,167,821` ticks, `25.26%`
  - `0x86bc04/0x2ada93c`: `2,801,703` ticks, `7.72%`

These examples establish that the pairs are real, recurrent runtime work identities. They do **not** by themselves establish the semantic owner names or prove a single target is the sole slow-cadence cause.

## Immediate semantic-mapping task

Use the exact TOTK 1.2.1 main NSO build ID:

`9B4E43650501A4D4489B4BBFDB740F26AF3CF85`

Offline-disassemble and reference-trace the following three non-common-shim paths:

- `main+0x96e2a8 -> main+0x26936d0`
- `main+0x86bc04 -> main+0x2ada93c`
- `main+0x244fc20 -> main+0x2ad6b20`

The current tab had begun trying to extract the exact dumped `main-...nso` from the user-provided dump ZIP. If the archive is not visible in a new tab, obtain/re-upload the same exact dump rather than guessing from another game revision or build ID.

Map each pair by code shape, callers/xrefs, vtable/constructor/registration references, nearby strings, and already-known Stage K semantic anchors.

Do not hardcode runtime bases or raw VAs.

## Causal frontier after this capture

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two selected producer threads
-> producer CPU growth + Arbitration growth
-> exact Nintendo SDK blocker semantics
-> Stage J main/LockMutex parent
-> Stage K grandparent semantic mapping
-> EventModuleSubWorker + shared dependency-worker/ModuleSystem branches
-> x26 runtime work-target resolver
-> **runtime work-target identities observed**
-> **current frontier: semantic ownership of the three dominant non-common-shim pairs**.

No behavior-changing optimization is justified until this semantic mapping is closed and the slow/fast correlation is interpreted against those concrete owners.
