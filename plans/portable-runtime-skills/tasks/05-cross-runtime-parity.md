# Add cross-runtime parity checks

Type: task
Status: open
Blocked by: 04, 14
Test first: yes

Add deterministic parity checks over the canonical skills and both rendered installations. Compare shared sections and resources, allow only declared runtime fragments and metadata differences, and produce a focused diff naming the skill when the renderers drift.

Include `drive-flow` in the runtime-boundary checks: the Claude output contains it and the Codex output does not.

## Not in this ticket

- Activation evaluations: ticket 15, which is optional.
- Building the plugin artifact; the packager consumes the verified Codex-supported set later.

## Done when

- The parity command exits 0 for current generated outputs and fails a fixture with an undeclared body difference, printing the skill and differing section.
- Tests prove `drive-flow` is present only in the Claude output, while every common skill renders for each supported runtime.
- `bash tests/run.sh` exits 0 without network access or a model invocation.

## Reference

- spec.md § Stories, Edge cases
- canonical skills and renderers completed by tickets 04 and 14
- `tests/run.sh` fake Claude and fake Codex helpers

## Answer
