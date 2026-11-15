# Commands: portable-live-page

Read from .github/workflows/tests.yml, tests/run.sh, both pyproject.toml files and packages/forkboard/tests/browser/package.json. Unix shell development gate; Python runtime remains supported on Python 3.9 and Windows as in CI. Bash and jq are required for the existing offline suite. Build dependencies and Chromium must be installed before the run; no account or model required.

Build: `python3 -m build --outdir dist`
Test: `bash tests/run.sh && python3 -m unittest discover -s packages/forkboard/tests -v && npm --prefix packages/forkboard/tests/browser test`
Lint: `python3 -c 'import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3, 9)) for f in sys.argv[1:]]' feature_flow/*.py feature_flow/conductor/*.py feature_flow/conductor/*/*.py packages/forkboard/forkboard/*.py scripts/flow.py`
Smoke: `python3 -m unittest discover -s packages/forkboard/tests -v`
Setup: `python3 -m pip install build && npm --prefix packages/forkboard/tests/browser install --no-audit --no-fund && npm --prefix packages/forkboard/tests/browser exec -- playwright install chromium`
Sensitive: `feature_flow/, packages/forkboard/forkboard/server.py, packages/forkboard/forkboard/storage.py, packages/forkboard/forkboard/live.py, packages/forkboard/forkboard/cli.py, packages/forkboard/forkboard/assets/live.js, packages/forkboard/forkboard/assets/providers.js, scripts/, guides/, skills/, adapters/`
Shared: `tests/run.sh, packages/forkboard/forkboard/cli.py, feature_flow/brainstorm_page.py`
Profile: `standard`
Lanes: `1`
Acceptance: `python3 -m unittest discover -s plans/portable-live-page/acceptance -v`

Build is the release workflow's wheel/sdist command. Lint is the repository's Python 3.9 syntax check (the project has no separate linter). Test intentionally excludes plans/portable-live-page/acceptance. No invented Quick subset. Runtime commands are specified in spec.md Interfaces and shipped documentation once implemented.
