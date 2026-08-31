# DEBUG HISTORY — Stage K Work-Target Identity Design

Date: 2026-08-31 KST

## Scope

Design only the smallest observation-only extension needed to identify which concrete ModuleSystem work target owns expensive CPU slices already attributed to the shared dependency-worker branch.

This is **not Stage L** and does not add another stack depth.

Fixed Eden baseline remains:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Current branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No Windows ARM64 build, rebuild, rerun, workflow dispatch, or runtime attempt was performed for this design. No behavior-changing optimization was implemented.

## Source-of-truth static result

Stage K offline semantic mapping already closed the shared ModuleSystem execution path:

`component -> main+0x7eea44 -> shared DepWorker -> main+0x86a4ac -> main+0x86a988 -> main+0x2af1230 -> component vtable+0x60`

The existing runtime record does not contain the work-object identity needed to decide which of the 41 statically mapped ModuleSystem slots / 36 unique `vtable+0x60` targets owns each expensive shared-worker CPU slice.

## Exact x26 execution anchor

Exact TOTK 1.2.1 main disassembly around the work-object call is:

```text
main+0x86a97c: LDR x0, [x26]
main+0x86a980: LDR x8, [x0]
main+0x86a984: LDR x8, [x8, #0x10]
main+0x86a988: BLR x8
```

Therefore, while the shared dispatcher executes a queued work object:

- `x26` is the scheduler-node pointer;
- `[x26]` is the work-object pointer;
- `[work_object]` is its vtable;
- `[vtable+0x10]` is the virtual target invoked at `main+0x86a988`.

AArch64 `x26` is callee-saved, so nested work execution preserves the dispatcher-held scheduler-node identity under normal ABI-conforming calls.

The exact Eden dc95 guest thread context already stores general registers as `r[0..28]`, so the existing Stage G `cur_thread->GetContext()` sample exposes saved `x26` as:

`x1_stage_g_context.r[26]`

No second guest-context capture is required.

## Exact ModuleSystem shim

Exact disassembly of the common ModuleSystem virtual target confirms:

```text
main+0x2af1230: ...
...
main+0x2af12b0: LDR x8, [x0]
main+0x2af12b4: LDR x2, [x8, #0x60]
main+0x2af12b8: BR x2
```

Thus the common `vtable+0x10` shim tail-dispatches to the component-specific `vtable+0x60` work target.

The runtime instrumentation must **not** hardcode `main+0x2af1230`. It should resolve and normalize both the shim and work target; the offline analyzer may then recognize `main+0x2af1230` as the already-proven common ModuleSystem shim.

## Minimal pointer resolver

Reuse the existing Stage F selected-producer guard and the single Stage G context sample.

For each already-selected switched-out producer CPU slice:

1. `node = x1_stage_g_context.r[26]`
2. validate `[node, node+8)` and read `work_object = [node]`
3. validate `[work_object, work_object+8)` and read `vtable = [work_object]`
4. guard vtable alignment / `+0x60` overflow
5. validate `[vtable+0x10, vtable+0x18)` and read `shim_target`
6. validate `[vtable+0x60, vtable+0x68)` and read `work_target`
7. require both resolved targets to lie inside the dynamically registered `main` module range
8. normalize immediately to `shim_offset = shim_target - main_base` and `work_offset = work_target - main_base`
9. store only the normalized offset pair and the existing scheduler `tick_diff`

This adds exactly four guest-memory `Read64` sites for the work-target resolver:

- scheduler node -> work object
- work object -> vtable
- vtable+0x10 -> shim target
- vtable+0x60 -> concrete work target

No stack memory is scanned or walked.

## Main-module normalization

The existing Stage H loader hook already observes each module's dynamic load range.

The narrow design is to extend the existing Stage K profiler with a one-time method such as:

`RegisterMainModuleRange(base, end)`

At the Stage H module-load hook, when the loader's module name is exactly `main`, register that dynamic range with the Stage K profiler.

Requirements:

