# NEXT ACTION — X1 graphics Uniform stream/reuse

Updated: 2026-08-27 KST

## Fixed baseline

- Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Current branch: `exp/x1-uniform-stream-reuse`
- Parent completed experiment: `exp/x1-alias-sync-redundancy`
- New workflow: `.github/workflows/build-dc95-x1-uniform-stream-reuse.yml`
- Intended artifact: `Eden-dc95-X1-uniform-stream-reuse`
- New marker: `[X1-UNIFORM-PATH]`

## Why this is next

The alias-sync runtime disproved trivial alias deduplication: repeated alias pairs always advanced source `modification_tick`, with `sameSrcTick=0` and `sameStateSignature=0`.

Persistent tiny graphics Uniform traffic remains the strongest steady ~20 FPS ceiling candidate. Exact dc95 source inspection now shows a concrete architectural reason worth measuring:

- Vulkan has `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
- each enabled graphics Uniform is visited from `BindHostGraphicsUniformBuffers()`.
- the adaptive small-buffer fast path is a mapped staging stream path, not payload reuse.
- each Vulkan fast visit performs `staging_pool.Request(...Upload)`, descriptor insertion, and a guest-memory copy.
- classic cached-path `SynchronizeBuffer()` can distinguish zero-upload clean hits from real uploads.

## Prepared passive telemetry

At each existing profiler report interval, `[X1-UNIFORM-PATH]` reports:

- all graphics Uniform visits / bytes
- fast mapped-stream visits / bytes
- fast reason: alignment vs adaptive skip policy
- classic cached visits / bytes
- cached clean (zero upload) vs cached actual upload
- visits while the adaptive skip policy is active
- exact fast-stream key repetition for `(stage,index,device_addr,size)`
- same-frame / same-Draw / consecutive-frame repeats
- bounded-table overflow

Fast-key tracker: 16,384 entries, 32-probe cap, cleared every report.

A repeated key proves repeated streaming of the same binding identity and guest range. It does not prove byte-content equality.

## Static state

Prepared without Actions:

- transplant script Python syntax checked locally before commit
- analyzer Python syntax checked locally before commit
- transplant executed successfully against a marker-compatible synthetic fixture before commit
- workflow is `workflow_dispatch` only
- branch currently has 0 Actions runs
- workflow preflight guards exact dc95 source semantics and forbids Uniform behavior/state mutations in the new incremental diff

Full exact transplanted-tree compile/preflight has not run yet because that would require the ARM64 Actions attempt.

## Do not do

- do not enable persistent Vulkan Uniform bindings yet
- do not change `uniform_buffer_skip_cache_size`
- do not skip/reuse/batch Uniform updates yet
- do not add payload hashing in the first pass
- do not alter dirty tracking or `SynchronizeBuffer()` semantics
- do not touch scheduler/render-pass/barrier behavior
- do not start or rerun ARM64 Actions without fresh explicit user authorization

## NEXT ACTION

Only after fresh explicit user authorization for one ARM64 attempt:

1. temporarily add a branch-scoped `push` trigger only to `.github/workflows/build-dc95-x1-uniform-stream-reuse.yml`
2. that trigger-enabling commit is the single authorized ARM64 build attempt
3. immediately restore the workflow to `workflow_dispatch` only without creating a second run
4. if the build succeeds, test the same TOTK 1.4.2 / X1-85 / driver 512.863.0 route and collect `[X1-UNIFORM-PATH]` together with retained `[X1-ALIAS-SYNC]` and existing buffer-category telemetry
5. interpret first whether fast streaming or cached synchronization owns the ~10k–12k requests/frame
6. if fast exact-key repetition is high, design a second *measurement* for content/generation reuse before any optimization
7. if cached actual uploads dominate, move into dirty-range production and `ForEachUploadRange()` granularity instead
8. if the build fails, diagnose/fix but do not start another run without a new explicit authorization
