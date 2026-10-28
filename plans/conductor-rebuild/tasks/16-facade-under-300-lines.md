# Bring the facade under 300 lines

Type: task
Status: open
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
