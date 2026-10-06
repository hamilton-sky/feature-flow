# Interactive flow in Python — Spec

## Problem

After `plans/interactive-flow`, the conductor (`feature_flow/`, run as `scripts/flow.py`) is Python, but it still shells out to four bash scripts: `flow-status.sh` (reads the ticket graph), `gate.sh` (runs the commands in `commands.md`), `floor-guard.sh` (looks for weakened checks with awk) and `flow-view.sh` (draws the graph page). The installer is bash too. So feature-flow needs both bash and Python, does not run on Windows without a bash layer, and the fragile part, parsing ticket Markdown with awk patterns that must behave the same in mawk, gawk and BSD awk, is still there.

## Goal and the bar

Every feature-flow script is Python in the `feature_flow` package, standard library only, Python 3.9+. Each port prints the same output and returns the same exit codes as the bash script it replaces, proven by running both on the same fixtures before the bash version is deleted. Bash is no longer needed to run feature-flow, only to run the test harness.

The bar: CI is green on Ubuntu, macOS and Windows; on all three `python3 -m unittest discover -s tests/py` passes and a fixture plan driven through `python scripts/flow.py f start` / `next` reaches `REVIEW`; and `ls scripts/*.sh` lists nothing.

## Scope

In: porting `flow-status.sh`, `gate.sh`, `floor-guard.sh`, `flow-view.sh` and `install.sh` into `feature_flow/`; thin `scripts/*.py` shims; switching the conductor, guides, skills and README to the Python commands; deleting the bash scripts; a Windows CI job.

Not in scope:
- Changing any behaviour. A port that finds a bug in the bash version keeps the bug, writes it under Shortcuts taken, and a new ticket fixes it after the port.
- Publishing to PyPI or fetching a pinned version at run time: a distribution plan of its own.
- Rewriting `tests/run.sh` in Python. It stays a bash black-box harness; Windows CI runs the Python unit tests and a fixture drive instead.

## Design

```
 scripts/flow.py          shim ─┐
 scripts/flow-status.py   shim ─┤
 scripts/gate.py          shim ─┼─► feature_flow/
 scripts/floor-guard.py   shim ─┤     cli.py  conductor.py  state.py
 scripts/flow-view.py     shim ─┤     tickets.py  git.py
 install.py               shim ─┘     status.py  gate.py  floorguard.py  view.py  install.py
```

### Decisions

- **Parity first** — every port ticket adds a test that runs the bash script and the Python port on the same fixtures and compares stdout and exit code exactly. Why: the 415 existing checks prove behaviour from outside, and the parity test catches what they miss. The parity tests are deleted with the bash scripts.
- **In-process calls** — once a module is ported, the conductor imports it instead of starting a subprocess.
- **`install.sh` stays as a wrapper** — users and the README run `bash install.sh`; it becomes `exec python3 "$(dirname "$0")/install.py" "$@"` so that command keeps working on macOS and Linux.
- **Windows** — git for Windows is required (the flow is git based); bash is not.

## Migration and compatibility

Starts after `plans/interactive-flow` ticket 10 has removed the headless loop, so `auto-flow.sh` is never ported. Command names and output stay the same apart from `.sh` becoming `.py`; the skills and guides are updated in the same ticket that deletes the bash scripts.

## Risks

- awk and Python regexes differ in small ways (character classes, greedy matching) — the parity fixtures include the existing floor-guard and flow-status test cases.
- Windows paths and line endings — use `pathlib`, open text files with `newline=''` where output must match byte for byte, and test on the Windows runner.
