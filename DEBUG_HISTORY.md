# DEBUG HISTORY — Eden Adreno X1-85

This file records confirmed experiment outcomes and the current diagnostic chain. It was absent from the working branch before the 2026-08-27 Uniform investigation, so earlier history remains represented by the existing TECH_BIBLE / maps / handoff documents rather than being reconstructed here from memory.

## 2026-08-27 — X1 alias synchronization redundancy runtime

Baseline:

- exact Eden source `dc95cd09eea9749250fe31a3072684d341d19417`
- branch `exp/x1-alias-sync-redundancy`
- authorized build run `33024690895`, job `98363162523`, attempt 1
- build HEAD `804f394c5db280f842a01113e6ca92f7ad57d219`
- result success
- artifact `Eden-dc95-X1-alias-sync-redundancy`, id `9628554127`
- artifact SHA-256 `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

Matched runtime:

- TOTK 1.4.2
- Adreno X1-85, driver 512.863.0, Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- log `eden_log(9).txt`
- user stopped the emulator intentionally when the log became large; not a crash

Aggregate alias-sync result:

- copies 194,396
- sameFrame 59,722
- sameDraw 0
- consecutiveFrame 111,202
- sameSrcTick 0
- advancedSrcTick 190,823
- regressedSrcTick 0
- sameSignature 190,823
- sameStateSignature 0
- regions 194,396
- maxRegions 1
- tableOverflow 0

Conclusion — CONFIRMED:

Repeated alias pair/region requests are not trivial unchanged-state duplicates. Every tracked recurrence advances source `modification_tick`; there are zero same-source-tick + same-region candidates. Do not implement simple alias-copy dedupe from this evidence.

The established path remains:

`Draw Configure -> FillImageViews -> PrepareImage -> SynchronizeAliases -> CopyImage -> direct Vulkan copy -> RequestOutsideRenderPassOperationContext -> vkCmdCopyImage`

## 2026-08-27 — exact dc95 graphics Uniform source analysis

Motivation:

Steady TOTK gameplay continues to show roughly 10k–12k tiny graphics Uniform upload requests per frame, while alias trivial dedupe is now closed.

Exact source facts — CONFIRMED:

1. Vulkan `BufferCacheParams::HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
2. Generic graphics Uniform binding begins with `dirty = ~0U`; the persistent dirty-binding mask is only consumed when the policy enables persistent Uniform bindings.
3. Every visited graphics Uniform increments `uniform_cache_shots[0]`.
4. Classic cached path calls `SynchronizeBuffer()`.
5. `SynchronizeBuffer()` returns true when `ForEachUploadRange()` yields zero upload bytes, and returns false after a real `UploadMemory()`.
6. `uniform_cache_hits[0]` therefore counts classic cached visits that required zero upload bytes.
7. `TickFrame()` uses recent hit/shot history to toggle `uniform_buffer_skip_cache_size`.
8. Exact dc95 Vulkan fast graphics Uniform path calls `BindMappedUniformBuffer()`, which performs `staging_pool.Request(size, MemoryUsage::Upload)` and descriptor insertion; generic code then copies guest bytes with `device_memory.ReadBlockUnsafe()`.

Interpretation — STRONG SOURCE-LEVEL HYPOTHESIS:

The fast path is a stall-avoidance re-stream path, not persistent payload reuse. The steady ~20 FPS ceiling may therefore include a design-level cost from repeatedly allocating/streaming thousands of tiny Uniform payloads.

No performance optimization has been applied from this hypothesis.

## 2026-08-27 — Uniform stream/reuse diagnostic prepared

Branch:

`exp/x1-uniform-stream-reuse`

Parent restored HEAD:

`abad21031730d0f97eaef79b50a79308c4b50534`

Prepared instrumentation:

- `tools/adreno_lab/transplant_dc95_uniform_stream_reuse.py`
- `tools/adreno_lab/analyze_x1_uniform_path.py`
- `.github/workflows/build-dc95-x1-uniform-stream-reuse.yml`
- `UNIFORM_STREAM_REUSE_MAP.md`
- `NEXT_ACTION_UNIFORM_STREAM_REUSE.md`

New aggregate marker:

`[X1-UNIFORM-PATH]`

Measures:

- all graphics Uniform visits/bytes
- fast mapped-stream visits/bytes
- fast alignment vs adaptive skip-policy reason
- classic cached visits/bytes
- cached zero-upload vs actual-upload outcome
- adaptive skip-policy active visits
- repeated exact fast key `(stage,index,device_addr,size)`
- same-frame / same-Draw / consecutive-frame repeats
- bounded table overflow

Tracker:

- 16,384 fixed entries
- 32-probe cap
- cleared every profiler report

Interpretation guard:

Repeated exact keys prove repeated streaming of the same binding identity and guest address/range. They do not prove byte-content equality. Payload hashing was intentionally not added to this first pass to avoid perturbing CPU-side timing.

Safety:

- instrumentation only
- no Uniform skip/reuse/batching
- no persistent-binding enable
- no skip-threshold change
- no dirty-state mutation
- no barrier/render-pass/scheduler behavior change

Build state at preparation:

- workflow `workflow_dispatch` only
- current branch Actions runs: 0
- no ARM64 build authorized
