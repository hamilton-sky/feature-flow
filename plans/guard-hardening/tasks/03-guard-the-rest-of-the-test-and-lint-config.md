# Guard more test and lint config, section aware

Type: task
Status: resolved
Blocked by: 01
Test first: yes
Floor: allow skip, suppress, threshold, config

Add whole-file entries to `CONFIG` in `feature_flow/floorguard.py`: `.coveragerc`, `.flake8`, `.pylintrc`, `.golangci.y*ml`, `karma.conf.*`, `playwright.config.*`, `cypress.config.*`, `codecov.yml`, `.nycrc*`. Then three files judged by content, not name, from the diff of base to HEAD (outside the plans folder), each reported as `config: <path>` and allowed by `Floor: allow config`:

- `pyproject.toml` and `setup.cfg`: map each changed line (use `git diff --unified=0` hunk headers and the new file's text) to the last `[section]` header above it; flag only when that section is one of `tool.pytest*`, `tool.coverage*`, `tool.mypy`, `tool.ruff*`, `tool.pylint*`, `tool.pyright`, `tool.black`, `tool.isort` (pyproject) or `tool:pytest`, `flake8`, `mypy*`, `coverage:*` (setup.cfg). A changed `[tool.poetry]` dependency or a `[project]` version is clean. A deleted section header or deleted lines in those sections count too (use the base text for deleted lines).
- `package.json`: parse base and HEAD with `json`; flag when the value of any of `jest`, `scripts`, `eslintConfig`, `nyc`, `c8`, `mocha`, `ava` differs, or when either side is not valid JSON and the bytes differ. A changed `version` or `dependencies` is clean.
- `conftest.py`: not a config file. Flag `config: conftest.py` only when an added line contains `collect_ignore`, `pytest_collection_modifyitems`, `deselect` or `skip`. A new fixture is clean.
- `Makefile`: flag `config: Makefile` only when it changed and the plan's `commands.md` has a command line (Build, Test, Lint or Smoke) that starts with `make`. Read `commands.md` from the working tree. Otherwise it is clean. Explain this in a comment above `CONFIG`.

Tests in `tests/py/test_floorguard.py`, one caught and one look-alike per item, building real two-commit repos where hunks matter (use `helpers.Repo`).

## Not in this ticket

- The skip patterns (02) and the assertion count (04).
- README: ticket 09.

## Done when

- `python3 -m unittest discover -s tests/py -k floorguard` passes and covers: a coverage threshold line changed under `[tool.coverage.report]` is caught, a `[tool.poetry.dependencies]` change is not; a changed `scripts.test` in `package.json` is caught, a changed `version` is not; a new fixture in `conftest.py` is not caught, `collect_ignore = ["x"]` is.
- A changed `Makefile` is caught when `commands.md` has `Test: `make test``, and clean when it does not.
- `Floor: allow config` silences each of them.
- All existing tests still pass.

## Reference

- spec.md § Design (Goal 2)
- feature_flow/floorguard.py (`CONFIG`, the `touched` step in `run`), tests/py/helpers.py

## Answer


**Built**: `feature_flow/floorguard.py` (nine whole-file entries added to `CONFIG`; new `_content_config` with `_guarded_toml` and `_package_json_changed` for pyproject.toml, setup.cfg, package.json, conftest.py, Makefile; comment above `CONFIG` explains the Makefile rule); `tests/py/test_floorguard.py` (new `ConfigTests`, 11 tests, real two-commit repos).

**Proof**:
- `python3 -m unittest discover -s tests/py -k floorguard`: Ran 37 tests, OK. ConfigTests cover each item caught and look-alike: coverage `fail_under` under `[tool.coverage.report]` caught, `[tool.poetry.dependencies]` clean; `scripts.test` caught, `version`/`dependencies` clean; `collect_ignore = ["x"]` caught, new fixture clean; Makefile caught with `Test: `make test``, clean with the default commands.md; every caught case is silenced by `Floor: allow config` in the base ticket (the coverage case needs `threshold` too, as `fail_under` is also a threshold line).
- Tests were first run before the code and failed (18 failures, nothing flagged).
- `python3 -m unittest discover -s tests/py`: Ran 154 tests, OK. `bash tests/run.sh`: 441 passed, 0 failed.

**Decisions**: non-starred pyproject sections (`tool.mypy`, `tool.pyright`, `tool.black`, `tool.isort`) also match their sub-tables (`tool.mypy.overrides`); otherwise `[[tool.mypy.overrides]]` would escape. setup.cfg `flake8` and `mypy*` etc. match by prefix. A changed line is judged by the section above it in the new text, a deleted line by the section in the base text; a changed header line counts as in its own section. A package.json that is new or deleted counts as differing.

**Shortcuts taken**: toml section headers are found by a line regex, not a parser, so a multi-line array whose continuation line looks like `[name]` is read as a header. Worth upgrading only if that shows up in a real repo. The Makefile check reads only the first-token `make` in commands.md lines `Build|Test|Lint|Smoke:`.

**For later tickets**: ticket 05 (plain Python gate and floorguard) and 08 (committed copies under `.feature-flow/` and `scripts/`) should pick up the changed `floorguard.py`; the committed `.feature-flow/feature_flow/floorguard.py` was not synced here.
