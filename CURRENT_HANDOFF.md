# CURRENT HANDOFF — Eden Adreno X1 Uniform stream/reuse

Updated: 2026-08-27 KST

## Fixed baseline

- Lab repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Completed texture experiment: `exp/x1-texture-fill-reasons`
- Completed alias-route experiment: `exp/x1-alias-copy-reasons`
- Completed alias-redundancy experiment: `exp/x1-alias-sync-redundancy`
- Current prepared experiment: `exp/x1-uniform-stream-reuse`

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Latest successful diagnostic build

X1 Alias Sync Redundancy:

- workflow: `Build dc95 X1 Alias Sync Redundancy`
- run: `33024690895`
- job: `98363162523`
- run attempt: 1
- build HEAD: `804f394c5db280f842a01113e6ca92f7ad57d219`
- result: **success**
- artifact: `Eden-dc95-X1-alias-sync-redundancy`
- artifact id: `9628554127`
- size: 31,300,012 bytes
- SHA-256: `3aa79bb1cd986d7b4da19a1047a22c87db7b486b549a8856680138d11655b8f2`

The one-shot push trigger was removed after the authorized run. The alias-sync workflow is back to `workflow_dispatch` only.

## Latest matched runtime

Log: `eden_log(9).txt`

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- Eden source identification: `HEAD-dc95cd09ee-HEAD`
- user manually stopped the emulator when the log became large; this was **not a crash**

## Alias synchronization result — CONFIRMED / CLOSED AS TRIVIAL DEDUPE

Whole runtime aggregate:

- alias-sync copies: **194,396**
- same-frame repeats: **59,722**
- same-Draw repeats: **0**
- consecutive-frame repeats: **111,202**
- same source `modification_tick`: **0**
- advanced source tick: **190,823**
- regressed source tick: **0**
- same copy-region signature: **190,823**
- same source tick + same region signature: **0**
- total regions: **194,396**
- max regions per request: **1**
- bounded-table overflow: **0**

Interpretation:

- the same `(dst,src)` pair and same copy region often recur
- however every tracked recurrence advances the source `modification_tick`
- there are **zero** measured cases where source recency state and region signature are both unchanged
- therefore a simple `same pair/tick/region => skip CopyImage` optimization has zero measured candidates
- do not continue alias-copy trivial dedupe work without materially new evidence

The previously confirmed alias path remains:

`Draw Configure`
-> `FillImageViews`
-> `PrepareImage`
-> `SynchronizeAliases`
-> `CopyImage`
-> generic direct route
-> `TextureCacheRuntime::CopyImage`
-> `RequestOutsideRenderPassOperationContext()`
-> `vkCmdCopyImage`

Do not reopen reinterpret/convert/BPB fallback/resolve-shadow invalidation. Do not suppress the outside-render-pass request.

## Persistent performance structure

Matched steady gameplay continues to show two large recurring costs:

1. tiny graphics Uniform upload pressure, roughly **10k–12k requests/frame**, average payload only a few hundred bytes
2. valid alias image synchronization, roughly **100+ copies/frame**, with a substantial fraction requiring outside-render-pass operation

Heavy 3–6 FPS dips remain composite: the persistent costs above plus bulk staging, Vertex/Index copy spikes and texture refresh activity.

Do not force the normal ~20 FPS ceiling and severe dip events into one root cause.

## New exact dc95 Uniform source facts — CONFIRMED

### Vulkan does not persist graphics Uniform binding dirtiness

Exact dc95 `Vulkan::BufferCacheParams` has:

`HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`

Generic `BindHostGraphicsUniformBuffers()` starts with:

`u32 dirty = ~0U;`

and consumes `dirty_uniform_buffers` only when persistent Uniform bindings are enabled. Therefore Vulkan visits every enabled graphics Uniform binding on each call rather than relying on the persistent binding dirty mask used by the OpenGL policy.

### Uniform cache hit means zero upload on the classic cached path

`BindHostGraphicsUniformBuffer()` increments `uniform_cache_shots[0]` for every visit.

Classic path:

`SynchronizeBuffer(buffer, device_addr, size)`

`SynchronizeBuffer()` collects CPU-dirty upload ranges through `memory_tracker.ForEachUploadRange()`.

- when total upload bytes are zero: returns `true`
- when bytes exist: calls `UploadMemory(...)`, sets `any_buffer_uploaded = true`, returns `false`

`uniform_cache_hits[0]` is incremented only on the `true` / zero-upload result.

### The adaptive fast path is re-streaming, not persistent payload reuse

`TickFrame()` looks at recent hits vs shots and chooses whether `uniform_buffer_skip_cache_size` should be `DEFAULT_SKIP_CACHE_SIZE` or zero.

Fast graphics Uniform selection is:

- alignment-driven stream, or
- small-buffer adaptive skip/stream path when the region is not GPU-modified

On exact dc95 Vulkan, `BindMappedUniformBuffer()` performs:

- `staging_pool.Request(size, MemoryUsage::Upload)`
- descriptor queue buffer insertion
- then generic code copies guest data with `device_memory.ReadBlockUnsafe()`

