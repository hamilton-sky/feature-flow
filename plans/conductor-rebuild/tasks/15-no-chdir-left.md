# Run the conductor and proof with cwd= so nothing calls os.chdir

Type: task
Status: resolved
Blocked by: 12, 13
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, feature_flow/proof.py, tests/py/test_no_chdir.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py, tests/py/test_workspace.py (only to flip the two entered() cwd assertions)

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

- **Built**:
  - `feature_flow/proof.py`: `run_checks(checks, timeout, deferred=None, cwd=None)` runs the checks with `proc.run(..., cwd=)` in the repo top of `cwd` (else `cwd`). `repo_relative(path, cwd=None)` reads a relative path under `cwd`. `_candidates`, `_status`, `_ignored`, `_drop_ignored`, `_undo` and `_red` take `cwd=None` (keyword or last positional, so the existing calls in test_proof are unchanged). `test_first` keeps its five positional parameters; a new `_repo_of(plan_dir)` gives the top of the repo an absolute `plan_dir` is in (None for a relative one, which keeps today's behaviour). `_red` runs its pre-checkout git calls in `cwd` and the Test command, `_undo` and `_drop_ignored` in the repo top, as the old chdir did. No `os.chdir` left.
  - `feature_flow/conductor/workspace.py`: `_working_in` is gone; `entered()` only yields the Workspace; class attribute `folder = None` (a bare `Conductor.__new__`, as test_proof makes, still works); new `at(path)` puts a relative path under the folder for file reads and writes. `send_back`, `flow_edit_allowed`, `commands_at_base`, `measure_level`, `small_note`, `ticket_at_base` and `undo_edit` pass `cwd=self.folder` and read the ticket through `at()`. `flow_code()` calls `codehash.flow_code(self.scripts)` from the working folder (the main top in a lane run). `run_limit`, `gate_quick` and `write_followups` moved here from the facade (unchanged apart from `cwd=self.folder` and `at()`), so a lane or integration Workspace runs them in its own folder; `gate_quick` reads `session_done` from `self.all`, the run's count, as the facade method did in a lane.
  - `feature_flow/conductor/facade.py`: the three methods above removed (486 -> 449 lines), `checks` and `FULL_ROUNDS` imports dropped; `scout_prompt` names the lane folder by `ws.folder.resolve()`; `one_scout` gives a lane scout's role text the `python3 scripts/` rewrite (below).
  - `feature_flow/conductor/schedulers/lane.py`: `lane_next`, `lease`, `merge_in_place`, `refresh`, `rebuild` pass `cwd=ws.folder` / `lanes.git_in(ws.folder, ...)`, write the rebuild note through `ws.at()`; `make_worktree` runs Setup with `checks.smoke(..., cwd=path)`; `integrate` gates with `ws.gate_quick()` and `checks.gate(..., cwd=ws.folder)`; the Stop texts print `ws.folder.resolve()` where they printed `Path.cwd()`.
  - `buildchecks.py` (Gate, FloorGuard, Footprint, DoneWhen, TestFirst: `cwd=` the Workspace folder through `getattr(c, "folder", None)`, since test_buildchecks' `Handle` has none; TestFirst passes `plan_dir` under the folder, absolute in a lane), `guards.py` (Smoke reads commands.md through `c.at`, runs with `cwd=c.folder`), `serial.py` (`start_ticket` base from `git.head(cwd=c.folder)`), `phases/build.py`, `phases/review.py`, `phases/ask.py`, `phases/base.py` (the same `cwd=`/`at()`/`ws.folder.resolve()` changes).
  - New `tests/py/test_no_chdir.py` (5 tests): with `os.chdir` patched to raise, `cli.main` in process with `FLOW_LANES=2` starts, leases 01 and 02 into two lanes, takes `prompt <lane>` for each, builds, reviews, merges both to `DONE f is complete: 2 ticket(s)`, and checks `os.getcwd()` after every call; a removed lane folder stops with the old `lane 1 (...) is gone` text; `proof.test_first` with the absolute plan folder of a second repo finds and runs that repo's test commit and leaves the cwd, the branch and the tree as they were (a relative plan folder still reads the working folder); `run_checks(cwd=)` and `repo_relative(cwd=)`.
  - `tests/py/test_workspace.py`: only the two `entered()` assertions flipped (cwd is still the top, `folder` is the lane).
  - Test-only commit 6f20752: the discover command failed with `AssertionError: os.chdir('<repo>/.feature-flow/lanes/f/lane-1') was called` and `TypeError: run_checks() got an unexpected keyword argument 'cwd'`; test_workspace failed its two flipped assertions.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_no_chdir.py" -v`: `Ran 5 tests`, `OK`.
  - The chdir check prints `chdir 0` (exit 0).
  - The 400-line check prints `over 400: []` (exit 0); largest: workspace.py 342, lane.py 312 (facade.py 449).
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0 (test_proof, test_lanes_drive and test_golden unchanged). Before that, test_no_chdir, test_workspace, test_golden, test_lanes_drive, test_proof, test_buildchecks, test_schedulers, test_guards, test_phases, test_cwd, test_lanes, test_scouts_drive, test_conductor, test_prompts, test_batch_drive, test_reset together: `Ran 219 tests`, `OK`. The Smoke parse check (also over the package files) exits 0.
  - Acceptance `test_rebuild_lanes`: `test_a_lane_run_never_changes_the_process_working_folder` now passes (it failed at 6871fde); the other 3 failures there fail the same way at 6871fde (the twins' `code_files` difference learnings (04)/(05) describe).
- **Decisions**:
  - Lane prompts and `prompts._runner`: `prompts.py` (not in Touches) rewrites `python3 scripts/` to the running scripts folder unless it is `Path.cwd()/scripts`. The old lane prompts got the rewrite because the conductor worked in the lane; from the main top they would not, and the golden lane recordings fail. Instead of editing prompts.py, `phases/base.py` has `lane_runner(text, scripts)`, the same rewrite, applied in a lane only to what prompts rewrote before: the role and guide part of `ticket_prompt` (computed with no notes and no retry, then the notes and the debugging guide spliced back unchanged), the Ask role text, and a lane scout's role text. The golden test matches.
  - `gate_quick`, `run_limit`, `write_followups` moved to the Workspace rather than taking a folder argument: a lane Workspace reached them through `__getattr__` bound to the Conductor, so they could never see the lane's folder.
  - `flow_code()` relies on lanes running from the main top (`mode_ok("lanes_top")` at start), so codehash, which reads from the working folder, sees the main worktree's roles and guides, the same files the old chdir to the top gave it. codehash.py unchanged.
  - `make_worktree` reads Setup from the main worktree's commands.md, and `integrate` the ticket title from the integration worktree (`ws.at`), as the old code read them before and inside its chdir.
  - Trust-test strings (`"BUILD %s %s %s%s"`, `return "OK %s" % token`, `check_code`'s docstring) did not move, so test_trust_drive.py and test_trust_runner.py are unchanged.
- **Shortcuts taken**:
  - `lane_runner` copies `prompts._runner`'s regex. If prompts changes its rewrite, lane prompts drift from serial ones. Worth replacing with a `here=`/cwd parameter on `prompts.build`/`prompts.role` once a ticket may touch prompts.py.
  - `ticket_prompt` in a lane builds the prompt twice (once without notes and retry, to know which part to rewrite). Cheap (file reads), and it stops being needed with the prompts change above.
  - `flow_code()` and `prompts` still read from the working folder, which is the main top only because `start` requires it for lanes; a `next` run from a subfolder of a lane run would hash and rewrite from there. Worth a `top=` on codehash when it is next touched.
- **For later tickets**:
  - Ticket 16: the facade is now 449 lines; `gate_quick`, `run_limit` and `write_followups` already live on the Workspace. Anything run in a lane must take `cwd=ws.folder` and read relative paths through `ws.at()`; `buildchecks` uses `getattr(c, "folder", None)` because test_buildchecks' `Handle` has no folder.
  - Ticket 14 (ratchet): `entered()` is now only a context that yields the Workspace; keep it or drop it, callers do not depend on a folder change.

## Attempt note

Stopped before any code or test was written (work starts at 74f762d). The ticket cannot pass inside its `Touches:` line.

- **What fails:** `tests/py/test_workspace.py` (ticket 12's test, not in this ticket's Touches) asserts that `Workspace.entered()` changes the working folder. Line 88 (`test_entering_a_lane_works_in_its_folder_and_comes_back_to_the_top`): `self.assertEqual(Path.cwd().resolve(), path.resolve())` inside `with ws.entered()`. Line 170 (`CodeFingerprint.test_a_lane_snapshot_names_the_main_worktrees_role`): `self.assertEqual(Path.cwd().resolve(), self.lane.resolve())` inside `with self.ws.entered()`. Once `entered()` stops calling `os.chdir`, which is this ticket's whole point, both fail, and `bash tests/run.sh` (Done when 4) cannot pass. Changing them is outside Touches, and the footprint check sends the build back.
- **What is needed (a human decides):** widen this ticket's Touches with `tests/py/test_workspace.py`, so those two assertions can say the reverse: the working folder is unchanged inside `entered()` and `ws.folder` is the lane. Or add a ticket for that test change and block this one on it. I found no other existing test that depends on the chdir. The acceptance test `acceptance/test_rebuild_lanes.py` already expects no chdir.
- **What I found, for the next attempt:**
  - The chdirs are in `workspace.py` `_working_in` (used by `entered()` and `flow_code()`) and in `proof.py` `run_checks` and `_red`. Lanes require cwd == top (`mode_ok("lanes_top")` in `start`), so in a lane `flow_code()` can call `codehash.flow_code(self.scripts)` without the chdir. `codehash.py` does not have to change.
  - Methods the Workspace takes from the Conductor through `__getattr__` run with `self` set to the Conductor, so `self.folder` is None there. These are reached from a lane or integration ws: `run_limit` (from `start_ticket`), `gate_quick` (from `buildchecks.Gate`, `integrate`, `refresh`) and `write_followups` (from `write_due` and `pass_with_followups`). They need the folder passed in or must move to the Workspace.
  - Paths that today resolve against the lane through the chdir: `ws.ticket()` (`tickets.*`, `Path(...).read_text` in `Ask.open_ask`, `ticket_at_base`), `c.commands` (`tickets.commands_value` for Setup, Test and Smoke), `c.plan` (followups.md, `lanes.resolve_appends`). Also `lanes.git_in(".")` and `lanes.unmerged(".")` in lane.py, `proof.repo_relative` (it uses `Path.cwd()`), and `Path.cwd()` as the lane folder in `phases/base.py` `ticket_prompt`, `ask.py` (`ask_user`, `prompt`) and `facade.scout_prompt`, and in lane.py's Stop texts. Use `ws.folder.resolve()` there to keep the printed real path.
  - A lane folder that is gone: every lane path goes through `LaneScheduler.workspace(k)`, which raises the `lane %d (%s) is gone` STOP before any helper runs. The integration worktree goes through `make_worktree` (`lanes.ensure`) first. So passing `cwd=ws.folder` cannot get to `Popen` with a missing folder or to the gate's "nothing to run" on those paths. A test in test_no_chdir.py should still prove it (remove lane 1's folder, then `next 1` must STOP with that text).
