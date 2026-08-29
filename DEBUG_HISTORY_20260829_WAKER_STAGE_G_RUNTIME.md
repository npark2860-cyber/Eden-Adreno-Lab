# DEBUG HISTORY — 2026-08-29 Waker Stage G Runtime

## Scope

Stage G attributes only the Stage F producer CPU branch to saved guest `PC/LR` execution contexts at exact dc95 scheduler context-switch boundaries.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Source branch used by the successful build:

`exp/x1-waker-stage-g-producer-cpu-attribution`

Build source HEAD:

`573ba79f2a0a0ba534993d314e113d2f9fb7d1c5`

Runtime log:

`eden_log(20260829-093642).txt`

Observed environment:

- TOTK `1.2.1`
- Windows 11 25H2 build `26220.9223`
- Qualcomm Adreno X1-85
- Qualcomm Vulkan driver `512.863.0`
- Vulkan `1.3.295`

Absolute runtime TIDs, guest addresses, PC and LR values below are observations only. Do not hardcode them.

## Authorized ARM64 build — SUCCESS

The first Stage G ARM64 authorization had already been consumed by pre-configure failure run `33243420048`; that failure is recorded separately in `DEBUG_HISTORY_20260829_WAKER_STAGE_G_ARM_PRECHECK_FAILURE.md`.

A fresh authorization was then used for exactly one new attempt:

- workflow: `Build dc95 X1 Waker Stage G`
- run: `33244399213`
- job: `99079231424`
- attempt: `1`
- event: `workflow_dispatch`
- build HEAD: `573ba79f2a0a0ba534993d314e113d2f9fb7d1c5`
- exact dc95 verification: success
- retained Stage A-F reconstruction: success
- Stage G transplant: success
- Stage G pre-configure verification: success
- MSYS2 CLANGARM64 setup: success
- configure: success
- ARM64 compile: success
- package: success
- upload: success
- conclusion: success
- retry/rerun: none

Artifact:

- name: `Eden-dc95-X1-waker-stage-g`
- artifact id: `9712697731`
- size: `31,416,415` bytes
- SHA-256: `38ccf37cc28cb5123b5c4018117b4f53a651bc0e77488955dddaf9093c98a7a1`

Current ARM64 authorization after this attempt: **NONE**.

## Runtime cadence classification

Raw QueueBuffer cadence by 120-frame Stage G report window:

| report frame | swap2 | swap3 | classification |
|---:|---:|---:|---|
| 120 | 109 | 11 | startup / mixed |
| 240 | 120 | 0 | pure swap2, Stage F/G not armed yet |
| 360 | 94 | 26 | mixed / load transition |
| 480 | 120 | 0 | pure swap2 |
| 600 | 120 | 0 | pure swap2 |
| 720 | 120 | 0 | pure swap2 |
| 840 | 120 | 0 | pure swap2 |
| 960 | 44 | 76 | transition / hitch — exclude |
| 1080 | 0 | 120 | pure swap3 |
| 1200 | 0 | 120 | pure swap3 |
| 1320 | 0 | 120 | pure swap3 |

Stable comparison used below:

- pure swap2: frames `480, 600, 720, 840`
- excluded transition: frame `960`
- pure swap3: frames `1080, 1200, 1320`

Stage F discovery settled on this run at:

- promoted address observed `0x210b65b39c`
- producer 0 observed TID `0x80`
- producer 1 observed TID `0x81`
- observed producer cores `1 / 2`
- priority `44 / 44`
- `candidateOverflow=0`
- `trackingSwitch=0`

## Stage F producer trend reproduced

Interval-count-weighted stable comparison for producer 0:

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 6.001 ms | 11.525 ms | +5.524 ms |
| corrected Waiting | 5.017 ms | 7.171 ms | +2.153 ms |
| residual | 0.984 ms | 4.354 ms | +3.369 ms |
| Stage F CPU | 0.922 ms | 4.096 ms | +3.173 ms |
| runnable-unscheduled | 0.257 ms | 0.628 ms | +0.371 ms |
| Arbitration | 4.833 ms | 6.864 ms | +2.031 ms |

Producer 1:

| metric | pure swap2 | pure swap3 | slow-fast |
|---|---:|---:|---:|
| inter-signal | 7.402 ms | 13.833 ms | +6.431 ms |
| corrected Waiting | 6.185 ms | 8.912 ms | +2.727 ms |
| residual | 1.216 ms | 4.921 ms | +3.705 ms |
| Stage F CPU | 1.089 ms | 4.679 ms | +3.589 ms |
| runnable-unscheduled | 0.357 ms | 0.678 ms | +0.321 ms |
| Arbitration | 5.981 ms | 8.572 ms | +2.592 ms |

The Stage F mixed conclusion reproduces: producer CPU and producer Arbitration both grow materially, while runnable-unscheduled growth remains much smaller.

## Stage G reconciles with Stage F CPU

Stage G scheduler `cpuTicks` were converted only for analysis using the exact CoreTiming tick domain. The stable aggregate per producer interval is:

| producer | Stage G swap2 | Stage F swap2 | Stage G swap3 | Stage F swap3 |
|---|---:|---:|---:|---:|
| 0 | 0.92233 ms | 0.92206 ms | 4.09551 ms | 4.09553 ms |
| 1 | 1.08955 ms | 1.08929 ms | 4.67808 ms | 4.67864 ms |

This is an excellent reconciliation. Stage G is measuring the same CPU branch exposed by Stage F aggregate `GetCpuTime()` accounting.

Stage G sanity counters in every armed stable report:

- `unknownN=0`
- `identitySwitch=0`
- `missingStart=0`
- `malStart=0`
- `malTicks=0`
- `clockMismatch=0`
- producer priority remained `44`
- producer cores remained `1 / 2`

