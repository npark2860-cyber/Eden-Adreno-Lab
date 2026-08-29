# DEBUG HISTORY — 2026-08-29 Waker Stage H Runtime

## Scope

Runtime analysis of Stage H artifact `Eden-dc95-X1-waker-stage-h` under the same TOTK 1.2.1 gameplay conditions used for Stage G.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Runtime log:

`eden_log(20260829-103238).txt`

- size: `2,975,852` bytes
- lines: `14,872`
- SHA-256: `02e42efccd2bf2d8c8bc3f2a5432b7a149ece0fb1faf6eac813fe8b5a9b58da0`
- Eden log build string: `Eden Development Build | HEAD-dc95cd09ee-HEAD`
- game: Tears of the Kingdom 1.2.1
- host: Windows 11 25H2 build 26220.9223
- GPU: Qualcomm Adreno X1-85
- Vulkan driver: 512.863.0
- Vulkan API: 1.3.295

Behavior-changing A/Bs were OFF.

Current ARM64 authorization remains **NONE**. No build/rebuild/rerun was performed for this analysis.

## Stage H module ranges

The runtime emitted four bounded module ranges:

- `rtld`: `0x80758000-0x8075c000`
- `main`: `0x8075c000-0x84e87000`
- `subsdk0`: `0x84e87000-0x85530000`
- `sdk`: `0x85530000-0x86309000`

All four recurring Stage G top saved PC/LR contexts resolve inside `sdk`.

Canonical context identities:

| raw PC | raw LR | canonical PC | canonical LR |
|---|---|---|---|
| `0x85688528` | `0x85654a8c` | `sdk+0x158528` | `sdk+0x124a8c` |
| `0x85688420` | `0x8566178c` | `sdk+0x158420` | `sdk+0x13178c` |
| `0x85688528` | `0x85654b40` | `sdk+0x158528` | `sdk+0x124b40` |
| `0x85688528` | `0x85657058` | `sdk+0x158528` | `sdk+0x127058` |

This rejects Stage H decision-map case B for the observed dominant family: the reported contexts are not producer-specific game `main` work paths.

The raw Stage G addresses from the prior run and the Stage H run shifted together by exactly `0x88a000`, while their new canonical module-relative identities are stable. This validates the ASLR-normalization premise.

Interpretation remains strict: Stage G/H attributes each completed scheduler slice to its saved guest PC/LR at switch-out. These identities are slice-end execution contexts/call-path evidence, not literal instruction residency time.

## Cadence classification

Raw QueueBuffer windows:

- frame 120: 110 swap2 / 10 swap3
- 240: 120 swap2, but Stage F/G not armed
- 360: 98 swap2 / 22 swap3
- 480: 113 swap2 / 7 swap3; first armed window, one `missingStart` per producer
- 600: 115 swap2 / 5 swap3
- 720: 117 swap2 / 3 swap3
- 840: 120 swap2
- 960: 114 swap2 / 6 swap3; transition/hitch window, excluded
- 1080: 120 swap3
- 1200: 120 swap3
- 1320: 120 swap3

Stable comparison used for aggregate attribution:

- fast / near-pure swap2: frames `600, 720, 840` = 352/360 swap2 (`97.8%`), all Stage G sanity counters clean
- strict pure-swap2 check: frame `840`
- transition excluded: frame `960`
- slow / pure swap3: frames `1080, 1200, 1320` = 360/360 swap3

Frame 480 is not used in the primary aggregate because it is the first armed window and reports `missingStart=1` for each producer. The counter is zero thereafter.

## Stage F reproduction in this run

Interval-count-weighted fast (`600,720,840`) -> slow (`1080,1200,1320`):

### Producer 0

- inter-signal: `5.881 -> 14.339 ms`, `+8.458`
- corrected Waiting: `4.958 -> 9.352 ms`, `+4.394`
- residual: `0.923 -> 4.988 ms`, `+4.065`
- guest CPU: `0.864 -> 4.662 ms`, `+3.797`
- runnable-unscheduled: `0.270 -> 0.794 ms`, `+0.524`
- Arbitration: `4.780 -> 8.962 ms`, `+4.182`

### Producer 1

- inter-signal: `7.713 -> 16.669 ms`, `+8.956`
- corrected Waiting: `6.489 -> 11.276 ms`, `+4.787`
- residual: `1.223 -> 5.393 ms`, `+4.170`
- guest CPU: `1.066 -> 5.144 ms`, `+4.078`
- runnable-unscheduled: `0.384 -> 0.689 ms`, `+0.305`
- Arbitration: `6.283 -> 10.894 ms`, `+4.611`

Thus the mixed producer CPU-growth + producer Arbitration-growth branch reproduces again. Runnable-unscheduled remains much smaller than either branch.

## Stage G exact CPU reconciliation

Using the canonical Stage G scheduler tick domain (`19.2 MHz`) and the same producer interval counts:

| producer | Stage G fast | Stage F fast | Stage G slow | Stage F slow |
|---|---:|---:|---:|---:|
| 0 | `0.86458 ms` | `0.86448 ms` | `4.66077 ms` | `4.66154 ms` |
| 1 | `1.06624 ms` | `1.06640 ms` | `5.14345 ms` | `5.14406 ms` |

Stable-window Stage G sanity:

- `unknownN=0`
- `identitySwitch=0`
- `missingStart=0`
- `malStart=0`
- `malTicks=0`
- `clockMismatch=0`

Therefore the Stage G instrumentation remains reconciled in the Stage H binary.

