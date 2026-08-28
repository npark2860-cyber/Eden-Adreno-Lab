# DEBUG HISTORY — Address Arbiter Dynamic Signal Target

Updated: 2026-08-28 KST

## Trigger

Stage B v1 hard-coded the gameplay wait address observed in one run:

- first Stage A runtime: `0x210adbc120`
- next Stage B runtime: `0x210b5bc120`
- delta: `+0x800000` (8 MiB)

The second runtime still showed one stable post-warmup `WaitIfEqual(timeout=-1)` gameplay key, but `[X1-ADDRSIG]` stayed empty because the signal-side profiler compared against the old absolute guest VA.

Conclusion: the logical wait object is stable within a run, but its absolute guest VA is not stable across launches.

## Minimal correction

Only the Address Arbiter transplant path was changed.

Generated exact-dc95 profiler behavior now:

1. first 120 rendered frames remain warmup;
2. only the dynamic guest-submit target thread is observed, as before;
3. the first post-warmup `WaitIfEqual` call with `timeout=-1` atomically latches its nonzero guest address into `target_signal_address`;
4. `BeginTargetWait`, `EndTargetWait`, and `SignalToAddress` attribution operate only on that latched address;
5. later addresses cannot replace the latch;
6. no wait, signal, scheduler, GPU, cadence, or queue semantics are changed.

The old fixed literal `0x210adbc120ULL` and `TargetSignalAddress` constant are removed from the generated profiler.

## Static verification

Ubuntu-only one-shot run:

- run: `33167902631`
- job: `98837619252`
- conclusion: `success`
- ARM64 runner: not used

Verified on exact `eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417` with the retained diagnostic chain:

- dynamic target initialization exists;
- compare-exchange latch exists;
- latch condition is `arbitration_type == 2 && timeout_ns == -1`;
- signal filter reads the runtime target;
- `[X1-ADDRSIG]` remains present;
- fixed Stage B v1 address is absent from generated source;
- `WaitAddressArbiter`, `SignalAddressArbiter`, SVC wrappers, and validation call counts are unchanged;
- no behavior-changing wait/scheduling/GPU policy leaked into the SVC diff.

The temporary static workflow was deleted after success.

## Current state

Source correction commit:

`77ca0cb6bde0416faaf335f092cba56c2e8e7baa`

Current ARM64 authorization: **NONE**.

Do not build or rerun ARM64 until the user provides a fresh explicit one-attempt authorization.

## Next runtime question after a newly authorized build

Confirm that `[X1-ADDRSIG] addr=` automatically matches the current run's `[X1-ADDRARB] top0=` address, then identify:

- signaling guest TID;
- signal type/count;
- wait-start -> signal (`w2s`);
- signal -> wait-end (`s2e`).

If `w2s` owns the long wait and `s2e` is near zero, the next target is the waker thread's work immediately before `SignalToAddress`.
