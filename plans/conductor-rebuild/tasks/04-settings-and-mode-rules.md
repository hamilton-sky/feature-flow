# Move the run settings into a frozen Settings with one table of mode rules

Type: task
Status: open
Blocked by: 03
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_settings.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 2 of the design. Add `feature_flow/conductor/settings.py` (new) with:

- `Settings`, a `@dataclass(frozen=True)` built from the environment, the profile and `commands.md`: everything `Conductor.__init__` reads today (`profiles.pick` and `profiles.apply`, `FLOW_MAX_RETRIES`, `FLOW_MAX_REVIEW_ROUNDS`, `FLOW_GATE_TIMEOUT`, `FLOW_GATE`, `FLOW_TICKETS_PER_SESSION` with the agent-driver rule, `FLOW_SMALL_FILES`, `FLOW_SMALL_LINES`, `FLOW_BATCH` capped at `MAX_BATCH`, `FLOW_SCOUTS`, `FLOW_RELAY`, `FLOW_INVOKE`, `FLOW_DIR`) and `_env_int`. The facade builds it once in `__init__`, at the point the values are read now, and keeps `per_session` and the other attributes existing code reads (`tests/py/test_agent_driven.py` reads `Conductor('f', 'scripts').per_session`).
- `MODE_RULES`, one table of exactly 6 rows, each a condition and the STOP text it raises (or none): (1) the `FLOW_LANES` range (1 to `MAX_LANES`), (2) lanes with relay (one row, asked by both `start` and `lane_next`), (3) lanes need the repo top, (4) `FLOW_DRIVER` values, (5) `FLOW_FAST` values, (6) the batch preconditions of `batch_for` (fast mode, gate on, no relay, no lanes, a size of 2 or more; no STOP, the batch is empty). The callers ask the table instead of writing the conditions out. `start`'s `lane(s) ... still hold tickets` STOP is not a mode rule and stays where it is; `FLOW_LANES must be a whole number` still comes from `_env_int`.

Keep each check where it runs today: a bad `FLOW_LANES` still stops only `start`, and several bad values give the same first STOP as now (spec.md § Edge cases). STOP texts are byte for byte the same. Add `tests/py/test_settings.py` (new): one table test row per rule (the condition, and the exact STOP text or none), a test named `test_settings_are_frozen` that builds a Settings and asserts assigning to a field raises `dataclasses.FrozenInstanceError` (documented as the error a frozen dataclass raises: map.md § Decisions so far), and the order of errors when two values are bad.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- The state file views: ticket 05.
- Budget settings and the budget code (`FLOW_BUDGET`, `set_budget`): ticket 11.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_settings.py" -v` prints `OK`.
- `Settings` is frozen (`test_settings_are_frozen ... ok` in the verbose run below) and `MODE_RULES` has the 6 rows above (the check below prints `rules 6`).
- No module of the package other than `facade.py` reaches 400 lines (the check below).
- `bash tests/run.sh` passes, including `test_golden.py`'s `test_mode_errors` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_settings.py" -v
prints test_settings_are_frozen
prints OK
$ python3 -c "import sys; from feature_flow.conductor.settings import Settings, MODE_RULES; print('rules', len(MODE_RULES)); sys.exit(0 if len(MODE_RULES) == 6 else 1)"
prints rules 6
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`settings.py`), § Edge cases, § Decisions (Settings validation stays lazy)
- `feature_flow/conductor/facade.py` (new in ticket 03): `__init__`, `start`, `lane_next`, `batch_for`, `_env_int`
- `feature_flow/profiles.py`, `tests/py/test_agent_driven.py`

## Answer
