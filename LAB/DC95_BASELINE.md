# dc95 Windows ARM64 baseline

## Canonical known-good source

- Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Source commit date: `2026-08-15T12:21:52Z`
- Official Nightly repository: `eden-ci/nightly`
- Official Nightly tag: `v1786904188.dc95cd09ee`
- Official Nightly release: `Eden Nightly - Aug 16 2026`
- Official Windows ARM64 Standard artifact: `Eden-Windows-dc95cd09ee-arm64-clang-standard.zip`
- Official Windows ARM64 PGO artifact: `Eden-Windows-dc95cd09ee-arm64-clang-pgo.zip`
- Target: Windows ARM64
- Compiler path: MSYS2 `CLANGARM64` / Clang
- CI scripts pinned from `Eden-CI/Workflow@afead830f3a444427f9fdfd841218f932465c03a`

The user-confirmed working runtime log identifies `master-dc95cd09ee-master`, so this exact revision and its official ARM64 Standard/PGO pair are the canonical comparison point. Do not substitute current `master`, `xuen2008/eden-nightly`, or the imported `0295dc5` tree.

## Why xuen2008/eden-nightly is not the dc95 source

`xuen2008/eden-nightly` stopped updating in January 2026 and cannot have produced the August 2026 dc95 build. The authoritative August nightly artifacts are published by `eden-ci/nightly` on the Eden Forgejo instance.

## Why the previous Lab baseline is not canonical

The imported Lab source was `0295dc5fff9b2977e753e7c126cc870abb07ee3f`.
That commit is itself a post-dc95 Vulkan/QCOM change:

`[vulkan] Removal of QCOM sampler limiters + CustomBorderColor and ColorBorderSwizzle adjustments (#4301)`

Therefore `0295dc5` is kept as a comparison point, not used as the known-good baseline.

## Build-path correction

The previous Lab Windows ARM64 workflow used `clang-cl` in an MSVC-oriented environment.
The official Eden Nightly Windows ARM64 path uses an ARM64 Windows runner with MSYS2 `CLANGARM64` and Clang.

For ARM64 the pinned Eden CI target logic uses:

- `-march=armv8-a`
- `-mtune=generic`
- `-O3`

The standard-baseline workflow is:

`.github/workflows/build-dc95-arm64-baseline.yml`

It checks out exact dc95 independently of the Lab branch contents and produces:

- `clean`: untouched dc95 source
- `profiled`: dc95 plus semantically-neutral Adreno profiler instrumentation

The exact-PGO workflow is:

`.github/workflows/build-dc95-arm64-pgo.yml`

It pins both the source and the PGO input rather than following a future `latest` profile.

## Exact PGO input for dc95 reproduction

The pinned Eden CI enables PGO with `PGO_TARGET=pgo` and adds `-fprofile-use=<eden.profdata>` to the ARM64 Clang flags.

The PGO release that predates dc95 and is the input used for this reproduction is:

- Repository: `Eden-CI/PGO`
- Tag: `v020525`
- Published: `2026-02-05T14:04:41Z`
- Asset: `eden.profdata`
- Size: `17925256` bytes
- SHA-256: `777dd9aefb9427ed08a642b02998f32c5ac120e5d32611d8f21cf1f4e68cee57`

The PGO workflow rewrites the pinned dc95-era CI download URL to `v020525` and verifies this SHA-256 after configure. A future `latest` profile therefore cannot silently change the experiment.

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

- `1fbace438c375ca1e33f3cb09d7d85249cb51293` — QCOM stock-driver fixes (#3334), including GPU/CPU synchronization and shader-compilation work
- `3d19743d95f973ec0c322a0e8703387513ee0c66` — Vulkan regression fixes (#3953), including ARM Windows / QCOM stock-driver blitter-query race fixes
- `8225151a4469a13ac602215dbeb2ce9a3702f38b` — 3rd Vulkan Global Maintenance (#4189)
- `eb9280dedfb5e49e17a0bb586c2be87c4b769625` — 4th Vulkan Global Maintenance (#4212)
- `49a0ca6d5d9929391e0633163ebbfec564d27cc1` — Bindless Buffer/Descriptors (#4251)

The dc95 baseline is therefore already a heavily QCOM-tuned source snapshot. The Lab task is to identify which existing paths matter on Windows ARM64, not to recreate these changes from scratch.

## Important post-dc95 QCOM changes

These are comparison candidates, not baseline content:

- `60a474b8df051beb1d5fb84f4363d1576fcbb3fa` — QCOM shader float-controls fix (#4297)
- `0295dc5fff9b2977e753e7c126cc870abb07ee3f` — QCOM sampler / custom-border-color / border-swizzle adjustments (#4301)

`#4297` changes QCOM handling so FP32 denorm-flush support can remain exposed while a QCOM-specific broken-denorm-flush quirk prevents the bad execution mode from being emitted.

`#4301` is primarily an accuracy/caching cleanup. Its own commit description states an almost-zero performance cost, so it should not be treated as the default explanation for a large FPS difference without measurement.

## Experimental branch policy

Old upstream branches such as `qcomopts2` and `eds-true-adreno-fixes` are idea archives only. They are not to be merged wholesale. Their useful changes must be evaluated as individual commits against dc95.

## Test order

1. Validate untouched `dc95 / CLANGARM64 / standard` against the known-good runtime behavior.
2. Validate profiler build does not materially change behavior.
3. Compare exact-source Standard vs PGO using the pinned `v020525` profile above.
4. Only then test post-dc95 QCOM commits individually or in tightly scoped groups.
5. Optimize only after the regression/benefit boundary is identified.
