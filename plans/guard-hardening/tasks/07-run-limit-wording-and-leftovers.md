# Recompute the run limit, say phases, drop the unused bash helper

Type: task
Status: open
Blocked by: 06
Test first: yes
Floor: allow flow-edit, skip, suppress

In `feature_flow/conductor.py`: recompute `limit` in `pick_ticket` from the current ticket count (`run_limit()`), not once on the first `next`, so a feature that gains tickets is not stopped by a stale limit; keep `runs` and `done`. Reword the message to `run limit of %d phases reached, stopping` (a phase is one BUILD or REVIEW hand-out). In `feature_flow/checks.py` delete the unused `_bash()` and the docstring about the bash scripts it still calls.

## Not in this ticket

- Changing what counts as a run.
- README wording: ticket 09.

## Done when

- A conductor test: a plan that gains a ticket after the first `next` gets the larger limit on the next `pick_ticket` (read it from the state file).
- `python3 scripts/flow.py f next` at the limit prints a STOP containing `phases`, and `grep -rn "sessions reached" feature_flow` prints nothing.
- `grep -n "_bash" feature_flow/checks.py` prints nothing.
- All existing tests still pass.

## Reference

- spec.md § Design (Goal 4)
- feature_flow/conductor.py (`run_limit`, `count_run`, `next`, `pick_ticket`), feature_flow/checks.py, tests/py/test_conductor.py

## Answer

