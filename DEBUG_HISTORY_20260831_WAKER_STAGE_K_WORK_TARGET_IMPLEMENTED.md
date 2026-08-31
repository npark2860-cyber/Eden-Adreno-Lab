# DEBUG HISTORY — Stage K Work-Target Identity Implemented / Ubuntu Static Validation

Date: 2026-08-31 KST

## Scope

Implement the previously approved Stage K work-target identity design without creating Stage L and without changing runtime behavior.

Fixed Eden baseline remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No Windows ARM64 build, rebuild, rerun, workflow dispatch, or runtime attempt was performed by this implementation work.

## Source-of-truth design

Design record:

`DEBUG_HISTORY_20260831_WAKER_STAGE_K_WORK_TARGET_IDENTITY_DESIGN.md`

The design resolves the shared dependency-worker work identity through the guest scheduler node retained in saved `x26`, rather than another stack-depth stage.

Exact static pointer chain remains:

`x26 node -> [node] work object -> [work object] vtable -> [vtable+0x10] shim -> [vtable+0x60] concrete work target`

The already-proven ModuleSystem path is:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

Runtime C++ does not hardcode those normalized TOTK offsets. Semantic recognition remains analyzer-side only.

## Implementation files

Modified:

- `src/core/x1_waker_stage_k_profiler.h`
- `tools/adreno_lab/transplant_dc95_waker_stage_k_grandparent_depth.py`
- `tools/adreno_lab/analyze_x1_waker_stage_k_grandparent_depth.py`

Implementation commits:

- profiler work-pair accounting: `fb91aee04fecf2a9c171163f37e58e577f24fcb9`
- x26 resolver / main-range registration transplant: `7419259d7dd7053033542f3a199481aa31353e76`
- initial work-target analyzer mapping: `59170e90d97dc6a9676232cfba24744008ef8ce4`
- incomplete-cadence ratio guard: `c02e0a138aa1d17f44626c4300900fcb875c6869`

## Runtime resolver shape

The existing Stage F selected-producer guard and the existing Stage G `cur_thread->GetContext()` sample are reused.

Saved x26 is read exactly once as:

`x1_stage_g_context.r[26]`

The work-target resolver performs exactly four additional guest-memory reads:

1. `[x26 node]` -> work object
2. `[work object]` -> vtable
3. `[vtable+0x10]` -> shim target
4. `[vtable+0x60]` -> work target

Every read has a preceding `IsValidVirtualAddressRange` check. Alignment and pointer-addition overflow checks are applied before dependent accesses.

Together with the existing Stage K grandparent frame-record reads, Stage K now contains exactly:

- Stage K `Read64` sites: **6**
  - frame/grandparent reads: 2
  - work-target reads: 4
- Stage K range-validation sites: **6**

The selected-producer block as a whole contains one additional Stage J parent read, so exact reconstructed dc95 contains seven `Read64` sites inside that bounded block.

No second guest-context capture and no additional stack walk were added.

## Dynamic main-module normalization

The existing Stage H loader path remains the source of the dynamically loaded module range.

When the loader module name is exactly `main`, the Stage K profiler receives:

`RegisterMainModuleRange(load_addr, next_load_addr)`

`Initialize()` resets Stage K counters but deliberately does not clear the previously registered main range.

Resolved executable targets are immediately range-checked and normalized to offsets. The work histogram stores only:

`(shim_offset, work_offset)`

Raw work-object, vtable, shim VA, work-target VA, and main base are not emitted as work-target identities.

## Bounded work-pair accounting

Per already-selected producer:

- fixed work-pair slots: **64**
- key: normalized `(shim_offset, work_offset)`
- values: CPU ticks + slices
- report cadence: **120 frames**
- reported work pairs: **top 4** by ticks

Coverage/censoring counters include:

- `workResolvedN`
- `workResolvedTicks`
- `workOtherResolvedTicks`
- `workOverflowN`
- `workOverflowTicks`
- resolver-status slices/ticks
- `workBadStatus`

`workOtherResolvedTicks` is the resolved total minus the four reported pair totals. Therefore fifth-and-lower resolved work remains quantitatively visible without widening the top list.