So every Vulkan fast Uniform visit allocates/requests mapped staging, binds a descriptor and copies the payload again. It is a stall-avoidance stream path, not a payload cache hit.

This exact design is now the next measured hypothesis for the steady ~20 FPS ceiling.

## Current prepared diagnostic

Branch:

`exp/x1-uniform-stream-reuse`

Prepared files:

- `tools/adreno_lab/transplant_dc95_uniform_stream_reuse.py`
- `tools/adreno_lab/analyze_x1_uniform_path.py`
- `.github/workflows/build-dc95-x1-uniform-stream-reuse.yml`
- `UNIFORM_STREAM_REUSE_MAP.md`
- `NEXT_ACTION_UNIFORM_STREAM_REUSE.md`

Intended artifact after a future authorized build:

`Eden-dc95-X1-uniform-stream-reuse`

New aggregate marker:

`[X1-UNIFORM-PATH]`

### Measurements

At the existing report interval:

- graphics Uniform visits / bytes
- mapped fast-stream visits / bytes
- fast reason: alignment vs adaptive small-buffer skip/stream
- classic cached visits / bytes
- cached clean (zero upload) vs cached actual upload
- visits while adaptive skip policy is active
- exact fast-stream key repetition for `(stage,index,device_addr,size)`
- same-frame / same-Draw / consecutive-frame repeat timing
- bounded-table overflow

Fast-key tracker:

- 16,384 entries
- 32-probe cap
- fixed storage, no dynamic growth
- cleared each report

A repeated key proves the same binding identity and guest address/range was streamed again. It **does not** prove byte-content equality. Payload hashing is intentionally excluded from this first pass to avoid perturbing CPU-side timing.

## Instrumentation-only safety state

The new diagnostic does **not**:

- enable persistent Vulkan Uniform bindings
- change `uniform_buffer_skip_cache_size`
- change fast/cached selection
- skip, cache, deduplicate, reuse or batch a Uniform payload
- change `SynchronizeBuffer()` dirty-state semantics
- change staging or descriptor behavior
- change barriers or render-pass behavior
- touch scheduler source
- change alias synchronization behavior

## Static/preparation state

Completed without Actions:

- new branch created directly from alias-sync restored HEAD `abad21031730d0f97eaef79b50a79308c4b50534`
- transplant script Python syntax checked locally before commit
- analyzer Python syntax checked locally before commit
- transplant executed successfully against a marker-compatible synthetic fixture before commit
- workflow is `workflow_dispatch` only
- branch Actions count after preparation: **0**

Workflow preflight additionally requires:

- exact dc95 checkout
- retained Draw + alias-sync instrumentation
- `[X1-UNIFORM-PATH]` marker
- fixed Uniform key table/probe bounds
- exact Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- exact staging-request / descriptor / guest-copy path markers
- exact cached `SynchronizeBuffer()` zero-upload vs upload semantics
- incremental Uniform-only diff scan rejecting behavior/state mutations
- no scheduler source touch
- exact-dc95 scheduler leak guards

Full transplanted-tree compile/preflight has not run because no new ARM64 attempt is authorized.

## Ryubing/Kenji comparison status

Reference comparison only, not yet an Eden optimization:

- Ryubing `BufferHolder` keeps pending data/ranges, mirrors and `MultiFenceHolder` in resource state
- TBDR mirror handling can reuse an existing `(offset,size)` mirror while respecting in-flight writes
- this is structurally different from exact-dc95 Vulkan's fast Uniform path, which streams a new mapped allocation/payload on each fast visit

User runtime observation: Ryubing/Kenji can hold 30 FPS in good TOTK sections but suffer freezing, whereas Eden is more continuously slow around 20 FPS and does not show the same characteristic freezing. Treat this as an important runtime observation, not yet a proved causal mechanism.

## What NOT to do next

- do not start Actions without fresh explicit permission
- do not optimize alias trivial dedupe
- do not enable persistent Vulkan Uniform bindings yet
- do not alter Uniform skip threshold or dirty tracking yet
- do not hash every Uniform payload in the first measurement
- do not import Ryubing/Kenji resource behavior blindly
- do not trade Eden's stability for an unmeasured stall/freeze regression

## NEXT ACTION

See `NEXT_ACTION_UNIFORM_STREAM_REUSE.md`.

The next executable action is only after fresh explicit user authorization for one ARM64 build attempt:

1. temporarily add a branch-scoped push trigger to the Uniform workflow
2. the trigger-enabling commit is the one authorized attempt
3. immediately restore manual-only workflow state without a second run
4. on success, run the same matched TOTK route and collect `[X1-UNIFORM-PATH]`
5. decide whether the 10k–12k requests/frame are dominated by fast mapped re-streaming or cached dirty uploads

## Current build authorization state

- current experiment: `exp/x1-uniform-stream-reuse`
- ARM64 runs on current branch: **0**
- next build authorization: **not granted**
- gameplay optimization applied: none
- Uniform payloads skipped/reused/batched: none
- alias copies skipped: none
- barriers/render-pass requests suppressed: none
