# Hand phases a Workspace in place of self.st, self.lane and prompts.REPO

Type: task
Status: open
Blocked by: 11
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, feature_flow/prompts.py, tests/py/test_workspace.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 9 of the design, first half. Add `feature_flow/conductor/workspace.py` (new) with `Workspace`, of one of three kinds (the main worktree, lane k, the integration worktree that `integrate` merges in): the folder a phase works in, its state view (ticket 05's `TicketState`, or the run's state outside lanes), the lane number (0 outside lanes) and the repo top. Phases, schedulers, guards and build checks receive a Workspace and read the state, the lane and the lane word from it, never from `self.st` or `self.lane` on the Conductor. `in_lane` goes: the LaneScheduler makes a lane's Workspace (with the same `lane N (...) is gone` STOP). Until ticket 15, entering a lane's Workspace may still change the working folder, in one place only.

`prompts.REPO` stops being a module global: the main worktree's top becomes an argument of the prompt functions that look up guides and roles (`find_file`, `role`, `lens`, `build`, `feature_review`, `tester`, `plan`, `replan`), with a default of `"."` so `feature_flow/codehash.py`'s `find_file(scripts, folder, name)` and every other caller still work. Guides and roles are still read from the main worktree while a lane works.

The facade keeps `self.st` only where the compatibility seam needs it (`ticket_at_base` on a bare Conductor in `tests/py/test_proof.py`).

Add `tests/py/test_workspace.py` (new): a lane's Workspace stores its keys as `L<k>.` and the run's keys plainly; the lane word; a missing lane worktree stops with the same text; prompts read guides from the top they are given, not from the lane.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- Replacing `os.chdir` with `cwd=` in git, checks and proof: tickets 13 and 15.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_workspace.py" -v` prints `OK`.
- `prompts` has no module global `REPO` and the package has no `in_lane` (the check below prints `REPO False in_lane 0`).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_prompts.py`, `tests/py/test_lanes_drive.py` and `test_golden.py`'s prompt and lane recordings unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_workspace.py" -v
prints OK
$ python3 -c "import pathlib; from feature_flow import prompts; n=sum(p.read_text(encoding='utf-8').count('def in_lane') for p in pathlib.Path('feature_flow/conductor').rglob('*.py')); print('REPO', 'REPO' in vars(prompts), 'in_lane', n)"
prints REPO False in_lane 0
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`workspace.py`, the compatibility seam), § Edge cases (guides and roles while a lane works; a lane worktree that is gone)
- the LaneScheduler and the facade: `in_lane`, `lane_word`, `scout_slot`, `ask_file`, `undo_edit`
- `feature_flow/prompts.py` (`REPO`, `find_file`), `feature_flow/codehash.py`

## Answer
