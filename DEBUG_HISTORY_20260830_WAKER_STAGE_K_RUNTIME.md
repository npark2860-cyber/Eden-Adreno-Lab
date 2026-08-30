# DEBUG HISTORY — Waker Stage K Runtime / Resolution A-B

Updated: 2026-08-30 KST

## Fixed baseline

Repository:

`npark2860-cyber/Eden-Adreno-Lab`

Exact Eden source remains immutable:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Stage K branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization after the completed build attempt: **NONE**.

No ARM rebuild/rerun is authorized by this document.

## Stage K post-fix Windows ARM64 build — SUCCESS

A fresh explicit authorization was consumed for exactly one post-fix Stage K Windows ARM64 attempt.

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33287796384`
- job: `99193953965`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- exact dc95 checkout: success
- retained A-J reconstruction: success
- Stage K snapshot/application: success
- Stage K pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 C++ build: **SUCCESS**
- package: success
- analyzer/metadata addition: success
- upload: success
- retry/rerun/additional ARM attempt: none

One-shot dispatcher lifecycle:

- creation / dispatch commit: `25701cc1305a85c47debbbf42af1e646c8822e5b`
- removal commit: `112541623742853bdb1c6114959f5bb5317cde89`

Artifact:

- name: `Eden-dc95-X1-waker-stage-k`
- artifact ID: `9725325607`
- size: `31,427,618` bytes
- SHA-256: `7483a09b7550f7a00cbe214e63b57ba43e6de8b0855299c731ea73412cdff926`
- created: `2026-08-30T02:50:02Z`
- expires: `2026-09-13T02:49:59Z`

The earlier lexical-scope compile blocker is therefore closed as a build blocker.

## First Stage K runtime — Res2X abnormal rendering

Runtime log:

`eden_log(20260830-025816).txt`

SHA-256:

`89784845234bd896149c61b9a856ab3b8b720b6588d6a9bb6a38b34a5755d2cf`

Environment observed in log:

- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Qualcomm Adreno X1-85
- Adreno Vulkan driver 512.863.0
- Vulkan 1.3.295
- Dynarmic CPU backend
- `Renderer.resolution_setup: Res2X`
- FSR scaling filter
- behavior-changing X1 A/B toggles off

User-observed behavior on this run:

- first newly observed abnormal rendering during the long attribution series;
- visible image occupied only approximately the upper-left quarter of the output;
- one launch terminated before normal game operation on an earlier attempt; that terminated process is not represented by this surviving log, so its cause is not established.

Full-log count of depth-scale failures:

- `BlitScaleHelper: Device does not support scaling format D32_FLOAT`: **12,091**
- `BlitScaleHelper: Device does not support scaling format D16_UNORM`: **7,685**
- total `BlitScaleHelper` unsupported-scaling errors: **19,776**

The geometric symptom is consistent with a 2x image / output-scale mismatch, but the log alone does not prove the exact viewport/blit mechanism.

Do not attribute this visual regression to Stage K frame walking merely because it first appeared in the Stage K binary.

## Stage K profiler health during the Res2X run

Stage K itself continued to emit bounded selected-producer records.

Representative reports showed:

- selected producer IDs `0x80` / `0x81` once latched;
- `grandRangeBadN=0`;
- `grandZeroN=0`;
- `badStatus=0`;
- no evidence of widespread invalid grandparent-frame reads.

Therefore the Res2X rendering symptom and Stage K grandparent attribution must remain separate hypotheses unless joined by direct evidence.

## Controlled follow-up — Res1X capture

Runtime log:

`eden_log(20260830-122027).txt`

SHA-256:

`3b1ae0252918010736b842767b39c3cdd090215918a624e618b42a3fd57522cb`

The log records `Renderer.resolution_setup: Res1X`.

Full-log comparison:

- `BlitScaleHelper` unsupported-scaling errors at Res2X: **19,776**
- `BlitScaleHelper` unsupported-scaling errors at Res1X: **0**
- `VK_ERROR_UNKNOWN` occurrences: **2** in both captures; this is not a new Stage K-only signature.
- fatal/unhandled/crash text in the Res1X log: none found.

The user supplied the Res1X capture after the requested A/B. The chat does not contain an explicit textual confirmation that the visual image returned to normal, so that visual observation must not be invented. What is proven from the logs is that the massive Res2X depth-scaling error stream disappears completely at Res1X.

## Res1X Stage K validity

Stage K remains healthy through the late runtime windows.

Representative frame `1200`:

- producer 0: `3511` slices, `3509` valid; `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- producer 1: `3351` slices, `3350` valid; `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`

