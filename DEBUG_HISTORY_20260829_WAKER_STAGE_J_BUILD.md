# DEBUG HISTORY — 2026-08-29 Waker Stage J ARM64 Build

## Scope

One explicitly authorized Windows ARM64 build of Stage J selected-producer caller-depth instrumentation.

Fixed Eden source:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-waker-stage-j-caller-depth`

Current ARM64 authorization after this run: **NONE**.

## Authorization / dispatch

The user supplied one fresh `ㄱㄱ`, consumed for exactly one Stage J ARM64 attempt.

The persistent workflow remained manual-only:

`.github/workflows/build-dc95-x1-address-arbiter-attribution.yml`

`on: workflow_dispatch:`

Because the connector did not expose a direct workflow-dispatch write action, one temporary push-triggered dispatcher was created on the same branch, POSTed exactly once to the persistent workflow, and was immediately deleted after the Stage J ARM run appeared.

Dispatcher creation commit:

`516162fd94ee751b7ac54ff68986f867329dcca7`

Dispatcher deletion commit:

`0e0ebc6d68cee6261c31d2b9daaa3c351f26c4dd`

No additional dispatch, retry, or rerun occurred.

## ARM run identity

- workflow: `Build dc95 X1 Waker Stage J`
- run: `33249991294`
- job: `99093918714`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `516162fd94ee751b7ac54ff68986f867329dcca7`
- runner: `windows-11-arm`
- conclusion: **SUCCESS**

The workflow API again displayed a stale historical `display_title` string for this persistent workflow, but workflow name and job name identify the run as Stage J.

## Successful chain

The single attempt passed all retained validation/build stages:

1. exact dc95 checkout verification;
2. retained non-scheduler diagnostic patches;
3. focused attribution chain through Stage C;
4. Stage D CPU/scheduler attribution;
5. Stage E recursive arbiter attribution;
6. Stage F producer attribution;
7. Stage G focused producer CPU attribution and invariant checks;
8. Stage H module mapping and invariant checks;
9. Stage J selected-producer caller-depth application;
10. Stage J pre-configure safety/invariant checks;
11. MSYS2 CLANGARM64 setup;
12. dc95 ARM64 configure;
13. ARM64 compile;
14. Eden Windows package;
15. analyzer / metadata addition;
16. artifact upload.

No retry/rerun/additional ARM attempt was used.

## Artifact

Canonical artifact result from the dedicated Actions artifact query:

- name: `Eden-dc95-X1-waker-stage-j`
- artifact ID: `9714363715`
- size: `31,423,548` bytes
- SHA-256: `27b250b40b879eeeea0a33e8ded66d3e0e229aef22d67f4027715bedf240f7b8`
- created: `2026-08-29T11:50:01Z`
- expires: `2026-09-12T11:49:58Z`
- expired: false
- workflow run: `33249991294`
- head branch: `exp/x1-waker-stage-j-caller-depth`
- head SHA: `516162fd94ee751b7ac54ff68986f867329dcca7`

## Conclusion

Stage J ARM64 build succeeded on the first and only authorized attempt.

Current ARM64 authorization: **NONE**.

Any later Windows ARM64 build/rebuild/rerun requires a new explicit user authorization.