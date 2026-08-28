# Handoff Prompt — Eden Adreno X1 Address Arbiter Attribution

Use this prompt when continuing in a new tab.

---

Eden Windows ARM64 / Snapdragon X Elite / Adreno X1-85 performance diagnosis를 이어간다.

GitHub repository:

`npark2860-cyber/Eden-Adreno-Lab`

Current branch:

`exp/x1-guest-post-wait-attribution`

Do not reconstruct state from old chat. GitHub documents are source of truth.

First read:

1. `LAB_BOOTSTRAP.md`
2. `CURRENT_HANDOFF.md`
3. `DEBUG_HISTORY.md`
4. `DEBUG_HISTORY_20260827_CONTINUED.md`
5. `DEBUG_HISTORY_20260828_CONTINUED.md`
6. `DEBUG_HISTORY_20260828_GPU_SUBMIT.md`
7. `DEBUG_HISTORY_20260828_GUEST_SUBMIT.md`
8. `DEBUG_HISTORY_20260828_GUEST_POST_WAIT.md`
9. `NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md` — completed
10. `NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md` — current next action
11. `NEXT_ACTION_NVDRV_IPC_DISPATCH_GAP.md` — completed predecessor
12. `GUEST_SUBMIT_WAIT_SOURCE_MAP.md`
13. `HANDOFF_PROMPT.md`

Then verify actual branch HEAD/workflow state before editing anything.

Fixed Eden baseline — never change without explicit baseline-change procedure:

`eden-emulator/mirror`
`dc95cd09eea9749250fe31a3072684d341d19417`

Guest Post Wait experiment cleanup/code anchor before documentation:

`d9df8d7f594c3030ee518a2bd489a15708ad87b4`

Documentation commits may advance the branch HEAD. Verify that changes after this code anchor are documentation-only unless later source work is explicitly recorded.

Hard ARM64 rule:

- never build/rebuild/rerun ARM64 Actions without fresh explicit user authorization
- one authorization = exactly one attempt
- failure does not authorize a retry
- current ARM64 authorization = NONE

Persistent Guest Post Wait workflow:

`.github/workflows/build-dc95-x1-guest-post-wait-attribution.yml`

must remain `workflow_dispatch` only.

Completed approved Guest Post Wait build:

- run `33150086343`
- job `98779808729`
- build HEAD `d4cbe0ba893a61650583926434261565242bca3f`
- success
- artifact `Eden-dc95-X1-guest-post-wait-attribution`
- artifact id `9678004761`
- size `31,349,148` bytes
- SHA-256 `4c310923a53b3cfd337893329b1fbd41e317a79200139ae559064a520e882ee9`

The earlier run `33149694136` failed before ARM compile because WSL `bash` was selected instead of Git Bash. Corrected one-shot workflow/marker were removed after the successful build.

Retain the closed causal chain from `CURRENT_HANDOFF.md`:

- BufferQueue free-slot/backpressure is not the primary owner
- cadence/raw swap3/DFPS are downstream symptoms, not root frame-production cause
- measured RasterizerVulkan work explains only a minority of the slow frame
- GPU worker is starved in queueWait waiting for upstream command supply
- lower NVDRV/GPFIFO path is fast once candidate handler starts
- guest `tid=0x53` owns essentially all candidate submits and is only ~1-2% CPU-share
- NVDRV IPC dispatch/service is ~0.02-0.05 ms/request and not the missing 20-30 ms

Completed Guest Post Wait runtime:

`eden_log(20260828-080040).txt`

Environment:

- exact dc95
- TOTK 1.2.1
- Windows 11 25H2 build 26220.9223
- Adreno X1-85 / driver 512.863.0 / Vulkan 1.3.295
- swap3->2 clamp OFF
- Descriptor Ring happened to remain ON but sampled DBUF `alloc=0`, `reuseWait=0`; do not rerun only because of this.

Critical runtime result:

> The dominant submitter's C -> next candidate request interval is overwhelmingly KThread Waiting (~96-99% in steady reports), not CPU execution and not nvservices dispatch.

Fast AddressArbiter examples:

- frame 240: `1.253 ms/frame`
- frame 480: `1.080`
- frame 600: `2.595`
- frame 720: `1.112`
- frame 840: `1.030`

Transition/slow:

- frame 360, raw swap2: `23.771 ms/frame`
- frame 960 transition->swap3: `57.526`
- frame 1080 stable slow: `26.751`
- frame 1200 stable slow: `50.103`

Critical counterexample:

- frame 1320 stable slow: wall `50.227 ms/frame`, `guestPostAvg=24.228 ms`, `waitShare=98.89%`
- `Arbitration=8.615 ms/frame`
- `None=40.741 ms/frame`

Therefore do NOT conclude that Arbitration alone owns the entire slowdown.

Current defensible conclusion:

> Guest-post slowdown is KThread Waiting dominated. A once-per-frame AddressArbiter wait frequently expands sharply with slowdown, but unclassified None waits can also dominate a stable-slow window.

Profiler/source correctness already reviewed:

- `BeginWait()` enters Waiting before wait reason is assigned
- profiler classifies at Waiting exit using old reason captured before baseline clear, so recorded Arbitration duration is valid
- `topSvc0=0x0` is broken attribution because exact dc95 never populates `current_svc_id` and the transplant installs no recorder
- reply-wake exclusion is count-consistent in steady windows

Exact dc95 Arbitration mapping:

`Svc::WaitForAddress` (`0x34`)
-> AddressArbiter
-> `WaitIfLessThan` / `DecrementAndWaitIfLessThan` / `WaitIfEqual`
-> KThread reason `Arbitration`.

Wake side:

`Svc::SignalToAddress` (`0x35`).

Mutex `ArbitrateLock` and process-wide condition-variable waits use `ConditionVar` reason, not `Arbitration`.

`arbN=120` in every non-startup 120-frame report means one completed AddressArbiter wait per rendered frame for `tid=0x53`.

NEXT ACTION:

Read `NEXT_ACTION_ADDRESS_ARBITER_ATTRIBUTION.md` and prepare only Stage A:

- direct `Svc::WaitForAddress` observation for target `tid=0x53` / existing guest-post window
- aggregate by `(guest address, ArbitrationType)`
- record count, timeout, total/avg/max blocked duration, and result/timeout status if semantics remain unchanged
- no per-event logs
- no generic SVC profiler
- no scheduler profiler

Only if one address is proven dominant should a later Stage B instrument `SignalToAddress` for that exact address to identify signaler/waker.

If a frame-1320-like `None` wait remains dominant after Stage A, separately identify only the unclassified BeginWait source class for target `tid=0x53`.

Static/source preparation may proceed. Stop before any ARM64 Actions attempt unless the user gives fresh explicit authorization.