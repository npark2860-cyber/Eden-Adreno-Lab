# CURRENT HANDOFF — Eden Adreno X1 Uniform fast-stream diagnosis

Updated: 2026-08-27 KST

## Fixed baseline

- Lab repository: `npark2860-cyber/Eden-Adreno-Lab`
- Exact Eden source: `dc95cd09eea9749250fe31a3072684d341d19417`
- Immutable control: `lab/dc95-arm64-baseline`
- Completed texture experiment: `exp/x1-texture-fill-reasons`
- Completed alias-route experiment: `exp/x1-alias-copy-reasons`
- Completed alias-redundancy experiment: `exp/x1-alias-sync-redundancy`
- Completed Uniform path experiment: `exp/x1-uniform-stream-reuse`
- Current completed diagnostic: `exp/x1-uniform-payload-fingerprint`

**No ARM64 build may be started or re-run without fresh explicit user permission. One permission = one attempt.**

## Latest successful diagnostic build

X1 Uniform Payload Fingerprint:

- workflow: `Build dc95 X1 Uniform Payload Fingerprint`
- run: `33040377420`
- job: `98412364840`
- attempt: 1
- build HEAD: `9f1a916c7eaa72f3921cfa49233756dbbba5c3d9`
- result: **success**
- artifact: `Eden-dc95-X1-uniform-payload-fingerprint`
- artifact id: `9634160587`
- size: 31,299,993 bytes
- SHA-256: `de68710492c8c221a8936cef97bb6d876dd44f409cd2d75074cee18bcab6106f`

The workflow was restored to `workflow_dispatch` only after the authorized push-triggered run. No second run was created.

## Latest matched runtime

Log: `eden_log(20260827-052251).txt`

- TOTK 1.4.2
- Qualcomm Adreno X1-85
- Qualcomm driver 512.863.0
- Vulkan 1.3.295
- Windows 11 25H2 build 26220.9223
- Eden source identification: `HEAD-dc95cd09ee-HEAD`
- reached >3000 frames
- end `ForceStop` is the user's intentional stop after enough logging; do not classify it as a crash

## Closed alias result

Repeated alias copy pair/region traffic is **not** trivial unchanged-state duplication:

- same source modification tick among tracked repeats: 0
- every tracked repeat advanced source tick
- same-state + same-region candidates: 0

Do not pursue simple alias copy dedupe or suppress required outside-render-pass `vkCmdCopyImage` work.

## Exact dc95 Uniform source facts — CONFIRMED

1. Vulkan `HAS_PERSISTENT_UNIFORM_BUFFER_BINDINGS = false`.
2. Vulkan therefore revisits enabled graphics Uniform bindings instead of preserving the OpenGL-style binding dirty mask.
3. Classic cached path calls `SynchronizeBuffer()` and can finish with zero upload when the guest range is clean.
4. `uniform_cache_hits` counts that zero-upload outcome.
5. The adaptive small-Uniform fast path is a stall-avoidance stream path, not payload reuse.
6. Fast Vulkan Uniform path requests upload staging, adds a descriptor and copies guest bytes again.

## Uniform path runtime — CONFIRMED

Previous `exp/x1-uniform-stream-reuse` runtime proved:

- fast path dominates gameplay Uniform processing
- gameplay fast reason is adaptive `fastSkip`, not alignment (`fastAlignment=0`)
- classic cached path is mostly clean
- repeated exact `(stage,index,device_addr,size)` keys dominate
- `sameDraw=0`: repetition occurs across Draws, not inside one Draw

Therefore the existing Uniform upload explosion is primarily created by Eden's adaptive mapped re-stream policy, not by classic cached dirty uploads.

## Uniform payload fingerprint runtime — STRONG CONFIRMED EVIDENCE

Current instrumentation:

- deterministic 1/16 Uniform-key sampling
- fingerprint from the already-copied staging span; no second guest-memory read
- bounded fixed table
- instrumentation only; no work skipped/reused/batched

