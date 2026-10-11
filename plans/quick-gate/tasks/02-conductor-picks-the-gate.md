# Have the conductor pick the quick or the full gate for each ticket

Type: task
Floor: allow flow-edit
Status: resolved
Blocked by: 01
Test first: yes

In `feature_flow/conductor.py`, add `Conductor.gate_quick()`, true when all of these hold: `FLOW_GATE_FULL` is not `1`; `commands.md` has a usable `Quick:` value (use `tickets.commands_value(self.commands, "Quick")` and treat a value starting with `<` as none, as `smoke_command` does); this ticket is not the last one: `judge_build` reaches the gate only after the current ticket is already `resolved`, so read `checks.flow_status(self.scripts, self.feature, "--counts")` (read how `run_limit` parses its `key=value` words) and call the ticket the last when `open + claimed + waiting + unknown` is 0 (a `waiting` or blocked ticket still counts as unfinished, so the gate stays quick); and this ticket does not fill the session (`self.per_session > 0` and `self.num("session_done") + 1 >= self.per_session`). In `judge_build`, call `checks.gate(..., quick=self.gate_quick())` and log `GATE-QUICK` or `GATE-FULL` before the existing `GATE-PASS` or `GATE-FAIL`. The send-back text for a failed gate must say which mode ran (`gate (quick)` or `gate (full)` in the findings header source is enough). `FLOW_GATE=off` still skips the gate.

Tests in a new `tests/py/test_quick_gate.py` using `helpers.Repo` with a three-ticket plan (the `commands.md` there has only Build and Smoke placeholders, so write your own with Test and Quick commands that append `test` or `quick` to a log file): the first fixture ticket runs only Quick; the last fixture ticket runs Test; with `FLOW_TICKETS_PER_SESSION=2` the second fixture ticket runs Test because the run hands off after it; `FLOW_GATE_FULL=1` runs Test for every ticket; a plan with no `Quick:` runs Test every time; `FLOW_GATE=off` runs neither; the log carries `GATE-QUICK` and `GATE-FULL` to match; a Quick that fails sends the ticket back.

## Not in this ticket

- Guides, template, README, version: tickets 03 and 04.
- The end-to-end drive: ticket 05.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_quick_gate.py" -v` prints `OK` and lists tests with `last` and `handoff` in their names.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_quick_gate.py" -v
prints last
prints handoff
prints OK
```

## Reference

- spec.md § Happy path, § Edge cases, § Design
- `feature_flow/conductor.py` (`judge_build`, `smoke_command`, `run_limit`, `pick_ticket`), `feature_flow/checks.py`

## Answer

**Built**: `feature_flow/conductor.py` (`Conductor.gate_quick()`; `judge_build` passes `quick=` to `checks.gate`, logs `GATE-QUICK` or `GATE-FULL` before `GATE-PASS`/`GATE-FAIL`, and sends back with source `gate (quick)` or `gate (full)`); new `tests/py/test_quick_gate.py` (7 tests). Test-only commit came first and failed 4 of 7 for the right reason (Test ran, not Quick).

**Proof**: `python3 -m unittest discover -s tests/py -p "test_quick_gate.py" -v` ran 7 tests, listed `test_middle_quick_and_last_ticket_runs_test` and `test_handoff_ticket_runs_test`, printed OK. `test_conductor.py` also still passes. The full suite is left to the conductor's gate.

**Decisions**: `gate_quick` reads `--counts` and sums `open+claimed+waiting+unknown`; quick only when above 0. A Quick that is a `<...>` placeholder counts as none (`commands_value` already returns "" for it). Tests keep logger script and log file outside the repo so the tree stays clean; commands are double-quoted python calls, no skips.

**Shortcuts taken**: none.

**For later tickets**: the findings header for a failed gate is now `gate (quick)` or `gate (full)`; any text or test that matches `(round N, gate)` exactly would need to allow that.
