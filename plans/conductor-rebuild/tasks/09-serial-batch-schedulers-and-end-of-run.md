# Add the serial and batch schedulers and one shared end of run

Type: task
Status: open
Blocked by: 08
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_schedulers.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 7 of the design, without lanes. In `feature_flow/conductor/schedulers/` (made in ticket 03):

- `SerialScheduler`: `pick_ticket` and `start_ticket`.
- `BatchScheduler`: `batch_for`, `batch_note`, `ticket_ends`, `judge_batch` (on ticket 07's pipeline without the gate, and ticket 04's batch rule).
- `EndOfRun`: what happens when no ticket is ready, shared by every scheduler: acceptance tests due (`tests_due`, handing out the tester), the acceptance run (`check_acceptance`, `run_acceptance`, `acceptance_ticket`, `acceptance_command`, `acceptance_folder`), the feature review for deferred tickets, and the `DONE` line. Keep the differences spec.md § Edge cases lists: where serial and lane runs check tests due, and what each clears at `DONE`.

The facade picks the scheduler once per call (serial for now; ticket 10 adds lanes) and every place that wrote `self.dispatch() if self.num("lanes") > 1 else self.pick_ticket()` (in `judge_final` twice, `judge_test`, `check_acceptance`) calls the scheduler's `resume()` instead. The schedulers follow the scheduler protocol of spec.md § Interfaces: `next(lane)`, `on_passed(ws)` (called when a phase's `Outcome` has `passed`), `resume()`.

Add `tests/py/test_schedulers.py` (new): the serial scheduler hands out the lowest ready ticket and finishes through `EndOfRun`; `batch_for`'s choices for a table of ready tickets (level, `Touches:`, `Sensitive:`, `no_batch`, the session room left); `EndOfRun`'s order (tester first, then acceptance, then feature review, then `DONE`).

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- `LaneScheduler`, `dispatch`, `lease`, `integrate`, `refresh`, `rebuild` and the merge phase: ticket 10.
- The guards before a ticket (handoff, re-plan, budget, smoke): ticket 11.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_schedulers.py" -v` prints `OK`.
- No package file writes `dispatch() if` any more (the check below prints `copies 0`).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_fast_drive.py`, `tests/py/test_batch_drive.py`, `tests/py/test_tester_drive.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_schedulers.py" -v
prints OK
$ python3 -c "import pathlib,sys; n=sum(p.read_text(encoding='utf-8').count('dispatch() if') for p in pathlib.Path('feature_flow/conductor').rglob('*.py')); print('copies', n); sys.exit(1 if n else 0)"
prints copies 0
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`schedulers/`), § Edge cases (`pick_ticket` and `dispatch` at the end), § Happy path
- the facade: `pick_ticket`, `start_ticket`, `batch_for`, `judge_batch`, `tests_due`, `check_acceptance`, `finish`, `judge_final`, `judge_test`

## Answer