Therefore decision-map case C — instrumentation mismatch — is rejected.

## Exact recurring saved PC/LR contexts

Important interpretation rule:

Stage G assigns one completed scheduler slice's exact `tick_diff` to the **saved guest PC/LR observed when that slice switches out**. Therefore the numbers below mean "CPU slices ending in this guest execution context". They do **not** mean the CPU spent the entire slice executing the instruction at that PC.

### Producer 0

Stable per-interval CPU attribution:

| saved PC / LR | swap2 | swap3 | slow-fast | share of total CPU growth |
|---|---:|---:|---:|---:|
| `0x85f12420 / 0x85eeb78c` | 0.0741 ms | 0.8288 ms | +0.7547 ms | 23.8% |
| `0x85f12528 / 0x85edea8c` | 0.4257 ms | 1.1118 ms | +0.6860 ms | 21.6% |
| `0x85f12528 / 0x85edeb40` | 0.1044 ms | 0.5503 ms | +0.4459 ms | 14.1% |
| `0x85f12528 / 0x85ee1058` | 0.1425 ms | 0.1978 ms | +0.0553 ms | 1.7% |
| fixed-table overflow | 0.1175 ms | 1.2718 ms | +1.1543 ms | 36.4% |

The four reported exact contexts plus overflow account for about `97.6%` of producer 0 CPU growth.

### Producer 1

| saved PC / LR | swap2 | swap3 | slow-fast | share of total CPU growth |
|---|---:|---:|---:|---:|
| `0x85f12528 / 0x85edea8c` | 0.4948 ms | 1.3304 ms | +0.8356 ms | 23.3% |
| `0x85f12420 / 0x85eeb78c` | 0.1031 ms | 0.9116 ms | +0.8085 ms | 22.5% |
| `0x85f12528 / 0x85edeb40` | 0.1208 ms | 0.3400 ms | +0.2192 ms | 6.1% |
| `0x85f12528 / 0x85ee1058` | 0.1143 ms | 0.1812 ms | +0.0669 ms | 1.9% |
| fixed-table overflow | 0.1886 ms | 1.7638 ms | +1.5753 ms | 43.9% |

The four reported exact contexts plus overflow account for about `97.7%` of producer 1 CPU growth.

### What is concentrated vs diffuse

Two recurring exact context pairs alone explain about `45%` of slow-minus-fast CPU growth for both producers.

The four reported contexts use only two saved PC values:

- observed `0x85f12528`
- observed `0x85f12420`

Those four exact PC/LR contexts explain about:

- `61%` of producer 0 CPU growth
- `54%` of producer 1 CPU growth

However the fixed `64`-context histogram overflow becomes material in slow mode:

- producer 0 overflow share of total slow CPU ~= `31%`
- producer 1 overflow share of total slow CPU ~= `38%`

So do not claim that one exact PC/LR pair owns the whole CPU branch. The correct conclusion is a small repeated saved-PC family plus a material long tail.

## Important cross-branch observation

The same saved PCs and dominant LRs also appear in the separate Stage D dynamic-waker reports.

For the observed waker `tid=0x4f`, Stage D repeatedly reports saved `pc=0x85f12528`, with dominant LR values including observed `0x85edeb40` and `0x85edea8c`; one slow window reports saved `pc=0x85f12420`.

Therefore the recurring Stage G endpoint is likely a shared guest runtime / synchronization execution path, not enough evidence for a producer-specific game-work function.

Do not merge the producer CPU branch with the Stage D waker CPU branch merely because the saved endpoint is shared. Module and call-path mapping is required first.

## Stage E promoted-key timing still agrees

Across the same stable windows, promoted-key wait-start -> producer signal remains approximately:

- observed producer 0: `0.477 ms -> 3.124 ms`
- observed producer 1: `0.522 ms -> 2.952 ms`

Signal -> waker return remains about `0.01 ms`.

This preserves the earlier conclusion: the recursive delay is before producer signal, not after it.

## Runtime decision

Stage G decision map result:

- C is rejected: Stage G CPU ticks reconcile with Stage F and sanity counters are clean.
- B is not a sufficient description: the growth is not uniformly diffuse; a small repeated saved-PC family explains a majority of the measured growth.
- A is selected **with overflow caveat**: map the recurring exact guest contexts to ASLR-safe module-relative execution paths before any optimization.

No optimization is justified yet.

## Source-only mapping path found in exact dc95

Exact dc95 already maintains an NSO module map during application load:

- `AppLoader_DeconstructedRomDirectory::Load()` loads static modules in order and stores `modules[load_addr] = module_name`.
- `AppLoader_DeconstructedRomDirectory::ReadNSOModules()` exposes that map.
- `AppLoader_NCA::ReadNSOModules()` forwards to the directory loader.

This is the correct source for ASLR-safe normalization.

The next focused step does not need a broad profiler or per-switch logging. It should obtain the existing NSO module bases once and normalize only the already-selected Stage G top `PC/LR` contexts to `module+offset`.

Current absolute observations such as `0x85f12528` must not be hardcoded because application ASLR changes between launches.

## Next action

See `NEXT_ACTION_WAKER_STAGE_H.md`.

Stage H should be source-first and minimal:

1. reuse the existing loader NSO module map;
2. emit or expose one-time module ranges only under the existing focused diagnostic gate;
3. map Stage G selected-producer saved PC/LR to module-relative offsets;
4. preserve dynamic Stage F producer selection;
5. no all-thread profiler, no behavior mutation, no optimization;
6. do not widen the Stage G 64-slot table until module mapping shows that widening is actually necessary.

No new ARM64 build is authorized.