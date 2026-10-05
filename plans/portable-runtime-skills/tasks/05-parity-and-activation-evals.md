# Add cross-runtime parity and skill activation evaluations

Type: task
Status: open
Blocked by: 04
Test first: yes

Add deterministic parity checks over the canonical skills and both rendered installations. Compare shared sections and resources, allow only declared runtime fragments and metadata differences, and produce a focused diff naming the skill when the renderers drift.

Add an opt-in real-agent evaluation harness for representative skill activation. Cases cover direct invocation, indirect intent for implicitly invocable skills, incomplete arguments, prompts that must not activate an explicit-only skill, unsupported runtime requests, and edge cases that must not invent a feature or ticket. Keep expected cases as data so adding a skill does not require copying harness logic. Offline CI validates the case files and uses deterministic fake-agent responses; real Claude or Codex execution requires an explicit environment switch and never runs by default.

Include `drive-flow` in the runtime-boundary cases: Claude output contains it, Codex output and plugin inputs do not, and an unsupported Codex request produces a clear explanation rather than redirecting to a nonexistent skill.

## Not in this ticket

- Running paid evaluations in ordinary CI or defining a scheduled job.
- Building the plugin artifact; the packager consumes the verified Codex-supported set later.

## Done when

- The parity command exits 0 for current generated outputs and fails a fixture with an undeclared body difference, printing the skill and differing section.
- Offline tests load every evaluation case, reject duplicate IDs and unknown skill names, and cover direct, indirect, incomplete, negative, unsupported-runtime and edge categories.
- The opt-in harness exits 2 with an actionable message when credentials or the requested CLI are unavailable and makes no model call without its explicit enable flag.
- Tests prove `drive-flow` is present only in Claude cases and outputs, while every common skill has cases for each supported runtime.
- `bash tests/run.sh` exits 0 without network access or a model invocation.

## Reference

- spec.md § Stories, Edge cases
- canonical skills and renderers completed by ticket 04
- `tests/run.sh` fake Claude and fake Codex helpers
- `tests/smoke-real.sh` opt-in convention

## Answer
