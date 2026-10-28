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

- **Built**:
  - New `feature_flow/conductor/workspace.py` (299 lines): `Workspace(c, kind=MAIN, lane=0, folder=None)` with the kinds `MAIN`, `LANE`, `INTEGRATION`. It holds `kind`, `lane` (0 outside lanes), `top` (the main worktree's top), `folder` (None: the working folder), `st` (`TicketState(c.all, lane)`: a lane's keys as `L<k>.`, the run's plain) and `prompts_top` (`"."` in the main worktree, as `prompts.REPO` was; the main top in a lane). `entered()` is the one `os.chdir` left in the package (into `folder`, back to `top`). `__getattr__` takes what a lane's Workspace does not hold (settings, paths, `all`, `scheduler()`, `handoff`, `write_followups`, ...) from the Conductor. The per-ticket steps that read the state moved here from the facade unchanged: `get`, `num`, `save`, `log`, `emit`, `ticket`, `ticket_name`, `lane_word`, `scout_slot`, `count_run`, `pending`, `prompt_text`, `phase_key`, `scout_questions`, `scout_findings`, `round_cap`, `send_back`, `add_due`, `write_due`, `pass_ticket`, `pass_with_followups`, `defer_review`, `snapshot_code`, `flow_edit_allowed`, `base_level`, `commands_at_base`, `measure_level`, `small_note`, `ticket_at_base`, `undo_edit`, `edit_retry`. `Workspace.check_code` calls `type(self.c).check_code(self, ...)`, so `check_code` stays a `Conductor` method in `facade.py` with its docstring, and a patch of `Conductor.check_code` covers lanes too.
  - `facade.py` (731 -> 486 lines): `class Conductor(Workspace)`; `__init__` and `reset` call `Workspace.__init__(self, self)` in place of `self.st = TicketState(self.all)`; `in_lane`, `lane_word`, `self.lane` and the moved methods are gone. The facade's own run writes (`start`, `next`, `handoff`, `check_owner`) write `self.all` (the main view has no prefix, so the keys are the same). `prompt`, `scouts`, `scout_prompt` and `verdict` work on the Workspace that `pending_phase` (now yields one) or `lane_sched().workspace(k).entered()` gives; `one_scout` takes `top`. `start`'s `return "OK %s" % token` and `check_code` are untouched, so `tests/py/test_trust_drive.py` and `tests/py/test_trust_runner.py` were not changed.
  - `schedulers/lane.py`: new `workspace(k)` makes lane k's Workspace with the old `lane %d (%s) is gone. run reset to drop the lanes and start again` STOP; `lane_next`, `lease`, `refresh`, `rebuild` work in `with self.workspace(k).entered() as ws` on `ws`; `integrate` works in an `INTEGRATION` Workspace; `make_worktree(ws, name)` runs Setup through `ws.entered()`; `merge_in_place(ws, ...)` logs on the ws it merges in (lane or integration, as before). `import os` dropped.
  - `schedulers/serial.py`: `start_ticket(path, ws=None)` (the main worktree when None) so a lane's lease and rebuild start the ticket in the lane's Workspace.
  - `prompts.py`: `REPO` is gone; `find_file`, `lens`, `role`, `build`, `feature_review`, `tester`, `plan`, `replan` take `top="."` (last, so `codehash.find_file(scripts, folder, name)` and every positional caller still work). Phases pass `ws.prompts_top` (`phases/base.py` `ticket_prompt`, `build.py` batch prompt, `ask.py`, `test.py`, `final.py`); `phases/base.py` docstring says what `ws` is now.
  - New `tests/py/test_workspace.py` (13 tests): the Conductor is the main Workspace; lane keys stored as `L<k>.`, run keys plain, the run's keys plain; the lane word (lane and integration); a lane reads settings, `all` and the scheduler from the Conductor, and an unknown name is an AttributeError; a missing lane worktree stops with the exact old text; entering a lane changes to its folder and back to the top; a lane's Ask prompt reads the role from the main worktree's `.feature-flow/`, not the lane's copy; `find_file`/`build`/`role` read from the `top` given, the three-argument `find_file` reads from the working folder; `prompts` has no `REPO`.
  - Test-only commit 39d49ad: the discover command failed with `ModuleNotFoundError: No module named 'feature_flow.conductor.workspace'`.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_workspace.py" -v`: `Ran 13 tests`, `OK`.
  - The REPO/in_lane check prints `REPO False in_lane 0`.
  - The 400-line check prints `over 400: []` (exit 0); the largest are `schedulers/lane.py` 313 and `workspace.py` 299.
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0. Before it, ran test_workspace, test_schedulers, test_guards, test_phases, test_prompts, test_proof, test_buildchecks, test_lanes_drive, test_golden, test_conductor_package, test_lanes, test_scouts_drive, test_conductor, test_reset, test_batch_drive together: `Ran 211 tests`, `OK`. No existing test and no golden recording changed.
- **Decisions**:
  - The Conductor is the main worktree's Workspace (a subclass) rather than holding one. Existing tests, which may not change, use the Conductor as the `ws`: `test_schedulers` calls `sched.on_passed(run.c)`, sets `run.c.st = TicketState(run.c.all, 1)` and reads `run.c.pending()`; `test_guards`/`test_schedulers` write `run.c.st[...]`; `test_proof` sets `c.st` on a bare `Conductor.__new__` and calls `ticket_at_base`. As a subclass, all of these keep working with no forwarding code in the facade. So the facade has no `self.st` of its own: `st` is the Workspace attribute, which the seam sets directly.
  - Lane and integration Workspaces are separate objects that get the run-wide things from the Conductor through `__getattr__`. This way phases, guards and build checks keep calling `ws.<setting>` as before, and nothing is copied that could go stale.
  - `prompts_top` is `"."` in the main worktree, not the top. That is exactly what `prompts.REPO` was outside lanes, so a serial run from a subfolder finds its guides as before.
  - `ticket_prompt`, `Ask` and `scout_prompt` still name the lane folder through `Path.cwd()`, not `ws.folder`. `Path.cwd()` is the resolved real path the old prompts printed; the swap belongs with ticket 15's `cwd=` work.
  - The batch, serial and end-of-run code still writes `c.st`: there `c` is the Conductor, i.e. the main worktree's Workspace, which is the view they always used (batches never run in lanes).
- **Shortcuts taken**: `Workspace.__getattr__` forwards any missing name to the Conductor. A typo on a lane Workspace therefore resolves on the Conductor (and its main state view) instead of failing. This stops working only if a per-ticket method is added to the Conductor instead of the Workspace: in a lane it would then read the main view. It is worth an explicit list of forwarded names once the facade is trimmed (ticket 16) and the set is small.
- **For later tickets**:
  - Ticket 15: the only `os.chdir` left in the package is `Workspace.entered()` (workspace.py). `ws.folder` is the lane or integration folder (None in the main worktree), so it is the natural `cwd=`. `ticket_prompt`, `Ask.prompt`/`ask_user` and `scout_prompt` still read `Path.cwd()` for the lane folder.
  - Ticket 16: the facade is 486 lines. The per-ticket methods are in `workspace.py` already. A per-ticket method added later must go on `Workspace`, not `Conductor`, or lanes would see the main view (see Shortcuts).

## Review findings (round 1, single review)

SPEC
- test_workspace.py OK: MET (conductor)
- prompts has no REPO, package has no in_lane: MET (conductor)
- no module but facade.py reaches 400 lines: MET (conductor)
- bash tests/run.sh passes: MET (466 passed, 0 failed)
- scope: OK
- test first: OK

QUALITY
1. blocker feature_flow/conductor/workspace.py and facade.py (snapshot_code / check_code), via feature_flow/codehash.py: before this change in_lane set prompts.REPO to the main top, so codehash._files() (find_file with no top) hashed the main worktree's .feature-flow/agents and guides during a lane build. With REPO gone, codehash uses "." and inside ws.entered() that is the lane folder, so in a repo install the flow-code fingerprint covers the lane's copies while the prompts still read the main worktree's copies (ws.prompts_top). A lane builder can then edit <top>/.feature-flow/agents/ticket-reviewer.md or a review guide and check_code no longer notices. Fix: make the fingerprint read the main worktree's role and guide files again. codehash.py is NOT in this ticket's Touches, so do it inside feature_flow/conductor/: e.g. run codehash.flow_code / changed from the main top (the Conductor's own workspace entered(), or pass the main top through a conductor-side wrapper) in Workspace.snapshot_code and Conductor.check_code. Add a test_workspace case: a lane workspace's snapshot names the main worktree's role files, and editing the main worktree's role during a lane build makes check_code stop.
2. minor feature_flow/conductor/workspace.py Workspace.__getattr__: forwards every missing name to the Conductor, so a Conductor method reading self.get/self.st silently uses the main view in a lane. Consider an allow-list of forwarded names.
3. minor tests/py/test_schedulers.py:304 comment still says "as in_lane gives it" (not in this diff, leave for later).

REVIEW: FAIL
