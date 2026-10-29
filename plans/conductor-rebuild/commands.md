# Commands: conductor-rebuild

The real commands for this project, read from its own CI (`.github/workflows/tests.yml` runs `python3 -m unittest discover -s tests/py` and `bash tests/run.sh`; `tests/run.sh` runs that same unittest discovery itself, so Test runs it once) and CONTRIBUTING.md ("Run the checks before a pull request: `python3 -m unittest discover -s tests/py` and `bash tests/run.sh`"). There is no build step and no linter. Approved by a human when the plan is approved. Workers read this file and must not change it.

The flow runs Smoke before every ticket and Test after every ticket, so each must run without asking anything and exit non zero on failure.

- Smoke is the Python 3.9 parse check from `tests/run.sh` ("the conductor parses as Python 3.9"), copied as it is: the project's config has no faster test target, and the unittest discovery is most of the suite's time. It parses every top-level module of `feature_flow/` and `scripts/flow.py` in under a second and exits 1 on a syntax error.
- No `Quick:` line: the only subset in the project's config is the unittest discovery, which is not clearly faster than `tests/run.sh`.
- `Shared:` names the files most tickets change (the facade, the package's `__init__.py`, and the two trust tests that follow the source strings: spec.md § Decisions, Tests that name `conductor.py`), so a ticket touching one is never built beside another.
- `Acceptance:` runs only the tests under `plans/conductor-rebuild/acceptance/` (spec.md § Acceptance tests). `tests/run.sh` discovers only `tests/py`, so Test never runs them.
- Every ticket that edits `feature_flow/` is level 3 anyway; the `Sensitive:` line says so for any ticket that strays there.

Test: `bash tests/run.sh`
Smoke: `python3 -c 'import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3, 9)) for f in sys.argv[1:]]' feature_flow/*.py scripts/flow.py`
Shared: feature_flow/conductor/facade.py, feature_flow/conductor/__init__.py, pyproject.toml, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py
Sensitive: feature_flow/, scripts/, pyproject.toml
Acceptance: `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`
