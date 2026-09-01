# DEBUG HISTORY — ARM64 Exclusive Guest-PC Attribution Implemented

Date: 2026-09-02 KST

## Scope

This record closes the offline implementation step that followed the LDXR+STXR runtime measurement.

No Windows ARM64 build, rerun, or runtime was started by this step.

Current ARM64 authorization after this work: **NONE**.

Exact Eden baseline remains immutable:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Experiment branch:

`exp/x1-arm64-exclusive-pc-attribution`

## Prior runtime result that motivated this step

Authorized LDXR+STXR build/run:

- workflow run `33524417121`
- attempt `1`
- workflow head `1e1c8bc4574e3e8540630756eb8417a43d874577`
- result: **SUCCESS**
- retry/rerun: none

Runtime log:

`eden_log(20260901-155830).txt`

The runtime retained exact TOTK 1.2.1 main build ID:

`9B4E43650501A4D4489B4BBFDB740F26AF3CF85`

Closed runtime findings:

1. LDXR `ReadAndMark` is a material part of the ARM64 exclusive callback cost and represents roughly 47% of measured exclusive read+write time in the compared windows.
2. Combined selected-producer exclusive read+write aggregate CPU time increased from about `3.458 ms/frame` in the compared fast windows to about `4.571 ms/frame` in the compared slow windows (`~1.322x`). This is aggregate producer CPU time, not a serial frame stall.
3. The main amplification is operation-count growth, not a retry storm or an extreme per-operation latency increase.
4. P0 read/write attempts increased by about `1.20x`; P1 by about `1.25x`.
5. Roughly `94-96%` of measured exclusive time is 32-bit traffic.
6. STXR failure-rate growth is small and does not support a retry-storm explanation.
7. Exclusive read+write is material, around `10-12%` of selected-producer CPU wall in representative slow windows, but is not large enough to be the sole slowdown owner.

Therefore the next unresolved question became:

**Which exact guest instruction sites generate the extra 32-bit exclusive traffic in slow cadence?**

## Exact guest-PC source discovered in Dynarmic IR

No JIT-state guess or stack walk is required for first-stage attribution.

Exact dc95 A64 IR already emits the current A64 location descriptor as argument 0 for exclusive operations:

`ExclusiveReadMemory32(..., ImmCurrentLocationDescriptor(), vaddr, acc_type)`

The ARM64 callback-only emitter previously ignored that argument when preparing the exclusive-read callback.

The new diagnostic layer preserves and forwards this already-existing exact location descriptor:

`PrepareForCall({}, args[1], args[0])`

ABI meaning:

- X0 remains reserved for the trampoline's `conf` pointer;
- X1 carries guest virtual address;
- X2 carries the exact A64 location descriptor already attached to the IR operation.

The existing exclusive-read trampoline is extended only diagnostically to receive that descriptor and derive:

`A64::LocationDescriptor{IR::LocationDescriptor{location_descriptor}}.PC()`

This yields the exact guest PC of the LDXR operation rather than the RunThread entry PC or a guessed block owner.

## New PC attribution layer

Added:

- `src/core/x1_arm64_exclusive_pc_profiler.h`
- `tools/adreno_lab/transplant_dc95_arm64_exclusive_pc_attribution.py`
- `tools/adreno_lab/analyze_x1_arm64_exclusive_pc_attribution.py`

Stage K wrapper now chains:

`Stage K -> existing ARM64 exclusive attribution -> new exclusive guest-PC attribution`

The existing `[X1-XEXCL]` exact LDXR/STXR count/time record is preserved unchanged.

The new layer uses a separate prefix:

`[X1-XEXCLPC]`

## Sampling design

The PC layer intentionally does not record every exclusive operation.

Current design:

- selected Stage F producers only;
- **32-bit LDXR only** for the first attribution pass;
- sample rate: `1/16`;
- fixed PC table: `512` slots per producer;
- bounded linear probe: `8` slots;
- report interval: `120` frames;
- report top count: `12` PC sites;
- fixed-memory, no dynamic allocation in the callback hot path;
- separate sampled PC counters from the exact `[X1-XEXCL]` totals.

Sampling occurs only after the existing exact read timing has been recorded, so the prior exact total record remains the primary count/time measurement.

Output summary contains:

- sample rate;
- sampled count and sampled time;
- top-site sampled count/time coverage;
- dropped samples;
- occupied PC slots.

Each ranked row contains:

- absolute runtime guest PC;
- sampled count;
- sampled time;
- sampled average ns.

The analyzer consumes `[X1-WAKERH]` module ranges from the same log and normalizes absolute runtime PCs to durable:

`module+offset`

No ASLR-dependent raw address should be retained as semantic knowledge.

## Static validation

Temporary Ubuntu exact-dc95 validator:

- first run `33531722117`: transform application passed, final verifier failed because a verifier-only string count incorrectly counted both the definition and use of `CallbackOnlyEmitExclusiveWriteMemory`;
- no source transform failure occurred in that run;
- verifier assertion was narrowed to the exact function definition count;
- second run `33531976983`: **SUCCESS**.

The successful validator proved on exact dc95 fixture:

- Python scripts compile;
- existing `ReadAndMark<T>` count remains exactly one;
- existing `ReadAndMark<Vector>` count remains exactly one;
- existing `DoExclusiveOperation<T>` count remains exactly one;
- existing `DoExclusiveOperation<Vector>` count remains exactly one;
- generic and 128-bit read trampolines each receive the location descriptor exactly once;
- exact A64 PC extraction exists exactly twice, generic + 128-bit;
- write path remains structurally untouched by the PC layer;
- existing exact `X1Arm64ExclusiveProfiler::RecordRead` path remains once;
- existing exact `RecordWrite` path remains once;
- sampled PC record path exists once;
- no priority/affinity/reschedule/yield/sleep/QueueBuffer behavior changes were introduced.

The temporary validator workflow was removed immediately after success.

## Final branch diff scope

After temporary validator deletion, comparison against base

`784f098888e1d724152f0c55bc95890d50afae00`

contained only four intended paths:

1. `src/core/x1_arm64_exclusive_pc_profiler.h` — added
2. `tools/adreno_lab/analyze_x1_arm64_exclusive_pc_attribution.py` — added
3. `tools/adreno_lab/transplant_dc95_arm64_exclusive_pc_attribution.py` — added
4. `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py` — minimal chain connection

No persistent workflow file remains changed by this implementation step.
No Eden baseline change occurred.
No ARM build occurred.

## Immediate next action

Requires a fresh explicit Windows ARM64 authorization.

If authorized:

1. perform exactly one ARM64 build/run attempt from `exp/x1-arm64-exclusive-pc-attribution`;
2. do not retry on failure;
3. collect a runtime log containing `[X1-XEXCLPC]` plus existing `[X1-XEXCL]`, `[X1-WAKERH]`, and Stage K records;
4. use actual cadence windows from that same runtime;
5. normalize top guest PCs to `module+offset`;
6. map dominant `main+offset` PC sites offline against the exact TOTK 1.2.1 NSO;
7. test whether slow-only/additional 32-bit exclusive traffic falls inside or beneath the already-closed `gsys::SystemTask`, EventModuleSubWorker, ActorAIGroupMgr::Job, or another owner.

Do not create Stage L and do not implement a behavior-changing optimization from exclusive suspicion alone.
