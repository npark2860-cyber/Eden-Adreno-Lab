# NEXT ACTION — X1 Uniform payload fingerprint

Current branch: `exp/x1-uniform-payload-fingerprint`

Exact Eden source remains fixed at:

`dc95cd09eea9749250fe31a3072684d341d19417`

## Runtime goal

Use the same matched TOTK 1.4.2 setup and collect the new:

`[X1-UNIFORM-PAYLOAD]`

aggregate line together with the retained `[X1-UNIFORM-PATH]` and `[X1-FLOW][BUFFER]` telemetry.

## Primary decision

For sampled repeated exact fast Uniform keys `(stage,index,device_addr,size)`, compare:

- `sameFingerprint`
- `changedFingerprint`

If `sameFingerprint / repeatSamples` is high, repeated fast-stream traffic often carries the same sampled payload and persistent/reuse-oriented optimization becomes a concrete next target.

If `changedFingerprint / repeatSamples` is high, the same key is usually being rewritten and the better target is fast-stream allocation/copy/descriptor overhead rather than payload reuse.

## Guards

- `sampleOverflow` must be considered when interpreting coverage.
- `sameFingerprint + changedFingerprint` should equal `repeatSamples` for classified repeats.
- hash equality is strong evidence but not mathematical byte equality.
- do not implement a correctness-affecting skip from telemetry hashes.
- do not enable persistent Vulkan Uniform bindings or alter skip-cache policy before the runtime result.
- do not trade Eden stability for an unmeasured freeze/stall regression.

## Build safety

No re-run is allowed without fresh explicit user authorization. One authorization = one ARM64 build attempt.
