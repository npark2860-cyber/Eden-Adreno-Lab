# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-09-01 KST

## Source of truth / hard rules

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current experiment branch:

`exp/x1-waker-stage-k-grandparent-depth`

Exact immutable Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Immutable control branch:

`lab/dc95-arm64-baseline`

**Never change the exact baseline without explicit approval.**

Use GitHub documents as source of truth. Do not reconstruct project state from chat guesses.

### Windows ARM64 authorization rule — ABSOLUTE

- no Windows ARM64 build/rebuild/rerun without fresh explicit user authorization;
- one authorization = exactly one ARM attempt;
- failure does not authorize retry/rerun;
- no automatic retry;
- persistent ARM workflow stays `workflow_dispatch` only;
- current ARM64 authorization: **NONE**.

Ubuntu/static validation and offline NSO analysis do not consume ARM authorization.

Do not hardcode runtime TIDs, raw guest addresses, promoted keys, module bases, PC/LR/caller addresses. Durable address knowledge must use ASLR-normalized `module+offset`.

No broad/all-thread profiling. No behavior-changing priority/affinity/yield/reschedule/wait/signal/GPU/QueueBuffer/cadence changes.

Do not create Stage L merely to add stack depth.

Do not implement behavior-changing optimization before concrete semantic owner attribution is closed.

## Read these records first

At minimum:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_I_SDK_DISASSEMBLY.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_J_RUNTIME.md`
- `DEBUG_HISTORY_20260829_WAKER_STAGE_K_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_SCOPE_FIX.md`
- `DEBUG_HISTORY_20260830_WAKER_STAGE_K_RUNTIME.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IMPLEMENTED.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_ARM_BUILD_FAILURE.md`
- `DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_SHADOW_FIX.md`
- `DEBUG_HISTORY_20260901_WAKER_STAGE_K_WORK_TARGET_RUNTIME.md`
- `NEXT_ACTION_WAKER_STAGE_K.md`

## Repository state at this handoff

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Branch HEAD after the successful ARM one-shot dispatcher was removed, before the 2026-09-01 handoff documentation commits:

`6504731dc6286a740ce57a9a255f5c1f25071bd1`

Recent source fix relevant to the successful build:

`d8d9997cc388c934b21513738a34207fa8d6a364` — `fix: place Stage K resolver before producer declaration`

Recent handoff docs commits before this file update:

- `95050a010828da49e4b49b7f231dd80cf0b2fdb5` — first x26 work-target runtime record
- `90bac51dc63009c6f5588605926e3564d10866cc` — advance next action to offline semantic mapping

Verify actual branch HEAD at the start of the next tab before source work.

No source/workflow/baseline change is authorized by this handoff.

## Persistent Windows ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Workflow name:

`Build dc95 X1 Waker Stage K`

Trigger:

`workflow_dispatch` only.

No push/pull-request ARM trigger remains.

Current ARM64 authorization:

**NONE**

## Latest successful x26 Windows ARM64 build

This supersedes the previous failed build gate as the current x26 build source.

- workflow run: `33475954305`
- job: `99755146485`
- attempt: `1`
- event: `workflow_dispatch`
- workflow head SHA: `94856d2d8517e76fcd39289e2f3a52560736e6b2`
- result: **SUCCESS**
- retry/rerun: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9788853936`
- size: `31,431,536` bytes
- SHA-256: `d782e5f3b575c4c088e4af8be5e86a43b2a3b46b9807c9715a5aac140c55e411`

The build passed exact dc95 checkout, retained Stage D-K reconstruction, Stage K verification, ARM64 configure/build, packaging, analyzer metadata, and upload.

The temporary one-shot dispatcher was removed immediately afterward.

## Second compile blocker and fix — CLOSED

After the first `-Wshadow` repair, run `33395624235` still failed in the actual ARM C++ build.

The follow-up diagnostic/static work determined the compatibility wrapper inserted the Stage K resolver at the wrong lexical point relative to the producer declaration.

Minimal source fix:

`d8d9997cc388c934b21513738a34207fa8d6a364`

The wrapper now inserts the resolver before the complete producer declaration.

A temporary Ubuntu reconstruction validator confirmed the corrected placement/invariants and was removed before the successful ARM build.

Do not reopen this compile issue unless new evidence appears.

## Current runtime source — x26 resolver active

User-supplied log:

`eden_log.txt`

Confirmed environment:

- Eden: `HEAD-dc95cd09ee-HEAD`
- TOTK: `1.2.1`
- title ID: `0100F2C0115B6000`
- renderer: Vulkan
- GPU: Qualcomm Adreno X1-85
- resolution: `Res1X`
- `dump_nso: true`

Exact main NSO identity:

- build ID: `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`
- runtime main base: `0x805d6000`
- runtime main end: `0x84d01000`
- size: `0x472b000`

Raw base/range is observational only. Durable mapping uses `main+offset`.

The log contains populated Stage K work-target fields:

- `workResolvedN/workResolvedTicks`
- `workOtherResolvedTicks`
- `workOverflowN/workOverflowTicks`
- detailed resolver-status counters
- `workTop0..workTop3`

Therefore x26 runtime work-target identity is **observed and operational**.

## Runtime work-target pair format

