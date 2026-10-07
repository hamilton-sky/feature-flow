# Drive a plan end to end in a fixture, and document it

Type: task
Status: resolved
Blocked by: 04, 05, 06
Test first: yes

Add a fixture drive in `tests/py/test_fixture_drive.py` for planning, the same way the build drive works: in a repo with no plan, `start` prints `PLAN`; `plan-prompt brief.md` prints the planner prompt; the test writes a small valid draft where the planner would; `plan-review-prompt` prints the reviewer prompt; `plan-accept` prints `OK plans/f`; after a commit, `start` prints `OK <token>`. Then update the README: Quick start and "The skill and the roles" describe the brief, the two approvals, the two new roles, and that planning now runs in a fresh subagent.

## Not in this ticket

- A real agent run: ticket 08.

## Done when

- `python3 -m unittest discover -s tests/py` runs the new plan drive and it passes (the Windows CI job runs it too).
- `grep -c 'feature-planner' README.md` prints 1 or more.
- All existing tests still pass.

## Reference

- tests/py/test_fixture_drive.py, README.md

## Answer

Built: tests/py/test_fixture_drive.py PlanDrive: start prints PLAN, plan-prompt, a draft written where the planner would, plan-review-prompt with a clean tree, plan-accept prints OK plans/csv, commit, start prints OK <token>, next hands out BUILD 01. README: a Quick start row for planning from the conversation, a paragraph on the two approvals, the skill row, the two new roles, and the Codex limits.

Proof: `python3 -m unittest discover -s tests/py` 112 tests OK (the Windows job runs the same discover); `grep -c 'feature-planner' README.md` prints 2; `bash tests/run.sh` 441 passed, 0 failed.

Shortcuts taken: none.
