# X1 Uniform payload fingerprint diagnostic

## Baseline

- Lab: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Parent diagnostic: `exp/x1-uniform-stream-reuse`
- Current branch: `exp/x1-uniform-payload-fingerprint`

## Why this experiment exists

The matched TOTK 1.4.2 runtime from the Uniform stream/reuse build showed that graphics Uniform traffic is overwhelmingly driven by the Vulkan fast mapped-stream path rather than classic cached dirty uploads.

Steady sample window, frames 1200–1680 (five 120-frame reports, 600 frames):

- Uniform visits: **9,927,196**
- fast mapped-stream visits: **9,762,092** (**98.34%**)
- classic cached visits: **165,104**
- fastAlignment: **0**
- fastSkip: **9,762,092**
- cached clean / zero-upload: **154,847**
- cached actual upload: **10,257**
- exact fast-key repeats: **9,522,804**
- fast same-frame repeats: **7,821,763**
- fast same-Draw repeats: **0**

At frame 1680, where the fast-key table had zero overflow:

- fast visits: **1,077,023**
- unique keys: **5,445**
- repeat keys: **1,071,578**
- same-frame repeats: **896,989**
- cached upload: **1,294**
- Draw Uniform `uploadReq`: **1,078,317** = fast **1,077,023** + cachedUpload **1,294**

This establishes that the huge graphics Uniform upload-request count is mostly the adaptive fast-stream policy itself. It does **not** establish that repeated exact keys contain unchanged bytes.

## Question

For repeated fast Uniform key:

`(stage, index, device_addr, size)`

how often does the payload fingerprint remain unchanged from the previous tracked occurrence?

This separates:

1. repeated key + same payload fingerprint — strong candidate for avoidable re-stream/reuse work
2. repeated key + changed payload fingerprint — the guest reused the same binding/range identity but changed the contents, so simple payload reuse would be unsafe

## Low-perturbation sampling

Hashing every fast Uniform would itself add significant CPU work. Therefore the diagnostic uses deterministic **1/16 key sampling**.

Sample selection is based only on the exact key fields. The same key is therefore either always sampled or always unsampled within and across reports.

For sampled fast visits:

- no extra guest-memory read is issued
- the fingerprint is computed from the mapped staging span **after the existing `device_memory.ReadBlockUnsafe()` has already copied the payload**
- the full sampled payload span is hashed with 64-bit FNV-1a

The tracker reuses the existing fixed Uniform fast-key table.

## New marker

`[X1-UNIFORM-PAYLOAD]`

Fields:

- `samples` — sampled fast visits
- `uniqueSamples` — sampled keys first inserted into the bounded table during the report
- `repeatSamples` — sampled tracked key repeats
- `sameFingerprint` — repeat whose 64-bit payload fingerprint equals the previous tracked occurrence
- `changedFingerprint` — repeat whose fingerprint differs
- `sameFrameSame` — same-fingerprint repeat whose previous occurrence was in the same frame
- `sameFrameChanged` — changed-fingerprint repeat whose previous occurrence was in the same frame
- `sampleOverflow` — sampled visit that could not be classified because the bounded key table/probe cap could not place/find the key
- `sampleDenom=16` — deterministic 1/16 sampling denominator

For classified sampled repeats:

`sameFingerprint + changedFingerprint == repeatSamples`

unless a future instrumentation bug is found. `sampleOverflow` is reported separately.

## Interpretation guard

A 64-bit hash match is extremely strong evidence of equal payload bytes for this diagnostic, but it is not a mathematical byte-by-byte proof because hash collisions are theoretically possible.

Do not implement a correctness-affecting skip solely from fingerprint equality. If a later optimization is attempted, it must use an exact correctness-preserving state/content mechanism rather than trusting telemetry hashes.

## Safety

This experiment does not:

- enable persistent Vulkan Uniform bindings
- alter `uniform_buffer_skip_cache_size`
- alter fast/cached selection
- skip or reuse any Uniform upload
- change dirty tracking
- add another guest-memory read
- change staging allocation or descriptor behavior
- change barriers, render-pass handling, scheduler behavior or alias synchronization

## Decision after runtime

If sampled repeat keys are overwhelmingly `sameFingerprint`, the next optimization question becomes how to preserve/reuse the existing GPU-visible Uniform backing without recreating Ryubing/Kenji-style freeze hazards.

If sampled repeat keys overwhelmingly change fingerprint, the next direction is tiny-stream batching/allocation/descriptor overhead rather than content reuse.
