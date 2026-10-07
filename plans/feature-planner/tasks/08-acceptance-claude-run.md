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