Gameplay aggregate: report frames 1320–3000 inclusive = 1800 frames.

### Path totals

- visits: **41,733,585**
- fast streams: **41,188,346 = 98.69%**
- fastAlignment: **0**
- fastSkip: **41,188,346**
- cached: **545,239**
- cachedClean: **513,129 = 94.11% of cached**
- cachedUpload: **32,110**
- average fast payload: **410.46 bytes**
- fast streams/frame: **22,882.4** for this matched route

### Payload sample totals

- samples: **1,890,393**
- uniqueSamples: **14,526**
- repeatSamples: **1,835,334**
- sameFingerprint: **1,792,196**
- changedFingerprint: **43,138**
- sampleOverflow: **40,533**

Among tracked repeated sampled keys:

- **97.65% same fingerprint**
- **2.35% changed fingerprint**

Among same-frame repeated samples with fingerprint classification:

- same: **1,445,069**
- changed: **12,119**
- **99.17% same fingerprint**

Representative stability:

- frame 1440: 96.60% same fingerprint
- frame 1560: 95.47%
- frame 2400: 97.64%
- frame 2880: 98.23%

The effect is persistent across the gameplay run rather than a single spike.

## Interpretation boundary

The data now supports:

> Eden's dominant adaptive fast Uniform path repeatedly stages the same Uniform identity, and sampled repeat events overwhelmingly carry the same payload fingerprint, especially within one frame.

Do **not** jump directly to `same key/hash => reuse previous staging allocation` yet. Correctness still requires preserving descriptor/staging lifetime and in-flight GPU use. A 64-bit fingerprint is strong equality evidence but not mathematical byte-for-byte proof.

## Most conservative next A/B

Do not invent a custom dedupe first.

The safest causal test is a Qualcomm/X1 debug A/B that:

- leaves alignment-required streaming unchanged
- when enabled, disables only the adaptive small-Uniform skip-cache decision
- routes those Uniforms through Eden's existing classic cached `SynchronizeBuffer()` path
- does not change memory dirty semantics, descriptor lifetime, barriers, render-pass behavior or scheduler behavior

Why this is the best next test:

- current fast traffic is 100% `fastSkip`, 0 alignment in measured gameplay
- classic cached traffic is ~94% clean, so existing Eden logic already knows how to avoid the physical upload for many ranges
- it directly tests whether re-streaming causes the ~20 FPS ceiling
- if FPS rises without freezing, the optimization direction is validated
- if FPS rises but freezing/stalls appear, that directly mirrors the Ryubing/Kenji tradeoff the user observed and tells us where lifetime/stall mitigation is required
- if FPS does not improve, the fast streaming count is visually large but not the main frame-time cause

## What NOT to do next

- no ARM64 Actions without fresh explicit permission
- no alias trivial dedupe
- no render-pass/barrier suppression
- no blind persistent-binding enable
- no blind previous-staging reuse
- no global change to all vendors
- no removal of alignment-required fast streaming
- do not treat `ForceStop` as a crash

## NEXT ACTION

Prepare a new branch for a **Qualcomm/X1 adaptive Uniform cache A/B** with a debug checkbox, default OFF.

A/B OFF must be exact existing behavior.

A/B ON must only prevent `fastSkip` from selecting the mapped-stream path; `needs_alignment_stream` remains authoritative and the existing classic cached path handles the Uniform.

Static validation must prove the delta does not touch scheduler, alias copies, barriers, render-pass requests, memory dirty state or descriptor/staging lifetime code.

After preparation, stop before Actions. One future explicit user authorization permits exactly one ARM64 build attempt.

## Current build authorization state

- current diagnostic branch: `exp/x1-uniform-payload-fingerprint`
- payload-fingerprint build attempts: 1, successful
- next build authorization: **not granted**
- gameplay optimization applied: none
- Uniform payloads skipped/reused/batched: none
- alias copies skipped: none
- barriers/render-pass requests suppressed: none
