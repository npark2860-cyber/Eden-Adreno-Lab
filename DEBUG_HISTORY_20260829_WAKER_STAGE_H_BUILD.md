# DEBUG HISTORY — Waker Stage H ARM64 Build

Updated: 2026-08-29 KST

## Scope

This record covers the single authorized Windows ARM64 build of Stage H only. It does not change the fixed Eden baseline or authorize any further ARM64 attempt.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Source branch:

`exp/x1-waker-stage-h-module-callpath-mapping`

Persistent workflow:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

Persistent trigger remains:

`workflow_dispatch` only.

## Authorized attempt

Exactly one Stage H ARM64 attempt was created from the fresh authorization.

- workflow: `Build dc95 X1 Waker Stage H`
- run: `33246620972`
- job: `99085091095`
- attempt: `1`
- event: `workflow_dispatch`
- build HEAD: `1c8b699ccc51ff7bca28fc57bf654c1e18fbd5f2`
- conclusion: `success`
- retry: none
- rerun: none
- additional ARM64 attempt: none

The build HEAD contained the one-shot dispatcher commit used only to issue the approved manual workflow dispatch. That dispatcher was removed immediately afterward. Current branch HEAD after removal is `135d13a57d434e23d7f68928d0f335ed959d0892` (`Remove one-shot Stage H ARM64 dispatcher`). The persistent ARM workflow itself remains manual-only.

A later `ㄱㄱ` arrived while this same run was still active. It was used only to continue resolving the already-running attempt and was **not** consumed as authorization for a second ARM64 run. Current ARM64 authorization is therefore `NONE`.

## Verified build chain

The successful job verified and completed all of the following in the same attempt:

1. checkout of the exact known-good Eden source;
2. exact source verification at `dc95cd09eea9749250fe31a3072684d341d19417`;
3. retained non-scheduler patches;
4. retained X1 diagnostic chain;
5. focused attribution layers through Stage C;
6. Stage D CPU/scheduler attribution;
7. Stage E recursive arbiter attribution;
8. Stage F producer attribution;
9. Stage G focused producer CPU attribution and pre-Stage-H verification;
10. Stage H guest module mapping;
11. Stage H pre-configure verification;
12. MSYS2 CLANGARM64 setup;
13. dc95 ARM64 standard configure;
14. ARM64 compile;
15. Eden Windows package step;
16. analyzer/metadata addition;
17. artifact upload.

Stage H pre-configure validation also retained the relevant safety invariants:

- no hardcoded observed `0x80`, `0x81`, `0x210b...`, or `0x2181...` runtime observations in the Stage G/H additions;
- no Stage H scheduler hook;
- no priority/affinity/core/yield/reschedule/sleep/wait/signal/QueueBuffer/swap-interval behavior mutation;
- Stage G selected-producer sampling shape remains intact;
- Stage H adds bounded guest-module mapping evidence through the existing loader truth.

## Artifact

Exactly one artifact was uploaded:

- name: `Eden-dc95-X1-waker-stage-h`
- artifact ID: `9797889460`
- size: `31,414,690` bytes
- SHA-256: `d41d53def266705924a928716909532475f73e29a94c25ec513730aca4493d92`
- created: `2026-08-29T10:24:02Z`
- expires: `2026-11-27T10:23:59Z`

GitHub reported the digest directly as:

`sha256:d41d53def266705924a928716909532475f73e29a94c25ec513730aca4493d92`

## Conclusion

Stage H is no longer build-pending. The exact dc95 Windows ARM64 binary carrying Stage A-H diagnostics was built and packaged successfully in one authorized attempt.

No optimization conclusion follows from build success alone.

## Next action

Run `Eden-dc95-X1-waker-stage-h` under the same TOTK 1.2.1 gameplay capture conditions used for Stage G, with behavior-changing A/Bs OFF and enough 120-frame windows to isolate pure swap2 and pure swap3 periods.

Then analyze together:

- `[X1-WAKERH]` module ranges;
- `[X1-WAKERG]` selected-producer top saved PC/LR contexts;
- `[X1-WAKERF]` producer CPU/Waiting trend;
- raw QueueBuffer cadence.

Use:

`tools/adreno_lab/analyze_x1_waker_stage_h_module_mapping.py <eden_log>`

Canonical cross-run identity is `module+offset`; raw absolute PC/LR remains audit evidence only.

Keep producer CPU growth, producer Arbitration growth, and the separate Stage D dynamic-waker CPU branch distinct until direct evidence joins them.
