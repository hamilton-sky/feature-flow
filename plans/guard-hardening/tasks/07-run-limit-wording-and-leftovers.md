# Recompute the run limit, say phases, drop the unused bash helper

Type: task
Status: resolved
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


**Built**: `feature_flow/conductor.py` (`pick_ticket` sets `limit = run_limit()` after a ticket is chosen; message now `run limit of %d phases reached, stopping`), `feature_flow/checks.py` (deleted `_bash`, the now unused `import subprocess`, and the "bash scripts it still calls" docstring words), `tests/py/test_conductor.py` (class `RunLimit`), `tests/run.sh` (the one expected string `65 sessions` became `65 phases`).

**Proof**:
- `python3 -m unittest discover -s tests/py -k RunLimit` failed before the change (`STOP run limit of 2 sessions reached`) and the full suite now prints `Ran 166 tests ... OK`. The test sets the state file's `limit=2` after the first `next`, then picks ticket 02 and reads the state file: limit is back to the computed value.
- tests/run.sh check `and stops` expects `STOP run limit of 65 phases reached, stopping` from `flow.py f next` at the limit: `441 passed, 0 failed`. `grep -rn "sessions reached" feature_flow` prints only a stale `.pyc` match, no source line.
- `grep -n "_bash" feature_flow/checks.py` prints nothing.
- Full `python3 -m unittest discover -s tests/py` OK and `bash tests/run.sh` rc=0, 441 passed.

**Decisions**: the test simulates the stale limit by editing the state file rather than adding a ticket, because a ticket added after the base is flagged by the floor guard, and one committed during review stops the run as a reviewer change. Kept the first-`next` init of `limit` in `next()` so `count_run` always has a value.

**Shortcuts taken**: none.

**For later tickets**: ticket 08 (repo's committed copies under `.feature-flow/`) still has the old `sessions reached` text in `.feature-flow/feature_flow/conductor.py`; refreshing it is that ticket's job. tests/run.sh was edited for the wording only.
