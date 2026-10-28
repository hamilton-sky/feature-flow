# Run the checks before each ticket as an ordered list of guards

Type: task
Status: open
Blocked by: 10
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_guards.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 8 of the design. Add `feature_flow/conductor/guards.py` (new) and `feature_flow/conductor/budget.py` (new).

- `budget.py`: the time budget code as it is (`set_budget`, `tick`, `spent_minutes`, `note_slowest`, `budget_report`, `budget_cmd`'s work, `check_budget`), with `GAP`. `budget_cmd` stays a facade command that forwards.
- `guards.py`: `BEFORE_TICKET`, the ordered guards both schedulers run before a ticket starts: session handoff (`per_session`), the re-plan check (`check_replan`), the budget (`check_budget`), the smoke test (`run_smoke`, after the code snapshot in `start_ticket`). `AFTER_PHASE`: relay (`relay_handoff` set when a phase is handed out, and `next` handing off before it judges anything). Keep the scheduler differences spec.md § Edge cases lists (with busy lanes: `WAIT` instead of `HANDOFF`, the re-plan check only with no lane busy, the budget offer only with no lane busy).

Add `tests/py/test_guards.py` (new): the order of `BEFORE_TICKET`; the first guard that stops or hands off wins and the later ones do not run; the lane variants; relay hands off before judging.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- New guards or a changed order: out of scope.
- The budget's environment variable and its STOP texts: unchanged, read through ticket 04's Settings where they are read now.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_guards.py" -v` prints `OK`.
- `BEFORE_TICKET` holds four guards (the check below prints `before each ticket: 4`).
- No module of the package other than `facade.py` reaches 400 lines.
- `start`'s line and `check_code`'s docstring are still in `facade.py` (the check below prints `facade strings True`).
- `bash tests/run.sh` passes, including `tests/py/test_budget_drive.py`, `tests/py/test_agent_driven.py` and `test_golden.py`'s relay and budget scenarios unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_guards.py" -v
prints OK
$ python3 -c "from feature_flow.conductor import guards, budget; print('before each ticket:', len(guards.BEFORE_TICKET))"
prints before each ticket: 4
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
$ python3 -c "import pathlib,sys; t=pathlib.Path('feature_flow/conductor/facade.py').read_bytes(); ok=b'return \"OK %s\" % token' in t and b'Stop when the files the conductor runs from changed since the ticket was picked.' in t; print('facade strings', ok); sys.exit(0 if ok else 1)"
prints facade strings True
```

## Reference

- spec.md § Interfaces (`guards.py`, `budget.py`), § Edge cases (the session handoff with busy lanes; `FLOW_RELAY=1`)
- the facade and schedulers: `pick_ticket`, `dispatch`, `start_ticket`, `run_smoke`, `handoff`, `check_replan`, the budget section, `next`

## Answer