## Canonical context growth

Per producer interval, fast (`600,720,840`) -> slow (`1080,1200,1320`):

### Producer 0

Total Stage G CPU growth: `+3.796 ms`.

- `sdk+0x158528 / sdk+0x124a8c`: `0.396 -> 1.341`, `+0.945 ms` = `24.9%` of CPU growth
- `sdk+0x158420 / sdk+0x13178c`: `0.073 -> 0.822`, `+0.749 ms` = `19.7%`
- `sdk+0x158528 / sdk+0x124b40`: `0.096 -> 0.581`, `+0.485 ms` = `12.8%`
- `sdk+0x158528 / sdk+0x127058`: `0.134 -> 0.233`, `+0.098 ms` = `2.6%`
- fixed-64-slot overflow: `0.128 -> 1.537`, `+1.409 ms` = `37.1%`

The four visible contexts + overflow explain about `97.1%` of CPU growth.

### Producer 1

Total Stage G CPU growth: `+4.077 ms`.

- `sdk+0x158528 / sdk+0x124a8c`: `0.509 -> 1.392`, `+0.882 ms` = `21.6%`
- `sdk+0x158420 / sdk+0x13178c`: `0.095 -> 0.910`, `+0.815 ms` = `20.0%`
- `sdk+0x158528 / sdk+0x124b40`: `0.107 -> 0.327`, `+0.220 ms` = `5.4%`
- `sdk+0x158528 / sdk+0x127058`: `0.100 -> 0.189`, `+0.088 ms` = `2.2%`
- overflow: `0.213 -> 2.125`, `+1.912 ms` = `46.9%`

The four visible contexts + overflow explain about `96.1%` of CPU growth.

Overflow is still material, but it no longer prevents identifying the dominant normalized family: all visible recurring contexts are in the same `sdk` module, and two PC endpoints (`sdk+0x158528`, `sdk+0x158420`) dominate the visible growth. Therefore Stage H decision-map case D is not selected yet; do not widen the 64-slot table before resolving the existing SDK path semantics.

## Stage D dynamic-waker cross-join

The separate dynamic-waker branch now has direct module/caller evidence joining it to the same SDK endpoint family.

Across the stable windows, Stage D reports:

- saved PC: `0x85688528` = `sdk+0x158528`
- dominant LR0: `0x85654b40` = `sdk+0x124b40`
- dominant LR1: `0x85654a8c` = `sdk+0x124a8c`
- occasional LR: `0x8566178c` = `sdk+0x13178c`
- occasional LR: `0x8566f364` = `sdk+0x13f364`

This is stronger than the Stage G-only observation: the two selected producers and the dynamic waker repeatedly end scheduler slices in the same Nintendo SDK path family.

The accounting branches must still remain separate:

1. producer CPU growth;
2. producer Arbitration growth;
3. dynamic-waker CPU growth;
4. dynamic-waker Arbitration growth.

Shared SDK endpoints establish a common runtime/synchronization path, not yet which caller or operation owns the causal slowdown.

Current-run Stage D fast (`600,720,840`) -> slow (`1080,1200,1320`):

- inter-signal: `34.397 -> 65.358 ms`
- corrected Waiting: `28.325 -> 39.333 ms`
- residual: `6.073 -> 26.025 ms`
- estimated waker CPU: `5.871 -> 25.840 ms`, `+19.969`
- runnable-unscheduled: `0.232 -> 0.244 ms`, only `+0.012`
- Arbitration per interval: `5.837 -> 37.739 ms`

Scheduler starvation therefore remains rejected for the waker in this run as well.

## Stage E timing cross-check

Promoted-key signal timing, signal-count weighted:

Producer 0:

- fast w2s: `0.458 ms`
- slow w2s: `3.846 ms`
- fast s2e: `0.011 ms`
- slow s2e: `0.014 ms`

Producer 1:

- fast w2s: `0.560 ms`
- slow w2s: `3.441 ms`
- fast s2e: `0.012 ms`
- slow s2e: `0.013 ms`

The recursive delay remains before producer signal, not after signal return.

## Decision

Stage H decision-map result: **A selected**.

> The dominant saved PC/LR family normalizes to one shared SDK/runtime module and a small caller set.

Observed dominant module is `sdk`; no dominant top context resolves to `main` or `subsdk0`.

Do not optimize yet. Next resolve the exact semantics of:

- `sdk+0x158528`
- `sdk+0x158420`
- callers `sdk+0x124a8c`, `sdk+0x124b40`, `sdk+0x127058`, `sdk+0x13178c`
- secondary waker caller `sdk+0x13f364`

before adding caller depth or widening the Stage G histogram.

## Minimal next evidence

No new ARM build is required to obtain the next evidence.

Exact dc95 already supports `Settings::values.dump_nso` / UI `Dump Decompressed NSOs`. In exact dc95, `PatchManager::PatchNSO()` writes the flattened decompressed image to the configured dump root under `/nso/<name>-<build_id>.nso`.

For this runtime, the `sdk` build ID is:

`B9046C31EB5D31271BE970FE732D38DF49C6AA21`

Expected dump filename:

`sdk-B9046C31EB5D31271BE970FE732D38DF49C6AA21.nso`

Next action is to obtain that single SDK NSO and disassemble/function-boundary-map the canonical offsets above offline. This avoids a new scheduler hook, a caller-depth profiler, a larger histogram, and any ARM64 rebuild until the current evidence is exhausted.