`workTopN=<shim_offset>/<work_target_offset>/<ticks>/<count>/<percent>`

## Immediate runtime semantic frontier

Three dominant recurring **non-common-shim** pairs must now be semantically resolved offline:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x86bc04 -> main+0x2ada93c`
3. `main+0x244fc20 -> main+0x2ad6b20`

These are the three exact paths the next tab should disassemble/reference-trace against the exact TOTK 1.2.1 main NSO build ID `9B4E43650501A4D4489B4BBFDB740F26AF3CF85`.

The already-known common ModuleSystem shim also appears:

`main+0x2af1230 -> component vtable+0x60 target`

Observed common-shim concrete targets include:

- `main+0xc1c28c`
- `main+0xa5df60`
- `main+0x2adbb54`

Do **not** treat the three non-common-shim pairs as ModuleSystem components without proof.

## Exact Stage K semantic anchors already CLOSED

| Address | Durable classification |
|---|---|
| `main+0x86a490` | shared dependency-worker callback into dispatcher |
| `main+0x86bc9c` | **EventModuleSubWorker** virtual coordination/execution path |
| `main+0x2a2d958` | generic indirect thread/message-dispatch frontier |
| `main+0x86a530` | shared dispatcher LockMutex site A |
| `main+0x86a678` | shared dispatcher LockMutex site B |

`main+0x86a464` is shared by at least ModuleSystemWorker, NavMeshDepWorker, NavMeshCAStepDepWorker, and `phive::DepWorker`; it is not a unique gameplay owner.

Exact EventModuleSubWorker path:

`EventModuleSubWorker -> main+0x86bc04 -> main+0x86bd40 -> selected-object virtual operation -> nn::os::WaitLightEvent`

Keep this branch semantically separate from the common ModuleSystem work-target histogram.

## ModuleSystem static map — CLOSED

Shared execution chain:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Facts:

- `main+0x11d1b14` constructs a 41-slot ModuleSystem list;
- all 41 slots mapped;
- 36 unique concrete `vtable+0x60` targets;
- slots 17 and 37 are deliberately unnamed no-op components executing `main+0x26a7fc0: RET`.

## Strict cadence windows for the new log

Continue using pure cadence windows:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows remain non-primary.

Examples proving the new pair identities recur:

- frame `1080`, producer 0:
  - `0x96e2a8/0x26936d0` = `9,694,853` ticks / `20.71%`
  - `0x86bc04/0x2ada93c` = `5,657,143` / `12.09%`
  - `0x244fc20/0x2ad6b20` = `1,729,871` / `3.70%`
- frame `1320`, producer 1:
  - `0x96e2a8/0x26936d0` = `7,707,685` / `17.44%`
  - `0x86bc04/0x2ada93c` = `2,682,733` / `6.07%`
  - `0x244fc20/0x2ad6b20` = `1,813,780` / `4.10%`
- frame `1440`, producer 1:
  - `0x96e2a8/0x26936d0` = `9,353,792` / `25.38%`
  - `0x86bc04/0x2ada93c` = `1,750,375` / `4.75%`
- frame `1560`, producer 0:
  - `0x96e2a8/0x26936d0` = `7,075,395` / `17.88%`
  - `0x86bc04/0x2ada93c` = `5,048,660` / `12.76%`
  - `0x244fc20/0x2ad6b20` = `1,161,881` / `2.94%`

These numbers prove recurrent runtime identities, not yet semantic owner names or a sole causal owner.

Top4 censoring and unresolved/other-resolved buckets still matter.

## Immediate next action — NO ARM BUILD

Current ARM64 authorization:

**NONE**

Immediate work is offline only.

Use the exact dumped `main` NSO from TOTK 1.2.1 build ID:

`9B4E43650501A4D4489B4BBFDB740F26AF3CF85`

Disassemble/reference-trace:

1. `main+0x96e2a8 -> main+0x26936d0`
2. `main+0x86bc04 -> main+0x2ada93c`
3. `main+0x244fc20 -> main+0x2ad6b20`

For each, inspect code shape, callers/xrefs, vtables, constructors/destructors, registration tables, nearby strings/names, and relations to already-resolved Stage K anchors.

The current tab had started extracting the exact dumped `main-...nso` from the user-provided dump ZIP. If that archive is not visible in the next tab, re-obtain/re-upload the same exact dump. Do not substitute a different TOTK build or infer names from offsets alone.

Once semantic names are established, compare their strict swap2 vs swap3 contribution for both producers using `workResolvedTicks`, `workOtherResolvedTicks`, `workOverflowTicks`, status coverage, and visible top4 lower bounds.

Stop after semantic mapping/correlation unless the user authorizes another experiment.

## Current causal frontier

GPU command starvation
-> dominant guest submitter/victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two selected producer threads
-> producer CPU growth + producer Arbitration growth
-> Nintendo SDK blocker semantics
-> Stage J main/LockMutex parent
-> Stage K concrete main grandparent
-> EventModuleSubWorker + shared dependency-worker/ModuleSystem semantic split
-> 41-slot ModuleSystem static map
-> x26 runtime work-target resolver implemented
-> Windows ARM64 build **SUCCESS**
-> runtime x26 work identities **OBSERVED**
-> **current frontier: semantic ownership of the three dominant non-common-shim pairs**.

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
