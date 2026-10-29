# Move the run settings into a frozen Settings with one table of mode rules

Type: task
Status: resolved
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

- **Built**:
  - New `feature_flow/conductor/settings.py` (119 lines). It holds:
    - `MAX_LANES` and `MAX_BATCH`, moved from the facade.
    - `_env_int(name, default, environ=None)`, moved. The optional `environ` exists so the tests can pass a dict. The facade calls it with no `environ`, so it reads `os.environ` as before.
    - `Settings`, a `@dataclass(frozen=True)`. `Settings.load(feature, environ=None)` reads `FLOW_DIR`, then the profile (`profiles.pick`, then `profiles.apply`, which still fills `os.environ`), then every `_env_int` value and flag in `__init__`'s old order. `session_limit(driver)` applies the agent-driver rule.
    - `ModeRule(name, broken, stop)` and `MODE_RULES`, the 6 rows: `lanes_range`, `lanes_relay`, `lanes_top`, `driver`, `fast`, and `batch` (stop None).
    - `mode_ok(name, **facts)`. It returns True when the rule holds. When the rule is broken it raises `Stop(stop % facts)`, or returns False if the row has no STOP.
  - `feature_flow/conductor/facade.py`:
    - `__init__` builds `self.settings = Settings.load(feature)` where the values were read before. It copies every attribute existing code reads (`root`, `profile`, `max_retries`, `per_session`, `relay`, and so on). After the state loads, it sets `self.per_session = settings.session_limit(self.driver())`.
    - `start`, `lane_next` and `batch_for` ask `mode_ok` instead of writing the conditions out.
    - Removed the moved constants, `_env_int` and the now unused `profiles` import.
  - New `tests/py/test_settings.py` (11 tests): a table test with 24 rows over the 6 rules, `test_settings_are_frozen`, the defaults and values read, the profile filling the environment, the agent-driver rule, and the order of errors when two values are bad.
  - The three source strings named in the ticket (`"BUILD %s %s %s%s"`, `return "OK %s" % token`, `check_code`'s docstring) did not move. `test_trust_drive.py` and `test_trust_runner.py` are unchanged.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_settings.py" -v`: `Ran 11 tests`, `OK`, exit 0. At the test-only commit 8dcf386 it failed with `ModuleNotFoundError: No module named 'feature_flow.conductor.settings'`.
  - The same verbose run shows `test_settings_are_frozen (test_settings.SettingsLoad.test_settings_are_frozen) ... ok`. The `MODE_RULES` check prints `rules 6`, exit 0.
  - The 400-line check prints `over 400: []`, exit 0. `settings.py` is 119 lines, `planning.py` 215, and `facade.py` 2119 (was 2138).
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0. That includes `python3 -m unittest discover -s tests/py passes` (which runs test_golden's `test_mode_errors` with `tests/py/golden/` unchanged), `the conductor parses as Python 3.9` and `the conductor imports only the standard library`.
  - Also run:
    - `test_golden.py` alone: 14 tests, OK.
    - `test_agent_driven.py`: 8 tests, OK.
    - `python3 tests/package_smoke.py`: `all passed`.
- **Decisions**:
  - The agent-driver rule needs `driver()`, which reads the state loaded after the settings. So `Settings` records `per_session_given` (FLOW_TICKETS_PER_SESSION was set, and not by the profile), and the facade applies `session_limit(driver)` at the line where the rule ran before.
  - `FLOW_LANES`, `FLOW_DRIVER` and `FLOW_FAST` are not in `Settings` (spec § Decisions, Settings validation stays lazy). `start` reads them where it did, so only `start` stops on them. `FLOW_LANES must be a whole number` still comes from `_env_int`.
  - The facts for a rule are computed before the rule is asked, where the old code short-circuited. Two places are affected:
    - `batch_for`'s `self.num("lanes")`. `next` has already read `self.num("lanes")` in the same call before it reaches `batch_for`, so a damaged key still stops at the same place.
    - `start`'s `Path.cwd().resolve()`, which now runs even with one lane. `git.toplevel()` already ran in that folder.
  - `lane_next` asks `lanes_relay` with `lanes=self.num("lanes")`. It is only reached when that number is above 1, so the row reduces to the old `if self.relay`.
  - Rows are keyed by name, and `mode_ok` raises KeyError for an unknown name (a programming error, not a STOP).
- **Shortcuts taken**: none.
- **For later tickets**:
  - The acceptance file `plans/conductor-rebuild/acceptance/test_rebuild_modes.py` has 3 failures: `test_other_commands_ignore_a_bad_flow_lanes`, `test_patching_check_code_on_the_class_turns_the_code_check_off` and `test_batch_preconditions`. They fail the same way at the base commit f10963b, before this ticket. In each, `twins` compares the state's `code_files` between the old and the new code, and the list differs because ticket 03 replaced `conductor.py` with the package files. That is not a mode-rules difference. The other 10 tests in that file pass, including every mode-rule STOP text and the two-bad-settings order. A later ticket, or the conductor at the acceptance run, needs to know this.
  - `Settings` is on `Conductor.settings`. Ticket 05 and later can read it instead of the copied attributes. The copies stay because tests and code set some of them (for example `per_session`).
