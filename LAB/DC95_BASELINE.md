# dc95 Windows ARM64 baseline

## Canonical known-good source

- Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Target: Windows ARM64
- Compiler path: MSYS2 `CLANGARM64` / Clang
- Baseline mode: `standard`
- CI scripts pinned from `Eden-CI/Workflow@afead830f3a444427f9fdfd841218f932465c03a`

This is the reference point for Snapdragon / Adreno investigation. Do not substitute current `master` or the imported `0295dc5` tree when reproducing the known-good behavior.

## Why the previous Lab baseline is not canonical

The imported Lab source was `0295dc5fff9b2977e753e7c126cc870abb07ee3f`.
That commit is itself a post-dc95 Vulkan/QCOM change:

`[vulkan] Removal of QCOM sampler limiters + CustomBorderColor and ColorBorderSwizzle adjustments (#4301)`

Therefore `0295dc5` is kept as a comparison point, not used as the known-good baseline.

## Build-path correction

The previous Lab Windows ARM64 workflow used `clang-cl` in an MSVC-oriented environment.
The Eden nightly Windows ARM64 path uses an ARM64 Windows runner with MSYS2 `CLANGARM64` and Clang.

The baseline workflow is:

`.github/workflows/build-dc95-arm64-baseline.yml`

It checks out the exact dc95 source independently of the Lab branch contents and produces:

- `clean`: untouched dc95 source
- `profiled`: dc95 plus semantically-neutral Adreno profiler instrumentation

## Profiler provenance

Profiler source reference:

`318bb024cc06a0497d179d374b4680c8d57f767d`

Only instrumentation is transplanted. The later `0295` Vulkan behavior is not intentionally imported.
The dc95 scheduler hooks are transplanted by exact-context replacements in:

`tools/adreno_lab/transplant_dc95_scheduler_profiler.py`

The transplant currently records:

- Finish wait time
- Worker wait time
- render-pass begin/end/reuse
- post-render-pass image barrier count
- deferred clears
- descriptor-buffer binds
- queue submissions

## QCOM work already contained in dc95

Ancestry verification shows these upstream changes are already ancestors of dc95 and must not be reimplemented as new Lab optimizations:

- `8225151a4469a13ac602215dbeb2ce9a3702f38b` — 3rd Vulkan Global Maintenance (#4189)
- `eb9280dedfb5e49e17a0bb586c2be87c4b769625` — 4th Vulkan Global Maintenance (#4212)
- `49a0ca6d5d9929391e0633163ebbfec564d27cc1` — Bindless Buffer/Descriptors (#4251)

## Important post-dc95 QCOM changes

These are comparison candidates, not baseline content:

- `60a474b8df051beb1d5fb84f4363d1576fcbb3fa` — QCOM shader float-controls fix (#4297)
- `0295dc5fff9b2977e753e7c126cc870abb07ee3f` — QCOM sampler / custom-border-color / border-swizzle adjustments (#4301)

`#4297` changes QCOM handling so FP32 denorm-flush support can remain exposed while a QCOM-specific broken-denorm-flush quirk prevents the bad execution mode from being emitted.

## Experimental branch policy

Old upstream branches such as `qcomopts2` and `eds-true-adreno-fixes` are idea archives only. They are not to be merged wholesale. Their useful changes must be evaluated as individual commits against dc95.

## Test order

1. Validate untouched `dc95 / CLANGARM64 / standard` against the known-good runtime behavior.
2. Validate profiler build does not materially change behavior.
3. Compare exact-source Standard vs PGO.
4. Only then test post-dc95 QCOM commits individually or in tightly scoped groups.
5. Optimize only after the regression/benefit boundary is identified.
