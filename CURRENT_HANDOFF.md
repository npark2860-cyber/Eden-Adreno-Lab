# CURRENT HANDOFF — Eden Adreno X1 Address Arbiter Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current experiment branch: `exp/x1-guest-post-wait-attribution`
- Guest Post Wait cleanup/code anchor: `d9df8d7f594c3030ee518a2bd489a15708ad87b4`

Documentation commits after `d9df8d7f...` may advance the branch HEAD; verify that changes since this anchor are documentation-only before using it as the current code state.

Never change the exact Eden baseline without the explicit baseline-change procedure.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Verified branch / workflow / completed build state

Before the documentation updates in this handoff:

- branch `exp/x1-guest-post-wait-attribution` was exactly at `d9df8d7f594c3030ee518a2bd489a15708ad87b4`;
- that commit removes the corrected one-shot marker;
- corrected one-shot workflow is absent;
- persistent `.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml` remains `workflow_dispatch` only.

Approved Guest Post Wait build:

- run `33150086343`
- job `98779808729`
- attempt `1`
- build HEAD `d4cbe0ba893a61650583926434261565242bca3f`
- conclusion `success`
- artifact `Eden-dc95-X1-guest-post-wait-attribution`
- artifact id `9678004761`
- size `31,349,148` bytes
- SHA-256 `4c310923a53b3cfd337893329b1fbd41e317a79200139ae559064a520e882ee9`

Earlier run `33149694136` failed before ARM compilation because the wrapper selected WSL `bash` rather than Git Bash; it was not an experiment/compiler failure.

## Closed / retained causal facts

### Draw / texture / alias

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication.
- trivial alias dedupe / required outside-RP CopyImage removal remains rejected.

### Uniform

- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant gameplay Uniform path is mapped adaptive fast stream.
- tracked payload fingerprint: 97.65% same payload.
- blind reuse is invalid because lifetime/in-flight/descriptor identity still matter.
- wholesale classic-cache fallback A/B did not break the gameplay ceiling.

### Cadence / swap / DFPS

- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; raw swap3 ~= nominal 20-FPS opportunity.
- VI ~= 60 Hz.
- raw swap interval is guest QueueBuffer input.
- raw3->effective2 HWC clamp did not increase upstream frame generation.
- DFPS ON/OFF can both remain ~20-FPS class.
- cadence/swap3 are downstream symptoms, not the root frame-production cause.

### BufferQueue

Slow gameplay:

- Queue -> Dequeue ~0.16 ms
- Dequeue total ~0.05 ms
- free-slot wait ~0.001 ms
- Dequeue END -> next Queue ~45-47 ms

Conclusion: BufferQueue free-slot/backpressure is closed as primary owner.

### Frame Build

Slow gameplay ~48-55 ms/frame while measured RasterizerVulkan work explains only a minority:

- Vulkan Draw roughly 8-11 ms/frame
- Graphics Configure roughly 7 ms/frame
- FillImageViews roughly 0.7 ms/frame

Large residual remains outside measured RasterizerVulkan scopes.

### GPU Command

- slow GPU worker spends most wall time in `PopWait/queueWait`;
- DmaPusher active work is material but does not own the missing ~30 ms;
- `PushCommand` is tiny; synchronous `blockWait=0`.

Conclusion: GPU worker is starved waiting for upstream command supply.

### GPU Submit Gap

Exact path:

`NVDRV Ioctl -> nvhost_gpu SubmitGPFIFO -> PushGPUEntries -> GPUThread SubmitList -> GPU worker`

NVDRV service-entry, device-submit and PushGPUEntries gaps match; handler body / SubmitGPFIFOImpl / channel lock / copy/read/fence/syncpoint are tiny.

Conclusion: ~25-30 ms inter-submit gap exists before NVDRV handler entry.

### Guest Submit Thread

- dominant guest submitter = `tid=0x53`;
- share essentially 100%;
- priority 30, current/active core 1;
- caller PC is run-relocated but stable within a run;
- slow CPU share ~1-2%.

Conclusion: submitter is not CPU-bound during the missing interval.

### NVDRV IPC Dispatch Gap

Measured boundary:

`C_prev -> next SendSyncRequest A -> NVDRV handler B -> handler complete C`

Slow gameplay:

- guestPost ~26.7-29.3 ms/request
- IPC dispatch ~0.02-0.03 ms/request
- service/reply ~0.02-0.05 ms/request

Conclusion: Windows ARM64 nvservices host-thread wake/dispatch is not the root cause. Long time is guest-side C -> next submit request.

## Guest Post Wait Attribution — completed

Runtime:

`eden_log(20260828-080040).txt`

Environment:

- exact dc95 / TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Adreno X1-85, driver 512.863.0, Vulkan 1.3.295
- swap3->2 clamp OFF
- Descriptor Ring was still ON but sampled DBUF reports had `alloc=0`, `reuseWait=0`; no rerun is required for that reason.

### Primary runtime result

The dynamic submitter's C -> next candidate interval is overwhelmingly KThread `Waiting`:

- steady fast/slow reports generally `waitShare ~= 96-99%`;
- residual generally ~0.4-1.3 ms/frame;
- submitter CPU share remains ~1-2%;
- IPC dispatch remains ~0.02-0.03 ms/request.

Therefore:

> The missing guest-post interval is guest KThread wait residency, not CPU execution or nvservices dispatch latency.

### Fast -> transition -> slow Arbitration behavior

Fast raw-swap-2 windows:

- frame 240: `Arbitration=1.253 ms/frame`
- frame 480: `1.080`
- frame 600: `2.595`
- frame 720: `1.112`
- frame 840: `1.030`

Transition / slow:

- frame 360, still raw swap2: `23.771 ms/frame`
- frame 960 transition->swap3: `57.526`
- frame 1080 stable slow: `26.751`
- frame 1200 stable slow: `50.103`

This is strong correlation, and frame 360 shows the AddressArbiter expansion can precede raw swap3.

Critical counterexample:

- frame 1320 remains stable slow at `50.227 ms/frame`
- `guestPostAvg=24.228 ms`
- `waitShare=98.89%`
- `Arbitration=8.615 ms/frame`
- `None=40.741 ms/frame`

Therefore Arbitration alone is **not yet** established as the entire slowdown owner.

Correct current statement:

> Guest-post slowdown is KThread Waiting dominated. A once-per-frame AddressArbiter wait frequently expands sharply with slowdown, but unclassified None waits can also dominate a stable-slow window.

Full 120-frame table is in `DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`.

## Guest Post Wait profiler source review

### Wait reason is trustworthy

Exact dc95 `KThread::BeginWait()` enters Waiting first. AddressArbiter then sets `ThreadWaitReasonForDebugging::Arbitration` under scheduler locking.

The profiler snapshots the old reason on Waiting -> non-Waiting before baseline `SetState()` clears the reason. Therefore recorded Arbitration duration is valid despite SetWaitReason following BeginWait.

### `topSvc0=0x0` is broken attribution

The profiler samples `KThread::StackParameters::current_svc_id` on wait entry, but exact dc95 does not populate that field and the transplant installs no SVC recorder.

Therefore all `topSvc=0` output is unusable and must not be interpreted as SVC 0.

### `None` is a real unclassified Waiting bucket

Because classification happens at wait exit, the large None bucket is not a transient reason-order artifact from AddressArbiter. It represents Waiting paths whose debug reason remained None. Current instrumentation does not identify their call site.

### reply-wake exclusion

Representative begin/end/request counts are consistent with intended NVDRV reply exclusion. No representative orphan/nested/malformed pattern indicates an obvious pairing failure.

## Exact dc95 Arbitration mapping

The only actual `ThreadWaitReasonForDebugging::Arbitration` setter path is `KAddressArbiter`.

Blocking path:

`Svc::WaitForAddress` (`SvcId 0x34`)
-> `WaitAddressArbiter`
-> `KAddressArbiter`
-> one of:
  - `WaitIfLessThan`
  - `DecrementAndWaitIfLessThan`
  - `WaitIfEqual`
-> KThread Waiting reason `Arbitration`.

Wake side:

`Svc::SignalToAddress` (`SvcId 0x35`).

Important exclusion:

- mutex `ArbitrateLock/Unlock` uses `KConditionVariable` and is tagged `ConditionVar`;
- process-wide-key condition-variable waits are also tagged `ConditionVar`.

Thus runtime `Arbitration` specifically means AddressArbiter/WaitForAddress, not generic mutex contention.

`arbN=120` in every non-startup 120-frame report means exactly one completed AddressArbiter wait per rendered frame for `tid=0x53` in those windows.

Source-only analysis cannot yet identify which guest address/type/timeout or which logical TOTK/SDK synchronization object it is.

## Current next action

Read:

`NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md`

Stage A only:

Directly instrument `Svc::WaitForAddress` for the dynamic submitter/post-window and aggregate by `(guest address, ArbitrationType)`:

- count
- timeout
- total/avg/max blocked duration
- result/timeout status if possible without changing semantics

No per-event logging. No generic all-SVC recorder. No scheduler profiler.

Only if one address is proven dominant should a later Stage B instrument `SignalToAddress` for that exact address and identify the signaler/waker thread.

If a frame-1320-like slow None bucket remains after Stage A, separately identify only the unclassified BeginWait source class for `tid=0x53`.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.