- registration must not depend on the Vulkan profiler being initialized yet;
- later `Initialize()` must reset counters without clearing the already-registered main range;
- raw module base/end may exist transiently inside the process for range checks, but must not be emitted as new work-target records;
- work-target histogram keys and logs must contain normalized offsets only.

## Bounded accounting

Keep the measurement inside Stage K rather than creating a new stage.

Per selected producer:

- fixed work-pair slots: **64**
- key: `(shim_offset, work_offset)`
- counter: slices + CPU ticks
- report cadence: **120 rendered frames**, unchanged from Stage K
- report: **top 4** work pairs by ticks, unchanged in width from the existing Stage K top-count convention
- additionally report `resolvedTicks`, `otherResolvedTicks`, `overflowTicks`, and resolver-status ticks/slices so top-4 censoring is explicitly measurable

`otherResolvedTicks` is the resolved total minus the reported top-four pair ticks. Therefore a large fifth-or-lower contribution is visible quantitatively without widening the report to top 8 or globally expanding profiling.

A full-table overflow remains separately counted and must not be silently discarded.

## Resolver validity accounting

Use bounded status accounting rather than logging individual failures. Distinguish at least:

- valid resolved pair
- main range unavailable
- zero/bad node
- invalid node read range
- zero work object
- invalid work-object read range
- zero/bad vtable
- invalid shim read range
- invalid work-target read range
- zero resolved target
- resolved target outside `main`

The exact enum spelling is an implementation detail; the required property is that unresolved ticks remain measurable and cannot be mistaken for component-owned ticks.

## Runtime hardcode prohibition

Do not hardcode any observed TOTK runtime identity in the C++ measurement, including:

- raw ASLR addresses
- `main` base
- `main+0x86a988`
- `main+0x2af1230`
- any of the 36 statically enumerated `vtable+0x60` offsets

The runtime only follows the saved `x26` pointer structure and normalizes resolved executable addresses against the dynamically registered `main` module range.

The offline analyzer owns semantic recognition of normalized offsets.

## Offline analyzer decision rule

For each strict Stage K cadence window, the analyzer should:

1. read normalized `(shim_offset, work_offset)` pairs;
2. select the already-proven common ModuleSystem shim only after normalization (`main+0x2af1230`);
3. map `work_offset` against the static 41-slot / 36-target table from `DEBUG_HISTORY_20260831_WAKER_STAGE_K_OFFLINE_SEMANTIC_MAPPING.md`;
4. aggregate ticks per concrete component target for P0 and P1;
5. compare only strict fast/swap2 windows `960,1080` with strict slow/swap3 windows `1320,1440,1560,1680`;
6. report unresolved, other-resolved, and overflow shares before declaring an owner.

A resolved target outside the known 36-target ModuleSystem set must be reported as unmapped evidence, not assigned a guessed component name.

## Acceptance criteria for a future runtime capture

A future single authorized ARM attempt is useful only if all of the following hold:

1. work-target resolver remains confined to the two already-selected producers;
2. no new arbitrary stack depth or all-thread profiling exists;
3. logs store/report normalized offsets, not raw target VAs;
4. the common ModuleSystem shim appears as normalized `main+0x2af1230` in the resolved pair data;
5. resolved/common-shim coverage is high enough that the dominant target result is not overwhelmed by unresolved/overflow/other ticks;
6. dominant work offsets map cleanly to the already-established static component table or are explicitly reported as unmapped;
7. strict swap2/swap3 CPU-tick deltas can be computed from equal 120-frame windows;
8. `EventModuleSubWorker` remains a separate already-resolved Stage K branch and is not merged into the shared ModuleSystem target histogram.

If coverage is poor, the result is inconclusive. It does not authorize an automatic retry or a broader profiler.

## Design decision

This is the preferred next measurement design.

It is narrower than another stack-depth stage because it directly resolves the object identity already proven to sit behind the shared dispatcher. It reuses the existing selected-producer context sample, adds no thread discovery, and requires no behavior changes.

Implementation is **not performed by this record**. A later implementation can be statically validated without consuming ARM64 authorization. Any Windows ARM64 build/run still requires fresh explicit authorization, with one authorization = exactly one attempt and no automatic retry.
