# Add the serial and batch schedulers and one shared end of run

Type: task
Status: resolved
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

- **Built**:
  - New `feature_flow/conductor/schedulers/end.py` (136 lines): `EndOfRun(c, scheduler, lanes=False)`. It holds `acceptance_command`, `acceptance_folder`, `tests_due`, `tester()` (the TEST line when tests are due, else None), `run_acceptance`, `check_acceptance` (it ends with `self.scheduler.resume()`), `acceptance_ticket` and `finish()`: the acceptance run, then the feature review for deferred tickets, then `DONE`. The `lanes` flag keeps the spec's differences. A serial `DONE` clears `phase` and `owner` in the ticket view. A lane `DONE` removes the lane worktrees and clears only the run's `owner`. Where tests due are checked stays with the caller: serial `pick_ticket` checks before `--next`, and `dispatch` checks only with no busy lane.
  - New `schedulers/serial.py` (74 lines): `SerialScheduler(c)` with `next(lane)` (= `pick_ticket`), `on_passed(ws)` (sets phase "", counts done and session_done, saves, resumes), `resume()` (= `next(None)`), `pick_ticket`, `begin(first)` (starts the ticket and hands out its build) and `start_ticket`.
  - New `schedulers/batch.py` (162 lines): `BatchScheduler(SerialScheduler)`. `begin` adds the batch through `batch_for`. It also holds `batch_note()`, `ticket_ends` and `judge_batch`, which still runs `buildchecks.pipeline(c, gate=False)` and `mode_ok("batch", ...)`, and ends with `self.resume()`.
  - New `schedulers/facade_lanes.py` (20 lines): `FacadeLanes(SerialScheduler)`, a stand-in until ticket 10. `next` is `c.lane_next`, `resume` is `c.dispatch`, and `on_passed` sets phase `merge`, saves and returns None, as `pass_ticket` did in a lane. `lanes = True` gives it the lane end of run.
  - `schedulers/__init__.py` exports `BatchScheduler`, `EndOfRun`, `FacadeLanes` and `SerialScheduler`. Phases never import schedulers: they reach them through `ws.scheduler()`, so there is no import cycle.
  - `facade.py` (1408 to 1123 lines): `acceptance_*`, `tests_due`, `run_acceptance`, `check_acceptance`, `pick_ticket`, `batch_for`, `ticket_ends`, `judge_batch`, `start_ticket` and `finish` are gone. New `scheduler()` picks once per call, cached in `self.sched`: `FacadeLanes` when the run's `lanes` > 1, else `BatchScheduler`. These callers changed: `pass_ticket` calls `scheduler().on_passed(self)`, `next` ends with `scheduler().next(lane)`, `dispatch` uses `scheduler().end.tests_due()` and `scheduler().end.finish()`, and `lease` and `rebuild` call `scheduler().start_ticket(path)`. The now-unused `buildchecks` and `Final` imports were dropped. `start` (`return "OK %s" % token`) and `check_code` (same docstring, same indent) are untouched.
  - `phases/test.py`, `phases/final.py`: the three `dispatch() if ... else pick_ticket()` became `ws.scheduler().resume()`. The tester reads its acceptance helpers from `ws.scheduler().end`. `phases/build.py`: `Build.batch_note` moved to `BatchScheduler.batch_note`, and the batch judge is `ws.scheduler().judge_batch()`. The `"BUILD %s %s %s%s"` line stays in phases/build.py, so no trust test changed.
  - New `tests/py/test_schedulers.py` (8 tests, in process on helpers.Repo):
    - serial hands out the lowest ready ticket (02 when 01 is blocked);
    - serial finishes through `EndOfRun.finish`;
    - `on_passed` counts the ticket and hands out the next;
    - the facade picks its scheduler once;
    - a 14-row `batch_for` table: level, Touches, overlap, Sensitive (first ticket and later ones), `no_batch` (first and later), the session room left (2 and 1), FLOW_BATCH, fast off, gate off;
    - EndOfRun's order (tester, acceptance, feature review, DONE), checked by the call sequence;
    - a serial DONE versus a lane DONE (what each clears, and whether the lanes are removed).
  - Test-only commit 561b38c: the discover command failed with `ImportError: cannot import name 'BatchScheduler' from 'feature_flow.conductor.schedulers'`.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_schedulers.py" -v`: `Ran 8 tests`, `OK`.
  - The copies check printed `copies 0` (exit 0).
  - The 400-line check printed `over 400: []` (exit 0). The largest scheduler module is batch.py with 162 lines.
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0.
  - I also ran test_golden, test_ask_drive, test_tester_drive, test_scouts_drive, test_proof, test_trust_drive, test_trust_runner, test_conductor_package, test_lanes_drive, test_fast_drive, test_batch_drive, test_review_pass, test_levels_drive, test_conductor, test_phases, test_schedulers, test_budget_drive and test_reset together: `Ran 273 tests`, `OK`. The first run of that set had 1 error, a `git commit -qm 'feat: 01'` exit 128 inside a test fixture. The identical rerun passed, and so did run.sh.
  - Acceptance: 16 failures, the same list as at 0d5f1d0 (diffed). `test_serial_batch_and_lane_runs_are_scheduler_classes_with_one_end_of_run` still fails, only because `LaneScheduler` is ticket 10's.
- **Decisions**:
  - Schedulers are instances bound to the conductor, because `resume()` takes no arguments in the protocol. `on_passed(ws)` and the per-ticket code take the conductor as ws until ticket 12.
  - A non-lane run always gets `BatchScheduler`, a `SerialScheduler` whose `begin` may add a batch. The batch is decided per ticket, as before: `check_budget` can switch fast mode on in the same call, just before `batch_for`, and a pending batch must be judged whatever the env says now. With the batch rule unmet, `batch_for` returns [] and the run is plain serial.
  - `on_passed` is called from `pass_ticket`, after `write_due` and `note_slowest`. Every phase Outcome with `passed=True` comes from a `pass_ticket` chain, so it runs exactly when an Outcome passes, with the same order of effects. The old `if self.lane` branch became the scheduler choice: lanes > 1 holds exactly when a lane is being judged.
  - Lanes needed a scheduler for `resume()` before ticket 10. That is `FacadeLanes`, which forwards to the facade's own lane code. It is deliberately not named `LaneScheduler`, which is ticket 10's.
- **Shortcuts taken**: `FacadeLanes` is a stand-in that forwards to `lane_next` and `dispatch` on the facade. It stops being right once ticket 10 moves the lane code, and ticket 10 should replace it with `LaneScheduler`.
- **For later tickets**:
  - Ticket 10: replace `FacadeLanes` (schedulers/facade_lanes.py, the `scheduler()` pick in facade.py and the export in schedulers/__init__.py) with `LaneScheduler`. `dispatch` must keep calling `end.tests_due()` only with no busy lane, then `end.finish()`. `EndOfRun(..., lanes=True)` already holds the lane DONE. Lane `start_ticket` is inherited from `SerialScheduler`.
  - Ticket 12: phases now reach `ws.scheduler()` (`resume`, `judge_batch`, `batch_note`, and `end.acceptance_folder/run_acceptance/acceptance_command`) in place of the facade methods listed in 08's Answer.
