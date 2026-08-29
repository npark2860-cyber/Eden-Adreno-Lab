# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline / rules

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-stage-h-module-callpath-mapping`
- Stage H implementation code base HEAD: `59cbc61cafe8c1ae7360dc7e04e6f884c7a74512`
- successful Stage H ARM build HEAD: `1c8b699ccc51ff7bca28fc57bf654c1e18fbd5f2`
- one-shot dispatcher cleanup commit: `135d13a57d434e23d7f68928d0f335ed959d0892`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

Runtime-observed TIDs, guest addresses, PC and LR values are observations only and must not be hardcoded.

Primary records:

- Stage B runtime: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- Stage D runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_D_RUNTIME.md`
- Stage E runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_E_RUNTIME.md`
- Stage F runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_F_RUNTIME.md`
- Stage G implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_IMPLEMENTED.md`
- Stage G ARM precheck failure: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_ARM_PRECHECK_FAILURE.md`
- Stage G runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_G_RUNTIME.md`
- Stage H implementation/static: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_IMPLEMENTED.md`
- Stage H ARM build: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_BUILD.md`
- Stage H runtime: `DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`
- next action: `NEXT_ACTION_WAKER_STAGE_I.md`

## Persistent ARM workflow

Path:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Current workflow name:

`Build dc95 X1 Waker Stage H`

Trigger remains:

`workflow_dispatch` only.

No additional ARM64 attempt is authorized.

## Latest successful ARM64 build — Stage H SUCCESS

Exactly one fresh authorization was used for exactly one Stage H ARM64 attempt:

- workflow: `Build dc95 X1 Waker Stage H`
- run: `33246620972`
- job: `99085091095`
- attempt: `1`
- event: `workflow_dispatch`
- build HEAD: `1c8b699ccc51ff7bca28fc57bf654c1e18fbd5f2`
- exact dc95 verification: success
- Stage A-G reconstruction / Stage H pre-configure verification: success
- MSYS2 / configure / ARM64 compile / package / analyzer metadata / upload: success
- conclusion: success
- retry/rerun/additional ARM attempt: none

Canonical artifact:

- name: `Eden-dc95-X1-waker-stage-h`
- artifact ID: `9713380302`
- size: `31,419,464` bytes
- SHA-256: `ff166f3f39c695c1e8e879a7ecbfeca2916028f3318802123bed584775fe4d90`
- expires: `2026-09-12T10:24:22Z`

A later `ㄱㄱ` arrived while this same run was still active and was used only to resolve that run. It was not consumed as authorization for another ARM64 attempt.

## Closed historical chain

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is adaptive mapped fast stream/re-stream.
- classic-cache fallback did not break the gameplay ceiling.
- QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS; VI ~= 60 Hz.
- raw3->effective2 clamp did not improve upstream frame generation.
- DFPS is not root cause.
- BufferQueue free-slot/backpressure is closed as primary owner.
- GPU worker is predominantly waiting for command supply.
- NVDRV handler / SubmitGPFIFO / locks / fence / syncpoint are not the missing interval owner.
- NVDRV IPC dispatch ~= `0.02-0.03 ms/request`.
- host scheduler starvation is closed as primary owner for both dynamic-waker and producer slowdown.

## Stage A-G causal chain — COMPLETE THROUGH PC/LR ATTRIBUTION

Stage A/B:

- dominant guest submitter/victim observed as runtime TID `0x53`;
- matching dynamic waker observed as runtime TID `0x4f`;
- matching signal is `SignalAndIncrementIfEqual` on one dynamically latched per-process gameplay address;
- victim wait ~= wait-start -> signal; signal -> victim return is near zero.

Stage C/D:

- fast -> slow inter-signal growth splits into corrected Waiting + a large CPU/residual branch;
- host runnable-unscheduled time is too small to explain the slowdown;
- dynamic-waker slow Waiting becomes overwhelmingly Arbitration.

Stage E:

- promoted address recursion is repeated short `WaitForAddress` synchronization;
- two dominant producer signalers are dynamically discovered;
- fast w2s is around sub-ms, slow w2s grows to multi-ms;
- signal -> return remains near immediate.

Stage F:

- both producers show mixed CPU growth + Arbitration growth;
- runnable-unscheduled remains much smaller;
- keep CPU and Arbitration accounting branches separate.

Stage G runtime `eden_log(20260829-093642).txt`:

- Stage G exact scheduler `cpuTicks` reconcile essentially exactly with Stage F CPU;
- recurring saved-PC family uses two PC endpoints and a small LR family;
- fixed 64-context overflow is material;
- Stage G context is a scheduler slice-end execution context, not literal instruction residence time.

## Stage H — RUNTIME COMPLETE

Runtime record:

`DEBUG_HISTORY_20260829_WAKER_STAGE_H_RUNTIME.md`

Runtime log:

`eden_log(20260829-103238).txt`

Log SHA-256:

`02e42efccd2bf2d8c8bc3f2a5432b7a149ece0fb1faf6eac813fe8b5a9b58da0`

### Loaded module truth

- `rtld`: `0x80758000-0x8075c000`
- `main`: `0x8075c000-0x84e87000`
- `subsdk0`: `0x84e87000-0x85530000`
- `sdk`: `0x85530000-0x86309000`

All recurring Stage G top contexts normalize to `sdk`, not `main`/`subsdk0`:

- `sdk+0x158528 / sdk+0x124a8c`
- `sdk+0x158420 / sdk+0x13178c`
- `sdk+0x158528 / sdk+0x124b40`
- `sdk+0x158528 / sdk+0x127058`

The prior Stage G raw address family and this run's raw family shifted together by `0x88a000`, confirming that absolute PC/LR was ASLR-dependent while the module-relative family is stable.

### Cadence used

Primary fast comparison:

- frames `600,720,840`
- 352/360 queue events are swap2 (`97.8%`)
- all Stage G sanity counters clean

Strict pure-swap2 check:

- frame `840`

Excluded:

- frame `480`: first armed window, one `missingStart` per producer
- frame `960`: transition/hitch

Slow comparison:

- frames `1080,1200,1320`
- 360/360 swap3

### Stage F / G reproduction

Producer 0 fast -> slow:

- Stage F CPU `0.864 -> 4.662 ms`, `+3.797`
- Waiting `4.958 -> 9.352`, `+4.394`
- Arbitration `4.780 -> 8.962`, `+4.182`
- runnable-unscheduled `0.270 -> 0.794`, `+0.524`

Producer 1:

- Stage F CPU `1.066 -> 5.144 ms`, `+4.078`
- Waiting `6.489 -> 11.276`, `+4.787`
- Arbitration `6.283 -> 10.894`, `+4.611`
- runnable-unscheduled `0.384 -> 0.689`, `+0.305`

Stage G exact CPU reconciliation:

| producer | Stage G fast | Stage F fast | Stage G slow | Stage F slow |
|---|---:|---:|---:|---:|
| 0 | 0.86458 | 0.86448 | 4.66077 | 4.66154 |
| 1 | 1.06624 | 1.06640 | 5.14345 | 5.14406 |

### Canonical context contribution

Producer 0 CPU growth `+3.796 ms`:

- `sdk+0x158528 / sdk+0x124a8c`: `+0.945 ms` (`24.9%`)
- `sdk+0x158420 / sdk+0x13178c`: `+0.749` (`19.7%`)
- `sdk+0x158528 / sdk+0x124b40`: `+0.485` (`12.8%`)
- `sdk+0x158528 / sdk+0x127058`: `+0.098` (`2.6%`)
- overflow: `+1.409` (`37.1%`)

Producer 1 CPU growth `+4.077 ms`:

- `sdk+0x158528 / sdk+0x124a8c`: `+0.882 ms` (`21.6%`)
- `sdk+0x158420 / sdk+0x13178c`: `+0.815` (`20.0%`)
- `sdk+0x158528 / sdk+0x124b40`: `+0.220` (`5.4%`)
- `sdk+0x158528 / sdk+0x127058`: `+0.088` (`2.2%`)
- overflow: `+1.912` (`46.9%`)

The visible family + overflow explains about `97.1% / 96.1%` of producer 0/1 CPU growth. Overflow remains material, but it does not block identification of the dominant normalized SDK family, so do not widen the histogram yet.

### Direct cross-join to Stage D waker

The dynamic waker now has direct module/caller evidence joining it to the same SDK family:

- PC `sdk+0x158528`
- dominant LR `sdk+0x124b40`
- dominant LR `sdk+0x124a8c`
- occasional `sdk+0x13178c`
- occasional `sdk+0x13f364`

This establishes a shared Nintendo SDK/runtime path family across producers and waker. It does **not** yet prove which exact SDK operation or caller owns the causal slowdown.

Current-run waker fast -> slow:

- CPU `5.871 -> 25.840 ms`, `+19.969`
- runnable-unscheduled `0.232 -> 0.244`, only `+0.012`
- Arbitration per interval `5.837 -> 37.739 ms`

Host scheduler starvation remains rejected.

Stage E signal timing also reproduces:

- producer 0 w2s `0.458 -> 3.846 ms`, s2e stays ~`0.01 ms`
- producer 1 w2s `0.560 -> 3.441 ms`, s2e stays ~`0.01 ms`

Delay remains before producer signal.

## Stage H decision

Decision-map case **A selected**:

> dominant saved PC/LR contexts normalize to one shared runtime/SDK module and a small LR caller set.

Case B rejected for the visible dominant family: not producer-specific `main` work.

Case D not selected yet: overflow is large but the dominant normalized SDK family is already identifiable.

No optimization is justified yet.

## Immediate next action — Stage I, no new ARM build

Read:

`NEXT_ACTION_WAKER_STAGE_I.md`

Use Eden's existing `Dump Decompressed NSOs` / `Debugging.dump_nso` support to obtain the exact runtime SDK image:

`sdk-B9046C31EB5D31271BE970FE732D38DF49C6AA21.nso`

Then disassemble/function-boundary-map offline around:

- `sdk+0x158528`
- `sdk+0x158420`
- `sdk+0x124a8c`
- `sdk+0x124b40`
- `sdk+0x127058`
- `sdk+0x13178c`
- `sdk+0x13f364`

Goal: identify the exact Nintendo SDK runtime/synchronization semantics before adding caller depth, widening the histogram, or considering optimization.

Current ARM64 authorization: **NONE**.
