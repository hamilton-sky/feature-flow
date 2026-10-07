# Acceptance: turn a conversation into a plan in Claude Code

Type: task
Status: open
Blocked by: 07
Test first: no

A hand run by the user in their own Claude Code session (paid runs are the user's): in a scratch repo with feature-flow installed, talk a small feature through, type `/feature-flow`, and follow both approvals to a written plan. Record what the brief and the plan looked like and anything that went wrong.

## Not in this ticket

- Codex (spec.md § Scope).

## Done when

- The run reaches approval 1 with a brief drawn from the conversation, then approval 2 with a plan the plan-reviewer passed or whose findings were shown.
- `python3 scripts/flow-status.py <feature> --check` prints `OK` on the accepted plan.
- The Answer lists anything the skill or guides got wrong, each fixed or filed as a ticket.

## Reference

- map.md § The bar

## Answer

Run (2026-10-07), in a cloud Claude Code session at the user's request, not in the user's own session: a scratch repo with a tiny `greet` CLI and feature-flow installed from main (704ac59, `install.py --agent claude`). The conversation was a stand-in written by Claude ("add `--shout` and `--lang es|fr`, refuse an unknown language"); both approvals were the user's own, typed in the project thread.

- `start` printed `PLAN`. Approval 1 showed the brief (Feature greet-options, What, Why, In scope, Out, The bar, Unsure); the user said yes and it was saved to `.feature-flow/state/brief-greet-options.md`.
- `plan-prompt` printed the planner role, `guides/plan.md`, the brief and the task line. A fresh `feature-planner` subagent wrote spec, map, commands, learnings and three tickets into `.feature-flow/state/draft/greet-options/`, proved them with `FLOW_DIR=.feature-flow/state/draft ... --check` and ended `PLAN: READY`. It found a real bug in the scratch repo: `python3 -m unittest` ran 0 tests (no `tests/__init__.py`), and planned the fix into ticket 01.
- `plan-review-prompt` printed the reviewer role, `guides/plan-review.md`, the brief and the draft. A fresh `plan-reviewer` subagent checked all eight points, ran the commands, and ended `PLAN-REVIEW: PASS`.
- Approval 2 showed goal, bar, commands, the graph (01; 02 after 01; 03 after 01, 02), what was dropped and two open questions; the user said yes.
- `plan-accept` printed `OK plans/greet-options`; `python3 scripts/flow-status.py greet-options --check` printed `OK: 3 tickets, 1 ready now`; after the commit, `start` printed `OK <token>`.

What went wrong:

- The planner and the plan reviewer run Python while researching, which leaves untracked `__pycache__/` folders in a repo with no `.gitignore` for them (the reviewer left two). `next` counts untracked files as dirt, so the build would stop on "working tree is not clean". Filed as ticket 09.
- Not the product: the subagents started in the session's own folder, not the scratch repo, so each prompt got one line naming the repo; and the subagent tool lists came from the role files the session loaded at start, not main's. A run in the user's own repo has neither problem.

Left open: the user decides whether this run counts or they run it again in their own Claude Code session.

