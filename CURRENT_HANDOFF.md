# CURRENT HANDOFF — Eden Adreno X1 Waker Attribution

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- current source branch: `exp/x1-address-arbiter-signal-owner`
- Stage B dynamic-latch runtime record: `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_SIGNAL_OWNER.md`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Latest ARM64 build — SUCCESS

Dynamic-address Stage B build:

- run `33168281215`
- job `98838856202`
- attempt `1`
- build branch `exp/x1-address-arbiter-signal-owner-build`
- build HEAD `b2dbc9dbe7cb69a5856850d5d60750355f186b19`
- conclusion `success`
- exact dc95 verification `success`
- dynamic-latch verification `success`
- configure `success`
- ARM64 compile `success`
- package `success`
- artifact upload `success`
- artifact `Eden-dc95-X1-address-arbiter-dynamic-latch`
- artifact id `9685245645`
- size `31,385,379` bytes
- SHA-256 `a421cb6beaa7528ba024a1fee943c2c9a80bbb353142963e0391d2d00e67cfd7`

The temporary one-shot ARM64 workflow was removed after the successful run. No rerun occurred.

The persistent source-branch workflow remains manual-only (`workflow_dispatch`).

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
- dominant guest submitter = `tid=0x53`, essentially 100% candidate submits, CPU share about 1-2%.
- NVDRV IPC dispatch is about 0.02-0.03 ms/request; host service scheduling is not the missing owner.
- post-submit interval is generally 96-99% guest KThread `Waiting`.

## Address Arbiter Stage A — COMPLETE

Corrected Stage A runtime proved one stable gameplay wait key within a process:

- victim / dominant submitter: `tid=0x53`
- operation: `WaitIfEqual` (`ArbitrationType=2`)
- timeout: `-1`
- one active gameplay key
- no post-warmup slot overflow
- no timeout completions
- direct `WaitForAddress` duration reconciles essentially one-for-one with reason-level `Arbitration`.

The absolute guest address is **not process-invariant**. Observed across runs:

- `0x210adbc120`
- `0x210b5bc120`
- `0x210b1bc120`

Therefore never hardcode the absolute guest VA across runs. The profiler now dynamically latches the current run's first post-warmup target-thread `WaitIfEqual(timeout=-1)` address.

## Address Arbiter Stage B — COMPLETE

Runtime:

`eden_log(20260828-122253).txt`

Dynamic target in this run:

- victim: `tid=0x53`
- wait address: **`0x210b1bc120`**
- wait: `WaitIfEqual`
- timeout: `-1`

Matching signal owner:

- sole observed waker: **`tid=0x4f`**
- signal type: **`SignalAndIncrementIfEqual`** (`incEq`)
- value argument: `1`, stable
- count argument: `-1`, stable
- normal gameplay: one matching signal per rendered frame
- signal slots: `1`
- post-warmup missing/no-active/overflow: `0`

Representative timing:

| frame | raw swap2 | raw swap3 | direct wait avg | wait -> signal (`w2s`) | signal -> return (`s2e`) |
|---:|---:|---:|---:|---:|---:|
| 240 | 120 | 0 | 1.331 ms | 1.322 ms | 0.009 ms |
| 360 | 98 | 22 | 25.090 ms | 25.078 ms | 0.013 ms |
| 1560 | 120 | 0 | 1.072 ms | 1.062 ms | 0.011 ms |
| 1800 | 15 | 105 | 70.368 ms | 70.270 ms | 0.098 ms |
| 1920 | 0 | 120 | 40.185 ms | 40.177 ms | 0.008 ms |
| 2040 | 0 | 120 | 45.026 ms | 45.020 ms | 0.007 ms |
| 2160 | 0 | 120 | 50.797 ms | 50.778 ms | 0.019 ms |

At report precision, `direct wait ~= w2s + s2e` to within about `0.001 ms` average per call.

Therefore:

> `tid=0x53` is not spending the 40-70 ms slow-regime delay after being signaled. Almost the entire synchronous wait occurs **before** the matching signal. `tid=0x4f` is the producer/waker whose `SignalToAddress` arrives late; once it signals, `tid=0x53` returns essentially immediately.

This closes the late-waker-vs-wake-completion question.

## Current causal frontier — Stage C

Exact next question:

> What is guest thread `tid=0x4f` doing between consecutive matching signals, and which state/wait/SVC or guest code path becomes long before `SignalToAddress`?

Next instrumentation must remain narrow and observation-only:

1. dynamically latch the current run's signal-owner TID from the exact target-address signal; do not hardcode `0x4f` across runs without proof;
2. attribute only that waker thread between consecutive matching signals;
3. aggregate KThread wait reasons and runnable/CPU residual for the waker;
4. retain current/last SVC attribution for that waker if cheap;
5. capture guest PC/LR at the matching `SignalToAddress` call site if accessible cheaply and read-only;
6. compare fast swap2, transition, and stable swap3 windows.

Do **not** add all-thread scheduler tracing, a generic all-SVC profiler, per-event log flood, waits/sleeps/locks, thread-priority/core changes, or GPU/BufferQueue/cadence behavior changes.

Do not chase `None` unless a controlled stable-slow window shows the proven waker->signal edge is small while the frame remains slow.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
