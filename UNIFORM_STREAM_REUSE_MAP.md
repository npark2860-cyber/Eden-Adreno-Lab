# Uniform stream/reuse map — exact dc95

Updated: 2026-08-27 KST

## Question

Why does matched TOTK gameplay on Adreno X1-85 produce roughly 10k–12k tiny graphics Uniform upload requests per frame, and how much of that pressure comes from exact-dc95 Vulkan's fast stream path rather than actual cached-buffer synchronization uploads?

## Exact dc95 facts locked before instrumentation

- Vulkan `BufferCacheParams::HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- `BindHostGraphicsUniformBuffers()` therefore begins with `dirty = ~0U` and does not consume a persistent dirty-binding mask on Vulkan.
- Every enabled graphics Uniform binding calls `BindHostGraphicsUniformBuffer()`.
- Every such call increments `uniform_cache_shots[0]`.
- The classic cached path calls `SynchronizeBuffer()`.
- `SynchronizeBuffer()` returns `true` when `ForEachUploadRange()` produces zero bytes, and returns `false` after `UploadMemory()` when bytes were actually uploaded.
- `uniform_cache_hits[0]` is incremented only when that cached synchronization returns `true` (zero upload bytes).
- At `TickFrame()`, recent hit/shot history controls `uniform_buffer_skip_cache_size`; when the clean-hit ratio is not extremely high, the small-buffer skip/stream policy is enabled.
- Vulkan fast graphics Uniform path calls `BindMappedUniformBuffer()`, which performs `staging_pool.Request(size, MemoryUsage::Upload)` and descriptor queue insertion, then `device_memory.ReadBlockUnsafe()` copies guest bytes into the mapped span.
- Therefore a Vulkan fast-path visit is a real new stream allocation/copy/descriptor operation; it is not a persistent payload reuse.

## Current hypothesis

The steady ~20 FPS ceiling may be paying for a design-level tradeoff: exact dc95 avoids possible cached-buffer stalls by repeatedly streaming many tiny graphics Uniform payloads. Ryubing/Kenji resource/range lifetime handling makes this tradeoff worth comparing, but no optimization is justified until the Eden path split is measured.

## Passive telemetry

New aggregate marker: `[X1-UNIFORM-PATH]`, emitted at the existing profiler report interval.

Counters:

- `visits`, `bytes`: all graphics Uniform binding visits measured by this hook.
- `fast`, `fastBytes`: visits that actually executed the mapped stream path.
- `fastAlignment`: fast visits selected because the cached host-buffer offset violates Uniform alignment.
- `fastSkip`: fast visits selected by the adaptive small-buffer skip/stream policy rather than alignment.
- `cached`, `cachedBytes`: classic cached-buffer path visits.
- `cachedClean`: cached visits where `SynchronizeBuffer()` found zero upload bytes.
- `cachedUpload`: cached visits where `SynchronizeBuffer()` actually uploaded data.
- `skipPolicyVisits`: visits while `uniform_buffer_skip_cache_size != 0`.
- `fastUniqueKeys`: unique fast-stream `(stage,index,device_addr,size)` keys in the report window.
- `fastRepeatKey`: later fast-stream visits to an already seen exact key.
- `fastSameFrame`, `fastSameDraw`, `fastConsecutiveFrame`: repeat timing classification.
- `tableOverflow`: missed fast-key history due to the bounded tracker.

Tracker bounds: 16,384 entries, 32-probe cap, cleared every report.

## Interpretation limits

A repeated exact key proves the same guest address/range and shader-stage binding identity was streamed again. It does **not** prove the bytes were unchanged. This first pass intentionally does not hash Uniform payloads because hashing every tiny payload could perturb the very CPU-side cost being measured.

If fast streaming dominates and exact keys repeat heavily, a second targeted measurement can determine byte-content reuse with sampling or generation tracking. If cached uploads dominate instead, the investigation moves to dirty-range production and `ForEachUploadRange()` granularity.

## Safety / non-goals

Instrumentation only. This experiment does not:

- enable persistent Vulkan Uniform bindings
- change `uniform_buffer_skip_cache_size`
- change fast/cached path selection
- skip or reuse any Uniform payload
- change `SynchronizeBuffer()` dirty state
- change staging allocation, descriptor binding, barriers, render-pass behavior, or scheduler behavior

No ARM64 build is authorized by preparing this experiment.
