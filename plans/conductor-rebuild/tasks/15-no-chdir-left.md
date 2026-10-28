# Run the conductor and proof with cwd= so nothing calls os.chdir

Type: task
Status: open
Blocked by: 12, 13
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, feature_flow/proof.py, tests/py/test_no_chdir.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 9 of the design, the last part. The Workspace (ticket 12) passes its folder as `cwd=` to every helper ticket 13 gave the keyword (git calls, `checks.gate`, `checks.floor_guard`, `checks.flow_status`, `checks.smoke`, `proc.run`), resolves relative ticket and plan paths against its folder for file reads and writes, and no longer changes the working folder. The same holds for `make_worktree`'s Setup run and `integrate`'s merge and gate in the integration worktree. Lines printed keep the relative paths they print now.

`proof.py` (spec.md § Decisions, How `proof.test_first` learns the folder):

- `test_first(base, test_command, plan_dir, timeout, remember)` keeps its five positional parameters, and the conductor calls it with five positional arguments: `tests/py/test_proof.py` patches it with `lambda b, c, d, t, r: ...`. The Workspace passes `plan_dir` as an absolute path inside its folder; `proof` finds the repo top from it (`git.toplevel(cwd=...)`) and runs `_candidates`, `_red`, `_status`, `_undo` and `_drop_ignored` there with `cwd=`. A relative `plan_dir` keeps today's behaviour.
- `run_checks(checks, timeout, deferred=None, cwd=None)` runs the check commands in `cwd`, else the repo top as now, without `os.chdir`.

If a helper module this ticket does not list must change for a lane to work, stop and say so in the Answer: the plan changes, not the footprint.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

Add `tests/py/test_no_chdir.py` (new): with `os.chdir` patched to raise, an in-process `Conductor` on a throwaway repo with `FLOW_LANES=2` leases two tickets, builds, reviews and merges them to `DONE`, and `os.getcwd()` is the same after every command; `proof.test_first` given an absolute `plan_dir` of a second repo checks that repo's commits and leaves `os.getcwd()` unchanged.

## Not in this ticket

- The helpers' `cwd=` keyword itself: ticket 13.
- Bringing the facade under 300 lines: ticket 16.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_no_chdir.py" -v` prints `OK`.
- No file under `feature_flow/` calls `os.chdir` (the check below prints `chdir 0`).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_proof.py`, `tests/py/test_lanes_drive.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_no_chdir.py" -v
prints OK
$ python3 -c "import pathlib,sys; n=sum(p.read_text(encoding='utf-8').count('os.chdir(') for p in pathlib.Path('feature_flow').rglob('*.py')); print('chdir', n); sys.exit(1 if n else 0)"
prints chdir 0
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Decisions (cwd instead of chdir; how `proof.test_first` learns the folder), § Edge cases (code that runs in a lane after the switch; `proof.test_first` patched with a lambda)
- `feature_flow/conductor/workspace.py` (new in ticket 12), the LaneScheduler (`make_worktree`, `integrate`)
- `feature_flow/proof.py` (`run_checks`, `test_first`, `_candidates`, `_red`, `repo_relative`), `tests/py/test_proof.py`

## Answer

## Attempt note

Stopped before any code or test was written (work starts at 74f762d). The ticket cannot pass inside its `Touches:` line.

- **What fails:** `tests/py/test_workspace.py` (ticket 12's test, not in this ticket's Touches) asserts that `Workspace.entered()` changes the working folder. Line 88 (`test_entering_a_lane_works_in_its_folder_and_comes_back_to_the_top`): `self.assertEqual(Path.cwd().resolve(), path.resolve())` inside `with ws.entered()`. Line 170 (`CodeFingerprint.test_a_lane_snapshot_names_the_main_worktrees_role`): `self.assertEqual(Path.cwd().resolve(), self.lane.resolve())` inside `with self.ws.entered()`. Once `entered()` stops calling `os.chdir`, which is this ticket's whole point, both fail, and `bash tests/run.sh` (Done when 4) cannot pass. Changing them is outside Touches, and the footprint check sends the build back.
- **What is needed (a human decides):** widen this ticket's Touches with `tests/py/test_workspace.py`, so those two assertions can say the reverse: the working folder is unchanged inside `entered()` and `ws.folder` is the lane. Or add a ticket for that test change and block this one on it. I found no other existing test that depends on the chdir. The acceptance test `acceptance/test_rebuild_lanes.py` already expects no chdir.
- **What I found, for the next attempt:**
  - The chdirs are in `workspace.py` `_working_in` (used by `entered()` and `flow_code()`) and in `proof.py` `run_checks` and `_red`. Lanes require cwd == top (`mode_ok("lanes_top")` in `start`), so in a lane `flow_code()` can call `codehash.flow_code(self.scripts)` without the chdir. `codehash.py` does not have to change.
  - Methods the Workspace takes from the Conductor through `__getattr__` run with `self` set to the Conductor, so `self.folder` is None there. These are reached from a lane or integration ws: `run_limit` (from `start_ticket`), `gate_quick` (from `buildchecks.Gate`, `integrate`, `refresh`) and `write_followups` (from `write_due` and `pass_with_followups`). They need the folder passed in or must move to the Workspace.
  - Paths that today resolve against the lane through the chdir: `ws.ticket()` (`tickets.*`, `Path(...).read_text` in `Ask.open_ask`, `ticket_at_base`), `c.commands` (`tickets.commands_value` for Setup, Test and Smoke), `c.plan` (followups.md, `lanes.resolve_appends`). Also `lanes.git_in(".")` and `lanes.unmerged(".")` in lane.py, `proof.repo_relative` (it uses `Path.cwd()`), and `Path.cwd()` as the lane folder in `phases/base.py` `ticket_prompt`, `ask.py` (`ask_user`, `prompt`) and `facade.scout_prompt`, and in lane.py's Stop texts. Use `ws.folder.resolve()` there to keep the printed real path.
  - A lane folder that is gone: every lane path goes through `LaneScheduler.workspace(k)`, which raises the `lane %d (%s) is gone` STOP before any helper runs. The integration worktree goes through `make_worktree` (`lanes.ensure`) first. So passing `cwd=ws.folder` cannot get to `Popen` with a missing folder or to the gate's "nothing to run" on those paths. A test in test_no_chdir.py should still prove it (remove lane 1's folder, then `next 1` must STOP with that text).
