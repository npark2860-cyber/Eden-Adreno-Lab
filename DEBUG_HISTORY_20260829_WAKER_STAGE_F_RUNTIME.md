# DEBUG HISTORY — Waker Stage F Runtime

Updated: 2026-08-29 KST

## Scope

Stage F runtime decomposition for the two dynamically selected signal producers of the Stage E promoted AddressArbiter key.

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Runtime log:

`eden_log(20260829-073615).txt`

No behavior-changing A/B was enabled. `x1_ab_clamp_main_swap_interval_3_to_2=false`.

## Stage F ARM64 build — SUCCESS

- workflow: `Build dc95 X1 Waker Stage F`
- run: `33239788740`
- job: `99067041921`
- attempt: `1`
- build HEAD: `309c8cc5ab430289f9c1489ec7d4b79272ad88f4`
- exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- conclusion: `success`
- artifact: `Eden-dc95-X1-waker-stage-f`
- artifact id: `9711330615`
- size: `31,411,478` bytes
- SHA-256: `f3171da4a9756864b5c3f71b3870f435a8b11b74f3ec0895479331759b71b83f`
- created: `2026-08-29T07:29:03Z`
- expires: `2026-09-12T07:29:01Z`
- rerun/retry: none

Persistent workflow was restored to manual-only after the approved run was created.

Current ARM64 authorization: **NONE**.

## Runtime identity

Environment:

- Eden `HEAD-dc95cd09ee`
- Windows 11 25H2 build 26220.9223
- Adreno X1-85
- driver 512.863.0
- Vulkan 1.3.295
- TOTK 1.2.1
- Address Arbiter attribution ON

Stage F dynamically settled on:

- tracked promoted address observed in this run: `0x210b45b39c`
- producer 0 observed TID: `0x80`
- producer 1 observed TID: `0x81`
- producer 0 active/current core: `1/1`
- producer 1 active/current core: `2/2`
- priority: `44` for both
- candidate overflow: `0` in stable windows
- tracking switch: `0` after discovery settles

These TIDs and the guest VA are runtime observations only and remain forbidden as hardcoded profiler constants.

## Stable cadence windows

Raw QueueBuffer cadence counted directly from the log:

Pure swap2 windows:

- frame 480: 120/120 swap2
- frame 600: 120/120 swap2
- frame 720: 120/120 swap2
- frame 840: 120/120 swap2
- frame 960: 120/120 swap2

Transition window excluded:

- frame 1080: 13 swap2 / 107 swap3

Pure swap3 windows:

- frame 1200: 120/120 swap3
- frame 1320: 120/120 swap3
- frame 1440: 120/120 swap3

## Stage F aggregate decomposition

Averages below are interval-count-weighted across the pure windows.

### Producer 0 — observed `tid=0x80`

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 6.111 ms | 12.185 ms | +6.074 ms |
| corrected Waiting | 5.002 ms | 7.467 ms | +2.465 ms |
| residual | 1.109 ms | 4.719 ms | +3.610 ms |
| estimated guest CPU | 1.005 ms | 4.439 ms | +3.434 ms |
| runnable-unscheduled | 0.324 ms | 0.698 ms | +0.373 ms |

Corrected wait reason per producer interval:

| reason | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| Arbitration | 4.785 ms | 7.166 ms | +2.381 ms |
| Sleep | 0.192 ms | 0.278 ms | +0.086 ms |
| ConditionVar | 0.026 ms | 0.030 ms | +0.004 ms |
| IPC | ~0.000 ms | 0.000 ms | ~0.000 ms |
| Synchronization | 0.000 ms | 0.000 ms | 0.000 ms |
| true None | 0.000 ms | 0.000 ms | 0.000 ms |

Arbitration share of corrected Waiting:

- fast: ~95.7%
- slow: ~96.0%

### Producer 1 — observed `tid=0x81`

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 7.314 ms | 14.415 ms | +7.100 ms |
| corrected Waiting | 6.072 ms | 9.119 ms | +3.047 ms |
| residual | 1.243 ms | 5.296 ms | +4.054 ms |
| estimated guest CPU | 1.121 ms | 5.025 ms | +3.904 ms |
| runnable-unscheduled | 0.348 ms | 0.702 ms | +0.354 ms |

