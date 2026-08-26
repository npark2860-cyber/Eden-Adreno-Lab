# Eden Adreno Lab

Repository bootstrap for the Windows ARM64 Snapdragon X / Adreno X1-85 Eden investigation.

## Canonical references

Read in this order:

1. `TECH_BIBLE.md` — durable technical facts, architecture, invariants, experiment rules
2. `DEBUG_HISTORY.md` — chronological experiment/build/runtime history
3. `CURRENT_HANDOFF.md` — current branch/build/log state and the exact next action

## Immutable control

- Eden source: `eden-emulator/mirror`
- exact known-good SHA: `dc95cd09eea9749250fe31a3072684d341d19417`
- Lab control branch: `lab/dc95-arm64-baseline`

`0295dc5fff9b2977e753e7c126cc870abb07ee3f` is later source and must not be used as the dc95 control surrogate.

For a new ChatGPT tab, start from `CURRENT_HANDOFF.md` only after reading the two canonical history/reference documents above and verifying the live GitHub branch HEAD.
