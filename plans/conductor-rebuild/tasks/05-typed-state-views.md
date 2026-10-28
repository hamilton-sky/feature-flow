# Add RunState and TicketState views over the state file

Type: task
Status: resolved
Blocked by: 04
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, feature_flow/lanes.py, tests/py/test_store.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 3 of the design. Add `feature_flow/conductor/store.py` (new) with `RunState` (the whole run state: the dict `state.load` returns, `save`, `num`, `get`) and `TicketState` (one ticket's view: the run's keys pass through, a lane's keys are stored as `L<k>.<key>`, exactly as `lanes.Scoped` does). Both work on the same dict and the same `key=value` file through `feature_flow/state.py`, which does not change. `num` raises the same `Stop` (`the state file ... is damaged: <key> is not a number`). `store.py` takes over `RUN_KEYS` and `Scoped` from `feature_flow/lanes.py`; `lanes.py` re-exports both under their old names, so `tests/py/test_lanes.py` and every other caller keep working. `store.py` must not import `lanes`. Mind the cycle: `lanes` importing `feature_flow.conductor.store` loads `feature_flow/conductor/__init__.py` and the facade first, which import `lanes` back, so package modules import it as a module (`from feature_flow import lanes`), never names from it.

The facade's `self.st` and `self.all` become these views (`get`, `num`, `num_all`, `save` go through them). `self.st` must still accept a plain dict, because `tests/py/test_proof.py` sets `c.st = {...}` on a bare `Conductor` and calls `ticket_at_base()`.

Add `tests/py/test_store.py` (new): a state file written in the old format is read and written back byte for byte; lane keys go to `L<k>.`, run keys do not; `clear` drops only the lane's keys; a damaged number stops with the same text; `lanes.Scoped` and `lanes.RUN_KEYS` are the store's.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- Passing the views to phases through a Workspace: ticket 12.
- Changing any key or the file format: never, out of scope.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_store.py" -v` prints `OK`.
- `feature_flow.lanes.RUN_KEYS` is the store's (the check below prints `same True`).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_lanes.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_store.py" -v
prints OK
$ python3 -c "from feature_flow import lanes; from feature_flow.conductor import store; print('same', lanes.RUN_KEYS is store.RUN_KEYS)"
prints same True
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`store.py`, the compatibility seam), § Edge cases (a run paused on the old code)
- `feature_flow/lanes.py` (`Scoped`, `RUN_KEYS`), `feature_flow/state.py` (`load`, `save`)
- `tests/py/test_lanes.py`, `tests/py/test_proof.py` (`conductor()` helper)

## Answer

- **Built**:
  - New `feature_flow/conductor/store.py` (90 lines): `RUN_KEYS` and `Scoped`, moved verbatim from `lanes.py`; `number(value, key, path)`, the damaged-number Stop in one place; `RunState(dict)` with `path`, `RunState.load(path)` (through `state.load`, the not-UTF-8 Stop moved here with the same text), `num` and `save` (through `state.save`); `TicketState(Scoped)` with `num`, lane 0 meaning outside lanes (prefix `""`, every key passes through). It imports only `state` and `errors`, never `lanes`.
  - `feature_flow/lanes.py`: the two definitions removed, replaced by `from feature_flow.conductor.store import RUN_KEYS, Scoped` (re-exported under the old names).
  - `feature_flow/conductor/facade.py`: `self.all = RunState.load(self.state_file)`, `self.st = TicketState(self.all)`; `num` is `self.st.num`, `num_all` is `self.all.num`, `save` is `self.all.save()`; `reset` builds `RunState(self.state_file, kept)` and a fresh `TicketState`; `in_lane` uses `TicketState(self.all, lane)`. `get` stays `self.st.get(key, default)`, so `test_proof`'s plain-dict `c.st` still works for `ticket_at_base`.
  - New `tests/py/test_store.py` (10 tests). Test-only commit d891001 failed with `ImportError: cannot import name 'store' from 'feature_flow.conductor'`.
  - None of the three planted source strings moved; `test_trust_drive.py` and `test_trust_runner.py` are unchanged.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_store.py" -v`: `Ran 10 tests`, `OK`.
  - The RUN_KEYS check prints `same True`. Importing `feature_flow.conductor.store` first, `feature_flow.lanes` first, or `feature_flow.conductor` alone all import cleanly.
  - The 400-line check prints `over 400: []`, exit 0 (store.py 90, facade.py 2112).
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0; `tests/py/test_lanes.py` and `tests/py/golden/` unchanged. `test_golden.py` alone: 14 tests OK; `test_lanes test_proof test_settings test_conductor_package`: 76 tests OK.
  - Acceptance: 25 failures, the identical list of test names as at the base commit f9d716a (checked in a detached worktree); A3 and A4 (resume) pass.
- **Decisions**:
  - `RunState` subclasses `dict`, so the ~60 `self.all[...]`, `.get`, `.update`, `.setdefault` and `for key in self.all` sites, and `state.save`, work unchanged; it carries the file path so `num` and `save` need no conductor.
  - `self.st` is a `TicketState` outside lanes too (lane 0, empty prefix), rather than the `RunState` itself. Its `clear` then drops every key, as `dict.clear` did.
  - `Scoped` stays exactly as it was (prefix `L<k>.` for every lane, including 0) so `lanes.Scoped` behaves the same; `TicketState` subclasses it and only changes lane 0 and adds `num`.
- **Shortcuts taken**: `TicketState.num` reads the file path from `self.root.path`, so a `TicketState` over a plain dict can read and write but not `num`. Nothing builds one that way today; give it a path argument if a phase ever needs one over a bare dict.
- **For later tickets**: ticket 12 can pass `self.all` (RunState) and `self.st` (TicketState) to phases as they are. `lane_key` and the merge's `L%d.` key scan still read `self.all` directly; `TicketState(self.all, k).get(key, "")` and `.clear()` could replace them when the lane code moves.
