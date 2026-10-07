# Send the Codex skill's Plan section through the brief and the planner

Type: task
Status: open
Blocked by: 02, 03, 04
Test first: no

The Claude skill's new Plan section (spec.md § Design), ported to `adapters/codex/feature-flow/SKILL.md`, with Codex's spawning: `spawn_agent(task_name="feature_planner", fork_turns="none", ...)` and `task_name="plan_reviewer"`, then `wait_agent`. Say that the planner's tools cannot be limited on Codex and the draft folder plus `plan-accept` contain it, and that without web search the planner plans from the codebase and says so. Role files come from `.agents/flow-roles/`.

## Not in this ticket

- A Codex hand run: there are no Codex tokens (spec.md § Scope).

## Done when

- `bash tests/run.sh` prints `ok` for checks that the Codex skill names `plan-prompt`, `plan-review-prompt`, `plan-accept`, `feature-planner`, `plan-reviewer` and `guides/brief.md`, plus that it names `fork_turns="none"` for the planner, and the existing check that it never says `/feature-flow` or `$ARGUMENTS` still passes.
- All existing tests still pass.

## Reference

- adapters/codex/feature-flow/SKILL.md, guides/brief.md

## Answer
