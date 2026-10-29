# Bring the facade under 300 lines

Type: task
Status: resolved
Blocked by: 15
Test first: no
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

The last move. `feature_flow/conductor/facade.py` (new in ticket 03) must be under 300 lines and every other package module under 400. What still sits in the facade beyond the 17 commands, the attributes in spec.md § Interfaces and forwarding goes to the module it belongs to. `start`, `reset`, `fast_switch`, `budget_cmd` and `replan_prompt` stay facade methods (the brief's Design) whose work is delegated to guards, budget or settings code.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

`Test first: no`: a pure move that the size check and the existing tests prove.

## Not in this ticket

- The ratchet test that keeps the sizes: ticket 14.
- Any new behaviour: out of scope.

## Done when

- `feature_flow/conductor/facade.py` (new in ticket 03) is under 300 lines and no other package module reaches 400 (the check below prints `over: []`).
- `facade.py` still holds `start`'s line and `check_code`'s docstring (the check below prints `facade strings True`).
- The 17 commands are still methods of `Conductor` (the check below prints `commands 17`).
- `bash tests/run.sh` passes, including `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -c "import pathlib,sys; over=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if n >= (300 if p.name == 'facade.py' else 400)]; print('over:', over); sys.exit(1 if over else 0)"
prints over: []
$ python3 -c "import sys; from feature_flow.conductor import Conductor; names='start next prompt verdict reset fast_switch scouts scout_prompt budget_cmd replan_prompt plan_prompt plan_review_prompt plan_accept plan_scouts plan_scout_prompt consult_prompt brainstorm_prompt'.split(); n=sum(callable(getattr(Conductor, k, None)) for k in names); print('commands', n); sys.exit(0 if n == 17 else 1)"
prints commands 17
$ python3 -c "import pathlib,sys; t=pathlib.Path('feature_flow/conductor/facade.py').read_bytes(); ok=b'return \"OK %s\" % token' in t and b'Stop when the files the conductor runs from changed since the ticket was picked.' in t; print('facade strings', ok); sys.exit(0 if ok else 1)"
prints facade strings True
```

## Reference

- spec.md § Interfaces (the compatibility seam), § Design
- spec.md § Interfaces (the facade: what stays and what it delegates)

## Answer

- **Built** (work starts at 7f494e5):
  - `feature_flow/conductor/facade.py`: 449 -> 296 lines. The 17 commands, `log`, `per_session`, `check_code` (same docstring and indent) and `start`'s `return "OK %s" % token` stay. `fast_switch`, `reset`, `replan_prompt`, `handoff` and `check_owner` stay as methods that delegate; `start` keeps its body after the checks; `scouts` delegates to the pending Workspace. Unused imports dropped; `owner_hash` is imported from guards so `feature_flow.conductor` still exports it.
  - `feature_flow/conductor/guards.py`: `OLD_OWNER`, `owner_hash`, `check_owner(c)`, `handoff(c)`, `before_start(c)` (start's owner, lanes and driver checks, which return `(takeover, wanted, driver)`) and `replan_prompt(c)`. Each was moved unchanged. Guards imports `planning` as a module, not `from planning import BRAINSTORM`. The reason is the import cycle planning -> phases -> build -> guards.
  - `feature_flow/conductor/budget.py`: `fast_switch(c, value)`, moved unchanged.
  - `feature_flow/conductor/reset.py` (new): `reset(c, num)`, moved unchanged.
  - `feature_flow/conductor/schedulers/serial.py`: `SerialScheduler.put_back()`, the `restore`/`batch_restore` checkouts that `next` ran on the serial path, moved unchanged.
  - `feature_flow/conductor/planning.py`: `one_scout(c, found, k, workdir, top)` is now a module function, used by the facade's `scout_prompt` and by `Planner.plan_scout_prompt`. Planner no longer takes `conductor.one_scout`.
  - `feature_flow/conductor/workspace.py`: `list_scouts()` (the body of `scouts`) and `show_head(path)` (unchanged) moved here.
  - `tests/py/test_trust_drive.py` and `tests/py/test_trust_runner.py` are unchanged, because none of the strings they read moved.
- **Proof**:
  - The size check printed `over: []` (exit 0). The largest files are facade.py 296, workspace.py 363 and lane.py 312.
  - The command check printed `commands 17` (exit 0).
  - The strings check printed `facade strings True` (exit 0).
  - `bash tests/run.sh` printed `466 passed, 0 failed` (exit 0), and `tests/py/golden/` is unchanged. Before that, test_conductor_package, test_guards, test_schedulers, test_trust_drive, test_trust_runner, test_golden, test_reset, test_scouts_drive, test_conductor, test_proof, test_levels, test_phases, test_workspace and test_no_chdir ran together: `Ran 274 tests`, `OK`. The Python 3.9 parse of every package module exits 0.
  - Acceptance: test_rebuild_bar ran 7 tests, OK. On the full acceptance set there are 13 failures. At 7f494e5 (base worktree) there were 14: the same 13 plus the ratchet, which now passes. No new failure.
- **Decisions**:
  - Owner check, handoff, start's checks and the re-plan prompt went to guards.py, the home of the checks around a ticket that already holds check_replan. `fast_switch` went to budget.py, next to the fast mode the budget turns on. This matches spec § Interfaces: start, reset, fast_switch, budget_cmd and replan_prompt delegate to guards, budget or settings code.
  - `reset` went to a new module, `reset.py`, because guards, budget and settings do not fit it: it reopens tickets, commits, drops lanes and clears the state files.
  - `driver`, `fast`, `deferred` and `num_all` stay on Conductor: tests/py/test_schedulers.py patches `Conductor.deferred`, and lane Workspaces reach these names through `__getattr__`.
  - `handoff` and `check_owner` stay as thin Conductor methods. Guards, budget and phases call `c.handoff()` and `c.check_owner()`, and a lane Workspace reaches them through `__getattr__`, bound to the Conductor as before.
- **Shortcuts taken**: none. The facade has a margin of only 4 lines under 300, so the next addition to it must move something out first.
- **For later tickets**:
  - Ticket 14 (ratchet): the facade is at 296 and workspace.py at 363.
  - Guards must import planning as a module (`from feature_flow.conductor import planning`). A `from ... import` of a name there breaks when planning is imported first.