Corrected wait reason per producer interval:

| reason | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| Arbitration | 5.847 ms | 8.729 ms | +2.881 ms |
| Sleep | 0.216 ms | 0.345 ms | +0.129 ms |
| ConditionVar | 0.018 ms | 0.031 ms | +0.014 ms |
| IPC | ~0.000 ms | 0.000 ms | ~0.000 ms |
| Synchronization | 0.000 ms | 0.000 ms | 0.000 ms |
| true None | 0.000 ms | 0.000 ms | 0.000 ms |

Arbitration share of corrected Waiting:

- fast: ~96.3%
- slow: ~95.7%

## Reconciliation with Stage E

Across the same pure windows, Stage E promoted-key signal timing rises strongly while signal-to-waker-return remains tiny.

Weighted Stage E `w2s` / `s2e`:

- observed producer `0x80` fast: `w2s ~0.564 ms`, `s2e ~0.011 ms`
- observed producer `0x80` slow: `w2s ~3.152 ms`, `s2e ~0.014 ms`
- observed producer `0x81` fast: `w2s ~0.543 ms`, `s2e ~0.010 ms`
- observed producer `0x81` slow: `w2s ~3.045 ms`, `s2e ~0.013 ms`

The recursive delay is therefore still before the producer signal. Stage F shows that the producer's own signal-to-signal cycle becomes slower in the same regime.

## Interpretation

Stage F is a **mixed** result.

For both dynamically selected producers:

1. signal-to-signal wall time roughly doubles in slow swap3;
2. corrected Waiting grows materially;
3. residual grows even more;
4. estimated guest CPU growth almost matches the residual growth across stable 120-frame aggregates;
5. runnable-unscheduled growth is small compared with CPU and Waiting growth;
6. corrected Waiting is ~96% Arbitration in both fast and slow regimes;
7. core residency remains stable in the observed reports (`0x80` on core 1, `0x81` on core 2).

Therefore Windows/host scheduler starvation is **not the primary Stage F owner**.

The slow producer cycle has two real branches:

- **producer CPU branch**: about +3.43 ms / +3.90 ms per producer interval;
- **producer upstream Arbitration branch**: about +2.38 ms / +2.88 ms per producer interval.

Do not collapse these branches into one without further attribution.

## CPU measurement caveat

`KThread::GetCpuTime()` is updated on scheduler context switches, so the currently executing slice tail can be attributed at a later boundary. `cpuOverResidual` is therefore nonzero in many individual producer intervals.

Use the multi-window aggregate trend above, not single-interval arithmetic, for CPU interpretation. In particular, `cpuAvg` and `runUnschedAvg` should not be treated as perfectly additive per-event quantities when `cpuOverResidual` is nonzero.

The aggregate slow-fast CPU increase is nevertheless stable across multiple pure swap3 windows and nearly matches the aggregate residual increase for both producers.

## Current causal chain

Current measured chain:

GPU command starvation
-> dominant guest submitter / victim
-> dynamic waker
-> promoted AddressArbiter handshake
-> two dominant producer threads
-> **producer-side CPU work + producer-side Arbitration dependency both grow in slow mode**

Signal return itself remains tiny after the producer signals.

## Next frontier

Because Stage F is mixed, preserve both branches.

Priority 1 for the next diagnostic:

> focused CPU-slice PC/LR attribution for only the dynamically selected Stage F producers, using scheduler/context-switch accounting and no all-thread PC sampler.

Reason: CPU is the largest single slow-fast increase for both producers and Stage F intentionally deferred PC/LR attribution until runtime proved CPU growth was material.

Keep open in parallel, but do not instrument simultaneously unless explicitly scoped:

> the producer corrected-Waiting branch is overwhelmingly Arbitration and should later recurse only the dominant producer `WaitForAddress` key/release owner.

The separate Stage D dynamic-waker CPU-growth branch also remains open.

No optimization is justified yet.
