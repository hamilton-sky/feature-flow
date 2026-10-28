# Run the checks before each ticket as an ordered list of guards

Type: task
Status: resolved
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

- **Built**:
  - New `feature_flow/conductor/budget.py` (101 lines): `GAP`, `set_budget`, `tick`, `spent_minutes`, `note_slowest`, `budget_report`, `budget_cmd`, `check_budget`, moved from the facade as they were, as functions of the conductor (`self` -> `c`, `self.x()` -> `x(c)` within the module). Texts, state keys and log events unchanged.
  - New `feature_flow/conductor/guards.py` (152 lines): `check_replan`, `smoke_command`, `run_smoke` moved from the facade as they were; `Guard` (`name`, `stage`, `run(c, busy)` -> None or a line); `SessionHandoff` ("session": `WAIT <busy>` with busy lanes, else `handoff()`), `Replan` (only with no lane busy), `Budget` (`check_budget(offer=not busy)`), `Smoke` (stage "start"); `BEFORE_TICKET = (SessionHandoff(), Replan(), Budget(), Smoke())`; `before_ticket(c, busy=(), stage="pick", only=None)` runs them in order and returns the first line. `mark_relay(c, view)`, `Relay`, `AFTER_PHASE = (Relay(),)`, `after_phase(c)`.
  - `schedulers/serial.py`: `pick_ticket` calls `guards.before_ticket(c)` where the handoff / `check_replan` / `check_budget` lines were; `start_ticket` calls `guards.before_ticket(c, stage="start")` after `snapshot_code` where `run_smoke` was.
  - `schedulers/lane.py`: `dispatch` calls `before_ticket(c, busy, only=("session",))` where its session check was, and `before_ticket(c, busy, only=("replan", "budget"))` where its re-plan and budget calls were (same places, so its other differences stay: the session check before the ready/free test, the others only with a ready ticket and a free lane).
  - `facade.py` (851 -> 731 lines): the moved code is gone; `budget_cmd` forwards to `budget.budget_cmd`; `num_all` stays (others use it); `pass_ticket`, `start` and `next` call `time_budget.note_slowest/set_budget/tick` (the module is imported as `time_budget` because `start` has a local `budget`); both relay checks in `next` are `guards.after_phase(self)` at the same spot. `handoff`, `start`'s `return "OK %s" % token` and `check_code` unchanged. Unused import `gate` dropped.
  - `phases/build.py`, `review.py`, `test.py`, `final.py`: `ws.<st|all>["relay_handoff"] = "1" if ws.relay else ""` -> `guards.mark_relay(ws, ws.<st|all>)`. The `BUILD %s %s %s%s` string is untouched.
  - New `tests/py/test_guards.py` (18 tests): order and stages of `BEFORE_TICKET`; all pass in order; the session handoff wins and nothing later runs; a re-plan Stop wins over the budget; `only` keeps the order; lane variants (WAIT with busy lanes, HANDOFF with none, busy lanes count to the limit, no re-plan check and `offer=False` beside busy lanes, a real `dispatch` beside a busy lane and with none, `lease` recorded); serial `pick_ticket` runs the guards then the smoke after the code snapshot, and hands off at the session limit before the others; relay: `after_phase`, `mark_relay`, `next` hands off before judging a ticket phase (`build`) and a run-wide one (`test`) with `judge` patched to fail, and a build handed out under `FLOW_RELAY=1` hands off on the next call.
  - Test-only commit e237381: the discover command failed with `ImportError: cannot import name 'budget' from 'feature_flow.conductor'`.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_guards.py" -v`: `Ran 18 tests`, `OK`.
  - `before each ticket: 4` (exit 0).
  - `over 400: []` (exit 0); largest is still `schedulers/lane.py`.
  - `facade strings True` (exit 0).
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0. Also ran test_budget_drive, test_agent_driven, test_golden, test_schedulers, test_phases, test_conductor_package, test_trust_drive, test_trust_runner, test_lanes_drive, test_timeout, test_guards together: `Ran 172 tests`, `OK`. No existing test changed (test_trust_drive.py and test_trust_runner.py untouched: no source string moved).
  - Acceptance: 15 failures, the same list as at 52a5105 (diffed against a base worktree).
- **Decisions**:
  - The guards call the moved functions (`check_replan`, `run_smoke`, `budget.check_budget`) through module lookups, so a test can replace each with a recorder; the facade no longer has `check_replan`, `check_budget`, `run_smoke`, `tick`, ... methods (nothing outside called them but the schedulers and the facade itself).
  - Smoke is the fourth guard with `stage = "start"`, run by `start_ticket` after the snapshot, so the order stays: it only runs once the pick guards let a ticket start.
  - The lane scheduler runs subsets (`only=`) at its two existing places rather than all at once: moving its session check after the ready/free test would change what a lane run prints at the session limit when nothing is ready.
  - `handoff()` stays a facade method: `next`, the guards and both schedulers use it.
- **Shortcuts taken**: none.
- **For later tickets**:
  - Ticket 16 (facade under 300): the facade is 731 lines; the budget and guard code is out of it. `num_all` is still there for `end.py`, `test.py` and `budget.py`.
