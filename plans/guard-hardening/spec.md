# guard-hardening — Spec

## Problem

feature-flow lets a builder subagent build each ticket while the conductor runs the gate and the floor guard and a fresh reviewer checks the work. Today a builder can edit the tool that judges it. Each `scripts/flow.py` call is a new process that loads `feature_flow/` (or `.feature-flow/feature_flow/` in an install), so a committed edit to `floorguard.py` or `scripts/*.py` runs on the next `next`, and the floor guard says `clean` (reproduced on 0.1.6). With an `install --private` install those files are excluded from git, so the edit is invisible to git altogether.

The floor guard also misses common ways of weakening a bar (focused tests `it.only`, `self.skipTest(`, `pyproject.toml` test settings), the assertion-count warning is dropped by the conductor when the guard passes, the gate and smoke test have no timeout, and `floorguard.py` and `gate.py` still reproduce mawk's byte handling although the bash scripts are gone.

## Goal and the bar

The conductor notices a build that changed the code it runs; the floor guard covers the listed gaps with tests for each; the mawk leftovers are gone from `floorguard.py` and `gate.py`; the gate and smoke test time out; and this repo's own committed copies of the tool match the source. Released as 0.2.0.

**The bar.** `python3 -m unittest discover -s tests/py && bash tests/run.sh` passes, the two tamper tests (committed install, `--private` install) fail on 0.1.6 and pass now, and every CI job (Ubuntu, macOS, Windows, package) is green on the PR. Ticket 10 runs it.

## Scope

In: goals 1 to 5 below, README (floor guard categories, settings table, Caution), `guides/build.md`, version 0.2.0.
Not in scope: any change to the planner or plan-reviewer flow; an end to end run on Codex; a real agent run on Windows; the BUILD/REVIEW/DONE/STOP/HANDOFF protocol and the `REVIEW: PASS|FAIL` contract; the mawk-era code in `tickets.py`, `status.py`, `view.py`, `install.py` (named, left alone); porting `tests/run.sh` to Python.

## Design

**Goal 1, loaded-code snapshot.** When the conductor picks a ticket it records `code_sha` in the run state: one sha256 over the files it actually uses: every `*.py` of the `feature_flow` package it was imported from (the directory of the module, `__pycache__` excluded), every `*.py` in the `scripts` folder it was started from, and the role and guide files `prompts.find_file` resolves for `build` and `review`. After the build (`judge_build`, before anything else) and after the review (`judge_review`) it recomputes. A difference prints `STOP flow code changed while building <ticket>: <files>. if intended, the ticket needs a line: Floor: allow flow-edit`. The `Floor:` line is read from the ticket as it was at the base commit, with the same function the floor guard uses. When allowed, the snapshot is refreshed. The check does not depend on git seeing the files, so it works the same for a source checkout, a committed install and a `--private` install, and it never fires on edits made before the run. It is a tripwire, not a sandbox: a builder that edits the conductor can edit the check too. README says so.

**Goal 2, narrowed.** New `SKIP` patterns: `.only(` and `fit(`, `fdescribe(` only on lines of test-looking paths and not preceded by `.`, `def ` or a word character (`model.fit(` and `def fit(` are look-alikes); `self.skipTest(`, `pytest.importorskip`, `@unittest.expectedFailure`; also Go `t.Skipf(`/`t.SkipNow(`, Rust `#[ignore = `. New `CONFIG` files: `.coveragerc`, `.flake8`, `.pylintrc`, `.golangci.y*ml`, `karma.conf.*`, `playwright.config.*`, `cypress.config.*`, `codecov.yml`, `.nycrc*`, `setup.cfg`, `pyproject.toml`, `package.json`. Not flagged as whole files: `conftest.py` (added lines containing `collect_ignore`, `pytest_collection_modifyitems`, `deselect` or `skip` are findings), `Makefile` (flagged only when a `commands.md` command starts with `make`). `pyproject.toml` and `setup.cfg` are section aware: a changed line counts only inside a test or lint section (`tool.pytest*`, `tool.coverage*`, `tool.mypy`, `tool.ruff*`, `tool.pylint*`, `tool.pyright`, `tool.black`, `tool.isort`, `tool:pytest`, `flake8`, `mypy*`, `coverage:*`), found by mapping each hunk's changed lines to the last `[section]` above them in the new file; `[tool.poetry]` dependencies are not flagged. `package.json` is parsed with `json` at base and HEAD and flagged when the value of `jest`, `scripts`, `eslintConfig`, `nyc`, `c8`, `mocha` or `ava` differs (a file that is not valid JSON counts as changed). The "fewer assertions" warning stays a warning in the guard (counted over test-file paths only) and the conductor passes it to the reviewer's prompt instead of dropping it.

