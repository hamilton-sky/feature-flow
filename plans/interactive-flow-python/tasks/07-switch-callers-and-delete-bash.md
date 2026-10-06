# Switch every caller to Python and delete the bash scripts

Type: task
Status: resolved
Blocked by: 02, 03, 04, 05, 06
Test first: no
Floor: allow test-delete

Every port has passed its parity test. Switch the remaining callers to the Python commands and delete the bash versions: the guides under `guides/`, both `feature-flow` skills, `tests/smoke-real.sh`, `examples/demo.sh`, the README and the plan templates now call `python3 scripts/flow-status.py`, `python3 scripts/gate.py`, `python3 scripts/floor-guard.py` and `python3 scripts/flow-view.py`. Delete `scripts/flow-status.sh`, `scripts/gate.sh`, `scripts/floor-guard.sh` and `scripts/flow-view.sh`, and the parity tests that compared them. Point the remaining `tests/run.sh` checks at the Python commands. The installer installs the `.py` shims and stops installing the `.sh` scripts.

## Not in this ticket

- The Windows CI job: the next ticket.

## Done when

- `ls scripts/*.sh 2>/dev/null` prints nothing.
- `grep -rnE '(flow-status|gate|floor-guard|flow-view)\.sh' --exclude-dir=plans --exclude-dir=.git .` prints nothing.
- `bash install.sh "$(mktemp -d)"` installs `scripts/flow-status.py` and no `scripts/*.sh`.
- `bash tests/run.sh` exits 0 and `git status --porcelain` is empty afterwards.

## Reference

- guides/, skills/feature-flow/, adapters/codex/feature-flow/, README.md, tests/run.sh, tests/smoke-real.sh, examples/demo.sh

## Answer

Every caller now runs the Python commands, and the four bash scripts are gone. `ls scripts/*.sh` prints nothing; `scripts/` holds `flow.py`, `flow-status.py`, `gate.py`, `floor-guard.py`, `flow-view.py` and `flow-view.html`.

Switched to `python3 scripts/<name>.py`: `guides/` (build, plan, show, `templates/map.md`), `skills/feature-flow/SKILL.md`, `adapters/codex/feature-flow/SKILL.md`, `README.md` (the command table, the env var table, the `--json` and `.scratch` notes), `examples/demo.sh`, `tests/smoke-real.sh`, the two Stop messages in `feature_flow/conductor.py`, and the usage lines of the four ported modules (`status.py`, `gate.py`, `floorguard.py`, `view.py`, the parity comments dropped). The install help text now reads `usage: python3 install.py ...`; `install.sh` stays the 4-line wrapper (its own comment line still says `bash install.sh`, which still works). The installer copies `scripts/` as it finds it, so it now installs the four `.py` shims, `flow.py` and `flow-view.html` and no `.sh` file (`bash install.sh <dir>` into an empty folder: 36 added, `scripts/` has those six files). One behaviour change in `feature_flow/install.py`: the leftover-skill note now also names an old skill that runs `scripts/flow-status.py`, not only the old bash form, because a skill that runs the ticket script is what the note is for (regex `scripts/flow-status\.(?:sh|py)|REVIEW: PASS`).

