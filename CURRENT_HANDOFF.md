# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-29 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-waker-pre-signal-attribution`
- Stage B runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`
- Stage C implementation record: `DEBUG_HISTORY_20260828_WAKER_STAGE_C_IMPLEMENTED.md`
- Stage C runtime record: `DEBUG_HISTORY_20260829_WAKER_STAGE_C_RUNTIME.md`
- next action: `NEXT_ACTION_WAKER_STAGE_D.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest ARM64 build — Stage C SUCCESS

- run `33190793610`
- job `98915420071`
- attempt `1`
- branch `exp/x1-waker-pre-signal-attribution`
- build HEAD `7fdb505cda0af8559e5cea600721dc2cb17ac38b`
- conclusion `success`
- exact dc95 verify `success`
- Stage C apply/verify `success`
- MSYS2 setup `success`
- configure `success`
- ARM64 compile `success`
- package `success`
- artifact upload `success`
- artifact `Eden-dc95-X1-waker-stage-c`
- artifact id `9694545153`
- size `31,377,910` bytes
- SHA-256 `c47e008a951ce3a974a9694d2b7ee8b06c4fd4379b387ad687a6e7b5f35e91b0`

No rerun occurred.

The temporary workflow-file-only push trigger used to create this one approved run was removed after success. The persistent workflow is back to manual-only `workflow_dispatch`.

## Closed causal chain retained

Do not reopen without new evidence:

- Draw reason-level barrier owner = `PostCopyBarrier`.
- Draw outside-RP large texture parent = `FillImageViews`.
- repeated alias copies are not trivial unchanged-state duplication; blind alias dedupe remains rejected.
- exact dc95 `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- dominant Uniform path is mapped adaptive fast stream; payload repeats heavily but blind lifetime reuse remains unsafe.
- classic-cache fallback did not break the gameplay ceiling.
- raw QueueBuffer swap2 ~= nominal 30-FPS opportunity; swap3 ~= nominal 20-FPS opportunity; VI ~= 60 Hz.
- swap3->effective2 clamp and DFPS experiments did not raise upstream production rate.
- BufferQueue free-slot/backpressure is closed as primary owner.
- slow Frame Build is roughly 48-55 ms/frame while measured Vulkan scopes explain only a minority.
- GPU worker is mostly starved in queue wait; active GPU-command work is not the missing interval.
- long inter-submit gap exists before NVDRV handler entry; handler/SubmitGPFIFO/locks/fence/syncpoint are tiny.
- dominant guest submitter in tested runs = `tid=0x53`, CPU share about 1-2%.
- NVDRV IPC dispatch is about 0.02-0.03 ms/request; host service scheduling is not the missing owner.
- post-submit interval is generally mostly guest KThread `Waiting`.

## Address Arbiter Stage A — COMPLETE

Within each process the dominant submitter waits on one stable gameplay key:

- victim / submitter: `tid=0x53` in tested runs
- operation: `WaitIfEqual`
- timeout: `-1`
- direct `WaitForAddress` duration reconciles essentially one-for-one with reason-level `Arbitration`.

Absolute guest VA is not process-invariant. Observed:

- `0x210adbc120`
- `0x210b5bc120`
- `0x210b1bc120`

The profiler dynamically latches the current run's first post-warmup target-thread `WaitIfEqual(timeout=-1)` address.

## Address Arbiter Stage B — COMPLETE

Stage B proved the late-waker edge:

- victim `tid=0x53`
- sole observed waker `tid=0x4f` in tested runs
- signal type `SignalAndIncrementIfEqual`
- value `1`
- count `-1`
- normal gameplay one matching signal per rendered frame
- missing/no-active/overflow `0`
- `direct WaitForAddress ~= wait-start -> matching-signal (w2s)`
- signal -> wait-return (`s2e`) is essentially zero

Therefore the long submitter AddressArbiter delay happens **before** the waker signals. Once the matching signal arrives, the victim returns essentially immediately.

## Stage C — RUNTIME COMPLETE

Runtime:

`eden_log(20260828-173023).txt`

Current run:

- dynamic wait address `0x210b5bc120`
- victim `tid=0x53`
- dynamic waker `tid=0x4f`
- waker switches `0`
- matching signal sanity counters clean

### Stable fast vs stable slow

Stable fast windows:

- frame 240, 480, 600, 720, 840
- raw swap2 = 120/120

Mean per matching signal:

- inter-signal **33.722 ms**
- waker KThread Waiting **27.708 ms**
- Stage-C residual **6.014 ms**

Stable slow windows:

- frame 1200, 1320, 1440, 1560, 1680
- raw swap3 = 120/120

Mean per matching signal:

- inter-signal **55.022 ms**
- waker KThread Waiting **34.183 ms**
- Stage-C residual **20.839 ms**

Slow-minus-fast:

- inter-signal **+21.299 ms**
- Waiting **+6.474 ms**
- residual **+14.825 ms**

At this aggregate level about 70% of the stable slowdown increment lands in the current residual and about 30% in extra KThread Waiting. This is interval attribution, not a final root-cause percentage.

### Waker named wait reasons

For `tid=0x4f`:

- Sleep `0`
- Synchronization `0`
- ConditionVar `0`
- Arbitration `0`
- Suspended `0`
- IPC only a few milliseconds total per 120-frame report

Nearly all measured waker Waiting is reason `None`.

Important semantic rule:

> Stage C `none=...` means the KThread was actually `Waiting`, but its debug wait-reason field was `None`. It does not mean CPU/runnable time.

Exact dc95 contains direct `BeginWait` paths that do not assign a debug reason, so the enum is not exhaustive. Do not claim a particular unreasoned wait site owns the waker yet.

### Signal callsite context

Matching SignalToAddress PC is overwhelmingly:

`0x85f16528`

with very few PC mismatches in stable slow windows.

LR varies materially; common/latest values include `0x85ee2b40` and `0x85ee2a8c`.

Interpretation:

- signal reaches one stable guest SVC site;
- PC may simply be the common SVC wrapper;
- current LR reference+mismatch output is insufficient to identify the dominant higher-level caller.

`lastWaitSvc=0x0` throughout and is non-informative.

## Stage C conclusion

Stage C rejects the simple hypothesis that the waker is delayed by another single named `Arbitration`, `Synchronization`, `ConditionVar`, or `Sleep` wait.

Instead the stable slow-mode signal period expansion is split between:

1. additional **unclassified KThread Waiting (`reason=None`)**, and
2. a much larger **non-Waiting residual**.

Do **not** equate residual with guest CPU work. It also includes runnable-but-unscheduled scheduler delay.

## Current causal frontier — Stage D

Exact questions:

1. How much of the 20-21 ms stable-slow residual is actual waker guest CPU time?
2. How much is runnable/unscheduled delay?
3. Which exact direct `BeginWait` site owns the waker's `reason=None` Waiting time?
4. Which LR/caller sites dominate matching SignalToAddress?

Minimal next instrumentation is defined in `NEXT_ACTION_WAKER_STAGE_D.md`:

- waker `GetCpuTime()` delta between consecutive matching signals;
- derive CPU vs runnable/unscheduled residual;
- fixed-enum attribution for only direct `BeginWait` sites that can produce `Waiting + reason=None`, dynamically waker-gated;
- top-4 LR histogram at matching SignalToAddress;
- no all-thread tracing, all-SVC tracing, per-event flood, wait/sleep insertion, priority/core changes, or GPU/cadence behavior changes.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