Resolver statuses distinguish main-range absence, zero/bad node, invalid node range, zero/bad work object, invalid work-object range, zero/bad vtable, invalid shim/work-target ranges, zero resolved target, and target-outside-main.

## Offline analyzer

The existing Stage K analyzer now parses normalized work pairs and owns the semantic constants.

Analyzer-side static knowledge includes:

- common ModuleSystem shim: `main+0x2af1230`
- complete 41-slot ModuleSystem table
- 36 unique concrete work-target offsets

Known common-shim work offsets are mapped to component identities. Unknown targets are reported as unmapped evidence; non-common shim pairs are preserved separately.

Strict comparison remains fixed to:

- fast / swap2: frames `960`, `1080`
- slow / swap3: frames `1320`, `1440`, `1560`, `1680`

Because runtime logs expose only top four pairs, per-target cadence values are explicitly treated as visible lower bounds. The analyzer also reports `otherResolved` and overflow coverage before an owner is declared.

A slow/fast ratio is emitted only when both cadence groups are actually present. A one-sided/incomplete synthetic log no longer produces a misleading zero ratio.

## Ubuntu static validation — SUCCESS

### Full reconstruction validator

Temporary workflow:

`Validate dc95 X1 Waker Stage K Work Target`

Run:

`33350134250`

Job:

`99361721220`

Event:

`push`

Head SHA:

`6cc9b75d4446aa55fa18837fe73376f8fb48d5b5`

Attempt:

`1`

Result:

**SUCCESS**

This Ubuntu run reconstructed the retained diagnostic chain and Stage D through J on the exact dc95 baseline, applied the new Stage K extension, and verified:

- exact dc95 checkout unchanged
- `git diff --check`
- Python syntax
- `ThreadContext` exposes `r[0..28]`
- exactly six Stage K work/grandparent `Read64` calls and six matching Stage K range checks
- saved x26 use exactly once
- only one guest-context capture
- existing Stage F/G/J profiler files unchanged
- existing Stage H module-log count preserved
- dynamic main registration exactly once
- 64 work-pair slots and top4 reporting
- no behavior-changing scheduler/GPU tokens
- analyzer 41 slots / 36 unique targets
- synthetic normalized common-shim mapping

Synthetic validation resolved:

`main+0x2af1230 / main+0xa85380 -> Actor`

and measured the expected lower-bound common-shim coverage of `75.00%`.

### Analyzer incomplete-cadence guard validator

After the analyzer safety correction, the same temporary Ubuntu workflow was reduced to a focused analyzer regression gate.

Run:

`33350373759`

Job:

`99362422228`

Head SHA:

`e51dc7ec854b1afc7ef46a25f7d749e4c9584f49`

Attempt:

`1`

Result:

**SUCCESS**

It verified Python syntax, 41/36 static mapping, Actor synthetic mapping, 75% coverage, and absence of `strictRatio` output when only the fast cadence window exists.

No validator rerun was used for either successful attempt.

## Temporary validator cleanup

The temporary push validator was removed after validation at commit:

`09916c69671607f4d6240dc3ea3121e37372b45b`

It must not remain as a persistent automatic workflow.

The persistent Windows ARM workflow remains a separate manual `workflow_dispatch` workflow and was not dispatched.

## Behavior invariants

This implementation does not alter:

- thread priority or affinity
- scheduler selection/rescheduling
- yields or sleeps
- AddressArbiter wait/signal semantics
- QueueBuffer behavior or swap interval
- GPU work or fences
- frame cadence
- synchronization semantics

It is observation-only.

## Current gate

Stage K work-target identity implementation is **complete and Ubuntu-static validated**.

This is not Windows ARM64 compile/runtime proof.

A Windows ARM64 build/run requires fresh explicit authorization. Current ARM64 authorization is **NONE**.

If future ARM authorization is given, one authorization permits exactly one attempt and no automatic retry/rerun. Do not create Stage L. Do not implement an optimization before the runtime work-target attribution is observed and strict swap2/swap3 ownership is established.