Deleted: `scripts/flow-status.sh`, `gate.sh`, `floor-guard.sh`, `flow-view.sh`, `tests/install-bash-reference.sh`, and in `tests/run.sh` the sections "floor-guard.sh and floor-guard.py, parity", "gate.sh and gate.py parity", "install.sh and install.py parity", "flow-status.py, parity with flow-status.sh", "flow-view.py, parity with flow-view.sh", plus the `guard_both` helper and its parity log. In `tests/py`: `test_the_shim_matches_the_bash_gate` (replaced by `test_the_shim_runs_the_gate`, which pins the shim's output and exit codes for three argument sets) and the `*.sh` copy loop in `helpers.py`.

Kept and pointed at the Python commands in `tests/run.sh`: every flow-status check (table, `--next` 0/10/11, `--counts`, `--check`, `--mermaid`, aws words, FLOW_DIR/FLOW_TICKETS, ordering hints, `--json`), every floor-guard check (the guard repo cases and the 14 `tamper` cases; `guard_both` became `guard() { python3 "$ROOT/scripts/floor-guard.py" "$@"; }`), every gate check, every flow-view check (page, history, hostile text, `.git` default, missing feature, watch), every installer check, the skill checks (a skill never runs `python3 scripts/(gate|floor-guard).py` itself) and the smoke-real checks. The scripts are run from `$ROOT/scripts` with the temp repo as cwd, so `newrepo` no longer copies scripts into each fixture repo.

Converted from parity-only fixtures to plain checks of the port: the floor-guard extras (JS, Rust and Go skips and suppressions, both empty-catch forms, a coverage threshold, a workflow file, the 100 character cut, `Floor: skip, Config` allowing two categories, default and empty base, a bad base exits 128, missing arguments, FLOW_DIR, FLOW_TICKETS) are now asserted; a new "flow-status.py, odd plans" section keeps the duplicate number, CRLF Status line and empty file fixtures; a new "flow-view.py, edge cases" section keeps the edge plan (8 bullet cap, 240 and 700 character cuts, quotes, backslashes, tabs, review rounds with and without a number or source, the Answer placeholder, CRLF, FLOW_DIR, an empty ticket file, `--out` without a value, a missing template exits 2). Added: the `install.sh` wrapper runs the installer and passes its arguments, no `*.sh` is installed, and unit tests that the installed `scripts/` holds exactly the six files and that an old skill running `scripts/flow-status.py` is named as a leftover. Dropped without a replacement: every comparison of stdout, stderr and exit code against the bash version (nothing is left to compare against), the 17 installer scenarios that only compared transcripts and trees, the live `--watch` run of both versions at once (the plain live `--watch` check of the view section stays), and the byte-for-byte tree comparison of the installer (the unit tests keep the exec-bit and sort behaviour).

Smoke from `commands.md` (frozen, not edited): its loop is `for f in scripts/*.sh install.sh tests/*.sh examples/*.sh; do [ -e "$f" ] || continue; ...`. With no `scripts/*.sh` the glob stays literal, `[ -e ]` fails and the loop continues, so an empty glob is fine; the `bash -n` checks of `install.sh`, `tests/run.sh`, `tests/smoke-real.sh` and `examples/demo.sh` and the AST parse of `feature_flow/` and `scripts/` all pass.

Proof: `ls scripts/*.sh 2>/dev/null` prints nothing; the Done-when grep (with `--exclude-dir=.claude --exclude-dir=__pycache__` as well) prints nothing; `bash tests/run.sh`: 412 passed, 0 failed, and the tree is clean afterwards (no new or changed file); `python3 -m unittest discover -s tests/py`: 91 tests OK (2 new).

Stale lines left in `plans/interactive-flow/` (not edited, another thread owns it): `plans/interactive-flow/map.md` line 11 (`bash scripts/flow-status.sh interactive-flow`) and line 15 (`bash scripts/flow-status.sh interactive-flow --mermaid`) name a command that no longer exists; the new commands are `python3 scripts/flow-status.py interactive-flow` and the same with `--mermaid`. Tickets 03 and 10 there name the `.sh` scripts only as files to read or as history. In this plan, the two "How to work this" lines of `map.md` were updated to the `.py` command; ticket 01 (resolved) and the Answers of tickets 02 to 06 still name the `.sh` scripts as history.

Shortcuts taken:
- The Done-when grep also needs `--exclude-dir=.claude --exclude-dir=__pycache__` here, because agent worktrees live under `.claude/worktrees/` and hold their own copies; the repo itself has no hit.
- `tests/py/test_install.py` does not pin that an old skill naming the bash script is still reported as a leftover: that needs the literal name in a test file, which the Done-when grep forbids. The regex keeps that alternative.
- The bash bugs listed in tickets 02 to 06 are still kept in the port; each wants its own ticket.
