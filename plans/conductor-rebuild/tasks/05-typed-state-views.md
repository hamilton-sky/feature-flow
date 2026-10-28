# Add RunState and TicketState views over the state file

Type: task
Status: open
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
