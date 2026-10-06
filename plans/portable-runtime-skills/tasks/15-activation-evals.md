# Add optional skill activation evaluations

Type: task
Status: open
Blocked by: 05
Test first: yes

Optional. Nothing else in this plan waits on it, and it can be dropped.

Add an opt-in real-agent evaluation harness for representative skill activation. Cases cover direct invocation, indirect intent for implicitly invocable skills, incomplete arguments, prompts that must not activate an explicit-only skill, unsupported runtime requests, and edge cases that must not invent a feature or ticket. Keep expected cases as data so adding a skill does not require copying harness logic. Offline tests validate the case files and use deterministic fake-agent responses; real Claude or Codex execution requires an explicit environment switch and never runs by default.

Include `drive-flow` in the runtime-boundary cases: a Codex request for it produces a clear explanation rather than redirecting to a nonexistent skill.

## Not in this ticket

- Running paid evaluations in ordinary CI or defining a scheduled job.

## Done when

- Offline tests load every evaluation case, reject duplicate IDs and unknown skill names, and cover direct, indirect, incomplete, negative, unsupported-runtime and edge categories.
- The opt-in harness exits 2 with an actionable message when credentials or the requested CLI are unavailable and makes no model call without its explicit enable flag.
- `drive-flow` appears only in Claude cases, and every common skill has cases for each supported runtime.
- `bash tests/run.sh` exits 0 without network access or a model invocation.

## Reference

- spec.md § Stories, Edge cases
- `tests/run.sh` fake Claude and fake Codex helpers
- `tests/smoke-real.sh` opt-in convention

## Answer
