# Turn conductor.py into the package, with errors and the Planner split out

Type: task
Status: open
Blocked by: 01
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor.py, feature_flow/conductor/, pyproject.toml, tests/run.sh, tests/py/test_conductor_package.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py, tests/py/test_install.py, tests/py/test_state_report.py

Step 1 of the design. The user chose the package (brief, Decided, option A): existing tests change only the path they name.

Replace `feature_flow/conductor.py` with the package `feature_flow/conductor/` (new):

- `feature_flow/conductor/facade.py` (new) holds the `Conductor` class as it is now, minus what moves below. `start` (with `return "OK %s" % token`) and `check_code` (a method, same docstring, same indent) stay in it to the end of the plan, because four trust tests read those strings (spec.md § Decisions, Tests that name `conductor.py`).
- `feature_flow/conductor/errors.py` (new) holds `Stop` and `NoPhase`.
- `feature_flow/conductor/planning.py` (new) holds a `Planner` with `plan_prompt`, `plan_review_prompt`, `plan_accept`, `plan_scouts`, `plan_scout_prompt`, `consult_prompt` and `brainstorm_prompt`, and the helpers only they use (`no_plan_yet`, `draft_text`, `read_text`, `save_brief`, `brainstorm_for`, `plan_scout_key`, `HELPERS`, `HELPER_LIMITS`, `LENSES`). The facade's methods of the same names forward to it, so `feature_flow/cli.py` is not edited.
- `feature_flow/conductor/__init__.py` (new) re-exports `Conductor`, `Stop`, `NoPhase`, `followups_only`, `section_after`, `demote`, `owner_hash`.
- `feature_flow/conductor/policy/`, `feature_flow/conductor/phases/` and `feature_flow/conductor/schedulers/` (new), each with an `__init__.py` holding only a docstring, so `pyproject.toml` can list all four packages now: add `feature_flow.conductor`, `feature_flow.conductor.policy`, `feature_flow.conductor.phases`, `feature_flow.conductor.schedulers` to `[tool.setuptools] packages`.

Imports are absolute (`from feature_flow.conductor.errors import Stop`); `tests/run.sh` rejects `from . import x` and standard modules outside its list (spec.md § Decisions, Imports). Keep every method name the existing tests use (spec.md § Interfaces, the compatibility seam).

Tests, per the Decided line (spec.md § Decisions, Tests that name `conductor.py`), changing only the path each names:

- `tests/py/test_trust_drive.py`: the `PlantedBytecode` test (it checks the source holds `b'"BUILD %s %s %s%s"'`) and `Holes.test_a_builder_commit_that_makes_check_code_return_early` (it inserts `return` after `check_code`'s docstring) point at `feature_flow/conductor/facade.py` (new); every other mention of `feature_flow/conductor.py` (bytes appended, the STOP that names the file, the trust file's list) points at `feature_flow/conductor/__init__.py` (new).
- `tests/py/test_trust_runner.py`: `PlantedBytecode.plant` (it checks `b'return "OK %s" % token'`, same size after the edit), `PlantedBytecodeCrlf.prepare` (it converts the planted file to CRLF, so it names the same file as `plant`) and `test_hole_a_a_committed_return_in_check_code` (it asserts `check_code`'s docstring is in the file and inserts `return` after it) point at `feature_flow/conductor/facade.py` (new); other mentions at `feature_flow/conductor/__init__.py` (new); the `LinkedFolders` fake file system is not touched.
- `tests/py/test_install.py`: `.feature-flow/feature_flow/conductor/__init__.py` (new, once installed) is installed. `tests/py/test_state_report.py`: appends `Conductor.next = crash` to `feature_flow/conductor/__init__.py` (it imports `Conductor`, so the run still crashes).
- `tests/run.sh`: `flowrepo` copies the `feature_flow/conductor/` folder too, without `__pycache__`. Its other lines stay.

No assertion changes. A new `tests/py/test_conductor_package.py` (new) checks: every folder with an `__init__.py` under `feature_flow/conductor/` is listed in `pyproject.toml`'s packages; every `.py` file there parses with `ast.parse(..., feature_version=(3, 9))` (the `tests/run.sh` check reads only `feature_flow/*.py`); the seven names above import from `feature_flow.conductor`, and `feature_flow.conductor.errors.Stop is feature_flow.conductor.Stop`; `Planner` has the seven methods.

## Not in this ticket

- Settings, store, policies and the rest of the split: tickets 04 to 16. The facade may stay long here.
- The ratchet test (line counts): ticket 14.

## Done when

- `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` prints the three classes, and `feature_flow/conductor.py` does not exist.
- `python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v` prints `OK`.
- `facade.py` holds `start`'s `return "OK %s" % token` and `check_code`'s docstring (the check below prints `facade strings True`).
- `python3 tests/package_smoke.py` prints `all passed` (needs the `build` module and the network to fetch setuptools).
- `bash tests/run.sh` passes, including `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"
prints NoPhase
$ python3 -c "import os,sys; gone = not os.path.exists('feature_flow/conductor.py'); print('conductor.py gone:', gone); sys.exit(0 if gone else 1)"
prints conductor.py gone: True
$ python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v
prints OK
$ python3 -c "import pathlib,sys; t=pathlib.Path('feature_flow/conductor/facade.py').read_bytes(); ok=b'return \"OK %s\" % token' in t and b'Stop when the files the conductor runs from changed since the ticket was picked.' in t; print('facade strings', ok); sys.exit(0 if ok else 1)"
prints facade strings True
$ python3 tests/package_smoke.py
prints all passed
needs the build module (pip install build) and the network
```

## Reference

- spec.md § Design, § Interfaces, § Decisions (where the Conductor class lives, Packaging, Imports)
- spec.md § Decisions (Tests that name `conductor.py`)
- `feature_flow/conductor.py` (planning section at the end of the class; `consult_prompt`, `brainstorm_prompt`, `plan_scouts`, `plan_scout_prompt`)
- `pyproject.toml`, `tests/package_smoke.py`, `tests/run.sh` (`flowrepo`, the Python 3.9 parse check)

## Answer
