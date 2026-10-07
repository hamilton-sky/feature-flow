# Send the Claude skill's Plan section through the brief and the planner

Type: task
Status: open
Blocked by: 02, 03, 04
Test first: no

Rewrite the Plan section of `skills/feature-flow/SKILL.md`: with no feature given and a conversation that describes work, propose the feature from it instead of listing `plans/*/`; with no plan folder, follow `guides/brief.md`, spawning `feature-planner` and `plan-reviewer` subagents with the conductor's prompts and waiting for their final replies. Keep the commit suggestion and the rule that an uncommitted plan is not ready to build. Adding tickets to an existing plan stays a hand edit following `guides/plan.md`'s ticket rules. Check that `feature-planner.md` and `plan-reviewer.md` are installed before planning, as the build path checks the builder and reviewer.

## Not in this ticket

- The Codex skill: ticket 06.
- Anything from `start` with a plan present.

## Done when

- `bash tests/run.sh` prints `ok` for new checks that the Claude skill names `plan-prompt`, `plan-review-prompt`, `plan-accept`, `feature-planner`, `plan-reviewer` and `guides/brief.md`, and the existing `it is under 90 lines` check still passes.
- All existing tests still pass.

## Reference

- skills/feature-flow/SKILL.md, guides/brief.md

## Answer
