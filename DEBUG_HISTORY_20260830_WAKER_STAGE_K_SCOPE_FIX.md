# DEBUG HISTORY — 2026-08-30 Waker Stage K Scope Fix

## Scope

Record the compile-blocking Stage K integration defect discovered after the first Stage K Windows ARM64 attempt, the minimal source fix, and the Ubuntu-only regression validation.

Fixed Eden baseline:

`eden-emulator/mirror@dc95cd09eea9749250fe31a3072684d341d19417`

Branch:

`exp/x1-waker-stage-k-grandparent-depth`

Current ARM64 authorization: **NONE**.

No ARM64 rebuild, retry, or rerun was performed during this fix/validation step.

## Failed Stage K ARM64 attempt

The prior single authorized Stage K Windows ARM64 attempt was:

- workflow: `Build dc95 X1 Waker Stage K`
- run: `33254495504`
- job: `99105748612`
- attempt: `1`
- event: `workflow_dispatch`
- build/source HEAD: `c64f01a03dba7606061ddb8e8aa9fecad91051ee`
- exact dc95 checkout: success
- retained chain reconstruction through Stage J: success
- Stage K snapshot/application/pre-configure verification: success
- configure: success
- C++ build: **FAILED**
- artifact count: `0`
- retry/rerun: none

The failed attempt did not authorize another ARM64 attempt.

## Root cause

The simple enum-name mismatch hypothesis was rejected: the exact build-head Stage J/K sources use the expected nested enum names (`ParentStatus` and `GrandparentStatus`).

Read-only generated-source inspection then identified a deterministic C++ lexical-scope error in the Stage K transplant.

Stage J declares its memory reference inside a local `else` block:

```cpp
auto& x1_stage_j_memory = kernel.System().ApplicationMemory();
```

Stage K was appended after that Stage J block and attempted to reuse the now-out-of-scope local:

```cpp
auto& x1_stage_k_memory = x1_stage_j_memory;
```

That generated source is unconditionally ill-formed C++ because `x1_stage_j_memory` is no longer visible at the Stage K insertion point.

A minimal local Clang C++20 reproduction of the same lexical structure fails with an undeclared-identifier diagnostic. Replacing the initializer with a fresh reference obtained in the Stage K scope compiles successfully.

## Minimal fix

Only the Stage K transplant was changed:

```diff
- auto& x1_stage_k_memory = x1_stage_j_memory;
+ auto& x1_stage_k_memory = kernel.System().ApplicationMemory();
```

Fix commit:

`29d4c8ef376448bd7c61d354eb125fc052ac5c0e`

No Stage F/G/J profiler logic, producer selection, frame-depth logic, scheduler behavior, GPU behavior, waits/signals, priority/affinity, QueueBuffer, cadence, or A/B behavior was changed.

The Stage K memory-read shape remains exactly:

- one Stage J existing parent-LR read;
- two Stage K added frame-record reads;
- three total selected-producer `Read64` sites.

## Ubuntu regression validation

A temporary Ubuntu-only one-shot validator reconstructed exact dc95 through Stage J, applied Stage K, and repeated the previous structural checks.

Additional regression coverage specifically targeted the defect that the original static gate missed: the generated Stage K memory initializer was checked with a C++20 syntax-only scope probe so an out-of-scope initializer cannot silently pass the gate again.

Validation:

- workflow: `Validate dc95 X1 Waker Stage K Scope Fix`
- run: `33279373418`
- job: `99171791300`
- attempt: `1`
- event: `push`
- validation HEAD: `3f0843208512d2878f8f02a8c7938216bf5ecf21`
- result: **SUCCESS**

The core validation step `Reconstruct A-J and validate Stage K scope fix` completed successfully.

Validated:

- exact dc95 checkout;
- A-J reconstruction;
- Stage K application;
- existing Stage K structural/read/range/invariant checks;
- Python syntax/analyzer checks;
- actual generated Stage K memory initializer uses `kernel.System().ApplicationMemory()`;
- generated initializer does not reference `x1_stage_j_memory`;
- C++20 `-fsyntax-only` scope regression probe passes;
- no ARM runner was used.

Temporary validator cleanup commit:

`404a14af5a607762bd121dd98190d63c5c4466c0`

## Conclusion

The first Stage K build exposed a static-gate coverage hole rather than evidence against the Stage K attribution design itself.

The compile-blocking lexical-scope defect is fixed and the strengthened Ubuntu/static gate passes.

This does **not** prove that a full Windows ARM64 Stage K build will succeed; it only removes the identified deterministic compile blocker and adds a regression check for it.

A new Windows ARM64 Stage K attempt requires a separate fresh explicit user authorization. Generic continuation/read-only approval does not consume or imply ARM64 authorization.
