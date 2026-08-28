# NEXT ACTION — X1 NVDRV IPC Dispatch Gap Attribution — COMPLETED

Updated: 2026-08-28 KST

## Fixed baseline

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

## Completed build

- workflow: `Build dc95 X1 NVDRV IPC Dispatch Gap`
- run: `33145255519`
- job: `98764725334`
- attempt: 1
- build HEAD: `4edb96cc33c3393df34cbe048600f0fb6b669d61`
- conclusion: SUCCESS
- artifact ID: `9676070821`
- artifact: `Eden-dc95-X1-nvdrv-ipc-dispatch-gap`
- SHA-256: `26d68afae986d8e526b110d8e19826d642d9accda23e68c47d4b8fe13fa93184`
- reruns: 0

## Completed runtime

Log:

`eden_log(20260828-061910).txt`

Representative results:

- frame 840: `guestPostAvg=16.840 ms`, `ipcDispatchAvg=0.021 ms`, `serviceReplyAvg=0.014 ms`
- frame 1320: `guestPostAvg=26.743 ms`, `ipcDispatchAvg=0.017 ms`, `serviceReplyAvg=0.039 ms`
- frame 1440: `guestPostAvg=29.091 ms`, `ipcDispatchAvg=0.027 ms`, `serviceReplyAvg=0.033 ms`
- representative slow reports have `missingA=0`, `missingB=0`
- dominant candidate submitter remains `tid=0x53`, essentially 100%
- submitter CPU share remains ~1-2%

## Closed conclusion

Case A won decisively:

> The missing 20-30 ms is after the prior candidate NVDRV handler completion/reply-adjacent boundary and before the guest issues the next candidate sync request.

Therefore these are not the primary owner in this matched runtime:

- request -> `nvservices` handler dispatch;
- Windows host wake/scheduling latency of `nvservices`;
- Nvidia single-thread ServerManager head-of-line delay before the candidate request;
- lower candidate NVDRV handler/reply body.

## Superseded next action

Do not rerun or extend this pass as the next diagnostic.

Continue with:

`NEXT_ACTION_GUEST_POST_WAIT_ATTRIBUTION.md`

on branch:

`exp/x1-guest-post-wait-attribution`

The next question is whether the dominant guest-side C -> next-submit interval is explained by explicit KThread waits or by Runnable/not-scheduled residual time.

**ARM64 rule remains: no build/rerun without fresh explicit authorization; one authorization = exactly one attempt.**
