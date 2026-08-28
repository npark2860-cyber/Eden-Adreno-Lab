# CURRENT HANDOFF — Eden Adreno X1 Address Arbiter Signal Owner

Updated: 2026-08-28 KST

## Fixed baseline

- repository: `npark2860-cyber/Eden-Adreno-Lab`
- exact Eden source: `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`
- immutable control: `lab/dc95-arm64-baseline`
- Stage A branch: `exp/x1-address-arbiter-attribution`
- current Stage B source branch: `exp/x1-address-arbiter-signal-owner`
- Stage B source anchor before build trigger: `5709778bc0459887fbd7ab55232f9fcebbe20e2e`
- Stage B ARM64 build HEAD: `f7391ee756a748fad61dcd07b535649b54057862`

Never change the exact Eden baseline without explicit baseline-change approval.

**ARM64 build rule: no build/rebuild/rerun without fresh explicit user authorization. One authorization = exactly one attempt. Current authorization: NONE.**

## Stage B ARM64 build — SUCCESS

Approved one-shot build:

- run `33164528739`
- job `98826665494`
- attempt `1`
- build HEAD `f7391ee756a748fad61dcd07b535649b54057862`
- conclusion `success`
- configure `success`
- ARM64 compile `success`
- package `success`
- artifact upload `success`
- artifact `Eden-dc95-X1-address-arbiter-attribution`
- artifact id `9683706155`
- size `31,386,491` bytes
- SHA-256 `586dc8edf5bdff7102a0fb403363efc26538209d21728b238cdd5e31df8e3e5e`

The build-trigger commit differs from the Stage B source anchor only by the temporary one-shot ARM64 workflow file. The Stage B source itself is the same. The temporary ARM64 workflow was removed after the successful build. No rerun was performed.

Persistent workflow remains manual-only (`workflow_dispatch`).

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

Corrected runtime:

`eden_log(20260828-102127).txt`

Proven stable gameplay wait key:

- target guest thread: `tid=0x53`
- guest address: **`0x210adbc120`**
- operation: **`WaitIfEqual`** (`ArbitrationType=2`)
- timeout: **`-1`**
- timeout completions: `0`
- alternate gameplay address/type keys: none observed
- post-warmup slot overflow: `0`

The same exact key persists across fast swap2, transition, and stable swap3 states.

Representative direct wait averages:

- frame 840: `1.027 ms`, raw swap2 `120/120`
- frame 960: `3.601 ms`, mostly swap2
- frame 1080: `61.725 ms`, swap3 majority
- frame 1200: `45.593 ms`, raw swap3 `120/120`
- frame 1320: `41.227 ms`, raw swap3 `120/120`
- frame 1440: `40.159 ms`, raw swap3 `120/120`

Direct `WaitForAddress` duration reconciles essentially exactly with the existing reason-level `Arbitration` bucket (correlation approximately `0.999999`).

Therefore:

> The dominant GPU submitter is delayed by one stable once-per-frame guest `WaitForAddress(0x210adbc120, WaitIfEqual, timeout=-1)`. Its duration expands sharply in the slow regime. The blocked synchronization object/key is known; the producer/waker is the remaining causal question.

Full Stage A record:

- `DEBUG_HISTORY_20260828_ADDRESS_ARBITER_CORRECTED.md`
- `NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md`

## Stage B implementation — exact-address signal owner

Stage B is observation-only and reuses the existing Address Arbiter diagnostic control.

It instruments only `SignalToAddress` where:

`address == 0x210adbc120`

It records aggregated `[X1-ADDRSIG]` data per 120 rendered frames:

- signaling guest thread ID
- SignalType
- count argument
- relevant value argument
- calls/result status
- wait-start -> matching signal timing (`w2s`)
- matching signal -> target wait return timing (`s2e`)
- unmatched/cross-generation counters for sanity

No all-address signal tracing, generic SVC profiler, scheduler tracing, new locks/waits/sleeps, priority/core changes, or GPU/BufferQueue/cadence policy changes were added.

Ubuntu exact-dc95 static verification run `33164398004` succeeded before the ARM64 build. It verified transplant anchors, exact wait/signal call counts, and unchanged signal/wait semantics.

## Current next runtime question

Run the Stage B artifact with the same controlled TOTK 1.2.1 scenario.

Enable:

- `X1 Log: Address Arbiter Attribution`
- `X1 Log: Guest Post Wait Attribution`
- the existing correlation logs needed to compare cadence/submit timing

Keep all behavioral A/B controls OFF, especially swap3->2 clamp.

Primary output: `[X1-ADDRSIG]`.

Answer only:

1. which guest thread ID signals `0x210adbc120`?
2. is it the sole/dominant signaler across fast and slow windows?
3. which SignalType/count/value is used?
4. is there approximately one matching signal per rendered frame?
5. does `wait-start -> signal (w2s)` expand from low ms to roughly the same 40-60 ms seen in slow `WaitForAddress`?
6. does `signal -> wait-return (s2e)` remain near-zero?

If `w2s` owns the long wait and `s2e` is tiny, the next causal target is the identified waker thread's work immediately before `SignalToAddress`.

If `s2e` is unexpectedly large, do not assume late producer; inspect AddressArbiter wake/scheduling semantics minimally.

Do not claim the final root cause until this runtime identifies the waker and timing relationship.

## ARM64 status

Current ARM64 build authorization: **NONE**.

Do not trigger, rerun or rebuild any ARM64 workflow until the user gives fresh explicit authorization for exactly one attempt.