**Goal 3, plain Python.** `floorguard.py` and `gate.py` lose `_awk_assign`, byte lower-casing and "parity" wording; text is `str`, the 100 byte cut is 100 characters. Exit codes, category names and the `category: path: text` line stay. The `git diff` runs once. `tests/run.sh` and `jq` stay (it tests the viewer data, `--json`, the installer and the demo, not mawk parity); the CI matrix loses the mawk and gawk jobs, leaving one Ubuntu and one macOS job.

**Goal 4, smaller fixes.** `FLOW_GATE_TIMEOUT` (minutes, default 30, `0` none) applies to the gate commands and the smoke test; on timeout the whole process tree is killed (POSIX: own session and `killpg`; Windows: `taskkill /T /F`). A gate timeout is a gate failure sent back to the builder; a smoke timeout is a STOP. A failing smoke test writes its output to `.feature-flow/state/<feature>.smoke.log` and the one-line STOP names that file and says the last 40 lines are in it. The run limit is recomputed in `pick_ticket` from the current ticket count. The limit message says `phases`.

**Goal 5, this repo's copies.** In this repo `scripts/flow.py` and `prompts.find_file` find the source `feature_flow/`, `guides/` and `agents/` first, so `.feature-flow/feature_flow/` (0.1.4), `.feature-flow/guides/` and `.feature-flow/agents/` are dead copies and are deleted. A unit test installs into a temp dir and requires every `.claude/` and `.agents/` file the installer writes to equal the committed copy, which refreshes the stale `.claude/skills/feature-flow/SKILL.md`.

## Decisions

- Tamper fix: snapshot of what the conductor loads, not `installed.txt` against `installed.sha256`. The installer keeps files the user edited and records the old hash for them, so the brief's check would STOP on every `next` after any customisation, and this repo has no such record. Rejected as written.
- A change is a STOP (not a finding sent back): with `--private` the changed file is not in git, so a builder cannot be told to restore it from git.
- No diff-based `flow-edit` category in the floor guard; the snapshot covers the same files and more. `Floor: allow flow-edit` is still the way to allow it.
- Goal 3 keeps `tests/run.sh` and `jq`; the brief's assumption that the bash scripts are all gone is wrong (`tests/smoke-real.sh`, `examples/demo.sh` remain).
- Goal 5 is reworked: the dead copies are removed, and what is checked is the copies that are used (`.claude/`, `.agents/`).

## How this plan is built (read before running it)

Every ticket edits `feature_flow/`, which in this repo is the conductor's own code. Run this plan's conductor from a pinned checkout of the 0.1.6 tag so it is judged by the old guard: `git fetch --tags && git worktree add ../ff-0.1.6 v0.1.6`, then `python3 ../ff-0.1.6/scripts/flow.py guard-hardening <command>` from this repo (it loads its own package and guides and reads plans and git from the current directory). Each ticket carries `Floor: allow ...` for what it legitimately changes. Tickets 08 to 10 touch the skills, README and `guides/build.md`: build them after PR #34 (the one-command flow) is merged and this branch has merged main.