Representative frame `1560`:

- producer 0: `4190` slices, `4189` valid; `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`
- producer 1: `4023` slices, `4022` valid; `grandRangeBadN=0`, `grandZeroN=0`, `badStatus=0`

`parentUnavailable` is tiny and sporadic. There is no material Stage K frame-walk validity collapse.

## Strict cadence windows in the Res1X capture

Using only 120-frame report windows whose QueueBuffer cadence is pure:

- strict fast / swap2: frames `960`, `1080`
- strict slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Mixed windows such as `840` and `1200` should not be used as primary fast/slow evidence.

## Stage K normalized grandparent families

For the final Res1X process instance, module ranges include:

- main: `0x800c1000-0x847ec000`
- subsdk0: `0x847ec000-0x84e95000`
- sdk: `0x84e95000-0x85c6e000`

The recurring dominant Stage K quadruples normalize to:

1. `sdk+0x158528 / sdk+0x124a8c / main+0x86a820 / main+0x86a490`
   - Stage I/J meaning through parent: `WaitForAddress -> WaitLightEvent -> main+0x86a820`
   - Stage K now reaches grandparent `main+0x86a490`.

2. `sdk+0x158528 / sdk+0x124b40 / main+0x86be08 / main+0x86bc9c`
   - second `WaitLightEvent` return family;
   - Stage K reaches grandparent `main+0x86bc9c`.

3. `sdk+0x158528 / sdk+0x127058 / main+0x2a904cc / main+0x2a2d958`
   - `ReceiveLightMessageQueue` family;
   - Stage K reaches grandparent `main+0x2a2d958`.

4. `sdk+0x158420 / sdk+0x13178c / sdk+0x127e54 / main+0x86a530`
   - `ArbitrateLock -> InternalCriticalSectionImplByHorizon::Enter -> LockMutex`;
   - Stage K now crosses from the generic SDK LockMutex parent into `main+0x86a530`.
   - another recurring grandparent for this LockMutex family is `main+0x86a678`; do not merge them before static mapping.

This is the key Stage K success: all principal Stage J synchronization families now have concrete `main` grandparent offsets available for offline semantic mapping.

Do not yet claim these offsets are the final frame-critical game-work owners. They are caller return addresses and still require exact function/prologue/call-site mapping.

## Resolution-scaling interpretation

The earlier observation that 2x resolution produced little subjective slowdown is no longer valid as standalone evidence for a CPU-only ceiling.

Reason:

- the same Res2X run shows a massive unsupported depth-scaling error stream and abnormal quarter-screen output;
- therefore it has not been proven that the expected 2x rendering workload was executed and presented correctly.

The correct durable rule is:

> Do not use resolution-insensitivity as GPU-vs-CPU evidence until the scaling path itself is verified to render correctly and the actual render-target workload is confirmed.

This does not reopen the already measured CPU/synchronization chain. It only removes the unverified Res2X subjective observation as independent support for that chain.

## Current decision

Stage K runtime instrumentation is valid enough to continue offline analysis.

Do **not** add Stage L yet.

Immediate technical next action:

1. use the Res1X log as the primary Stage K runtime capture;
2. analyze strict swap2 `960/1080` vs strict swap3 `1320/1440/1560/1680`;
3. map `main+0x86a490`, `main+0x86bc9c`, `main+0x2a2d958`, `main+0x86a530`, and recurring `main+0x86a678` against the exact dumped TOTK 1.2.1 main NSO;
4. identify enclosing functions and direct/indirect call semantics;
5. only after that decide whether Stage K is sufficient or one more bounded attribution step is justified.

No behavior-changing optimization is justified yet.
