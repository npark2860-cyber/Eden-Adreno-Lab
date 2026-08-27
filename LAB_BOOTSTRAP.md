# Eden Adreno Lab

Repository bootstrap for the Windows ARM64 / Qualcomm Adreno X1-85 Eden optimization lab.

Updated: 2026-08-27 KST

## Fixed experimental baseline

- Upstream source: `eden-emulator/mirror`
- Exact known-good Eden SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control branch: `lab/dc95-arm64-baseline`
- Completed alias-route branch: `exp/x1-alias-copy-reasons`
- Completed alias-redundancy branch: `exp/x1-alias-sync-redundancy`
- Completed Uniform path branch: `exp/x1-uniform-stream-reuse`
- Current completed diagnostic branch: `exp/x1-uniform-payload-fingerprint`

Do not silently move the experimental source baseline while comparing performance. Later Eden behavior may be studied separately, but dc95 experiments must remain source-comparable.

## Resolved alias performance chain

Runtime diagnostics resolved the Draw outside-render-pass alias path:

`Draw other`
-> `texture-fill-image-views`
-> `SynchronizeAliases / alias-copy`
-> generic direct `CopyImage`
-> Vulkan `TextureCacheRuntime::CopyImage`
-> `RequestOutsideRenderPassOperationContext`
-> `vkCmdCopyImage`

Alias-route runtime attributed 24,806 / 39,017 = 63.58% of whole-log Draw outside-RP to `other/texture/alias-copy/direct-vk-copy`.

The follow-up alias-redundancy runtime closed trivial copy dedupe:

- 194,396 alias-sync copies
- `sameSrcTick=0`
- `advancedSrcTick=190,823`
- `sameStateSignature=0`
- `tableOverflow=0`

Repeated pair/region requests therefore represent newer source recency state under exact dc95; do not skip them as unchanged duplicates.

## Uniform source facts now confirmed

Exact dc95 Vulkan:

- `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`
- graphics Uniform bindings are revisited instead of using an OpenGL-style persistent dirty-binding mask
- classic cached path uses `SynchronizeBuffer()` and can finish with zero physical upload when the guest range is clean
- `uniform_cache_hits` corresponds to that zero-upload result
- adaptive small-Uniform fast path is a mapped staging re-stream path, not payload reuse
- every fast visit requests upload staging, inserts a descriptor and copies guest bytes again

## Uniform runtime results

### `exp/x1-uniform-stream-reuse`

Authorized build:

- run `33037180003`
- job `98402328028`
- attempt 1
- build HEAD `8f33dc37c98afa134ad5efbbf14ab85df388ee42`
- artifact `Eden-dc95-X1-uniform-stream-reuse`
- artifact id `9633005533`
- SHA-256 `03491e648026bf0226f2bbd3817d4a979040cc027991af45f9117c2a68564860`

Matched gameplay showed:

- fast path dominates graphics Uniform processing
- measured gameplay fast reason was entirely adaptive `fastSkip`; `fastAlignment=0`
- classic cached path was mostly clean
- exact `(stage,index,device_addr,size)` fast keys repeat heavily across Draws
- `sameDraw=0`

Therefore the previous tiny Uniform `uploadReq` explosion is overwhelmingly created by Eden's adaptive fast mapped-stream policy rather than by classic cached dirty uploads.

### `exp/x1-uniform-payload-fingerprint`

Authorized build:

- workflow `Build dc95 X1 Uniform Payload Fingerprint`
- run `33040377420`
- job `98412364840`
- attempt 1
- build HEAD `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- result success
- artifact `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id `9634160587`
- SHA-256 `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

Current payload diagnostic uses deterministic 1/16 key sampling and fingerprints the already-copied staging span; it does not perform a second guest-memory read and does not skip/reuse/batch Uniform work.

Latest matched runtime conclusion recorded in `CURRENT_HANDOFF.md` / `DEBUG_HISTORY.md`:

- fast streams: 41,188,346 / 41,733,585 visits = 98.69%
- fastAlignment = 0
- fastSkip = 41,188,346
- cached clean = 513,129 / 545,239 = 94.11%
- tracked repeat payload samples: 1,835,334
- same fingerprint: 1,792,196
- changed fingerprint: 43,138
- tracked repeated samples: 97.65% same fingerprint
- same-frame classified repeats: 99.17% same fingerprint

Interpretation:

The dominant adaptive fast Uniform path repeatedly stages the same Uniform identity, and sampled repeated identities overwhelmingly carry the same payload fingerprint. This is strong runtime evidence of avoidable-looking re-stream traffic, but it is not yet permission to reuse old staging allocations because descriptor/staging lifetime and in-flight GPU use must remain correct.

## Current performance picture

Normal ~20 FPS ceiling:

- dominant adaptive tiny-Uniform mapped re-stream pressure
- valid recurring alias image synchronization / render-pass disruption remains secondary

Severe 3–6 FPS dips:

- persistent costs above
- plus bulk staging
- Vertex/Index copy spikes
- texture refresh spikes

Do not force the normal ceiling and severe dips into one root cause.

## Next experiment

The next causal A/B is **Qualcomm/X1 adaptive Uniform cache A/B**.

Goal:

- A/B OFF = exact existing dc95 behavior
- A/B ON = prevent only adaptive `fastSkip` from selecting the mapped-stream path
- alignment-required streaming must remain unchanged
- affected Uniforms must fall through to Eden's existing classic cached `SynchronizeBuffer()` path
- do not alter dirty tracking, staging/descriptor lifetime, scheduler, barriers, render-pass behavior or alias synchronization

This is deliberately safer than custom payload dedupe/reuse. It directly asks whether Eden's fast-stream policy is responsible for the steady ~20 FPS ceiling, and whether routing through the existing cached path introduces the freeze/stall tradeoff observed in Ryubing/Kenji.

See:

- `CURRENT_HANDOFF.md`
- `DEBUG_HISTORY.md`
- `NEXT_ACTION_UNIFORM_CACHE_AB.md`
- `HANDOFF_PROMPT.md`

## Build safety

No ARM64 GitHub Actions build may be started or re-run without fresh explicit user authorization.

**One authorization = one build attempt.**

Current payload-fingerprint build attempts: **1, successful**.

Next build authorization: **not granted**.
