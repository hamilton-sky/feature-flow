# Build the conductor, the build and check phases

Type: task
Status: open
Blocked by: —
Test first: yes

Add the conductor in Python, the first piece of feature-flow written in Python. Python 3.9 or later, standard library only, no third-party packages, and it must run the same on Linux, macOS and Windows (use `subprocess` with argument lists, never a shell string; `pathlib` for paths). Layout:

- `feature_flow/` at the repo root, a package: `cli.py` (argument parsing and `main()`), `conductor.py` (the state machine), `state.py` (reading and writing the state and log files). Later scripts move into this package too, so keep ticket parsing and git helpers in their own small modules (`tickets.py`, `git.py`) rather than inside the conductor.
- `scripts/flow.py`, a shim of a few lines: it puts the directory that holds `feature_flow/` on `sys.path` (the repo root, or `.feature-flow/` in an installed repo) and calls `feature_flow.cli.main()`.
- `pyproject.toml` declaring the package, `requires-python = ">=3.9"` and a console script `feature-flow = feature_flow.cli:main`, so a later PyPI release needs no code change. Do not publish anything.
- `.gitignore` gains `__pycache__/` and `*.pyc`, so running the code never dirties the tree (the conductor STOPs on a dirty tree).
- Unit tests under `tests/py/` run with `python3 -m unittest discover -s tests/py`; `tests/run.sh` calls that command, so `bash tests/run.sh` still runs everything. The black-box checks in `tests/run.sh` call `python3 scripts/flow.py` exactly as a user would.

It owns the order of phases for a session that drives the flow. This ticket covers `next` up to asking for a review. Until the follow-up Python plan ports them, it calls the existing bash scripts `scripts/flow-status.sh`, `scripts/gate.sh` and `scripts/floor-guard.sh` as subprocesses; keep each call in one function so that port can swap it for an in-process call.

Usage: `python3 scripts/flow.py <feature> next`. It reads `plans/<feature>` (honouring `FLOW_DIR` and `FLOW_TICKETS`) and keeps its state in `.git/flow-<feature>.state` as key=value lines: ticket, base sha, review sha, phase, attempt, round (one counter shared by gate, floor guard and review), runs so far. It appends `HH:MM:SS,<NN>,<EVENT>` to `.git/flow-<feature>.log` for every line it prints and for each check it runs (`GATE-PASS`, `GATE-FAIL`, `GUARD-PASS`, `GUARD-FAIL`). Both files live under `.git`, so the tree stays clean. It prints exactly one line:

- `BUILD <ticket-path> <NN> <base-sha>` when a builder must run. `<base-sha>` is `git rev-parse HEAD` when the ticket is first handed out.
- `REVIEW <ticket-path> <NN> <base-sha>` after the ticket is resolved, the tree is clean, and the gate and the floor guard both passed. Save the current `HEAD` as review sha before printing it. The script runs the checks; the session never does.
- `STOP <reason>` and exit 1 on a problem.

Judge from the repo, never from the caller. After a BUILD, the next `next` reads the ticket's Status (`resolved`, `done`, `closed` are done; `claimed` and `in-progress` are reset to `open`) and `git status`. A resolved ticket with a dirty tree is `STOP working tree is dirty after <name>, it should have been committed`. Run the smoke command before the first BUILD of each ticket. A failing gate or floor guard appends its output to the ticket as `## Review findings (round N, gate)` or `(round N, floor guard)`, sets the ticket open, commits `chore(<feature>): NN review findings, round N`, and prints BUILD again. STOP comes on the failure after `FLOW_MAX_REVIEW_ROUNDS` send-backs, as in `auto-flow.sh`.

`scripts/auto-flow.sh` is the reference for names, limits and messages (`implement`, `send_back`, `ticket_state`, `set_open`, `smoke_command`). Copy its policy; do not change it. It is deleted later in this plan, so `flow.py` must not call it or source it.

## Not in this ticket

- The reviewer's verdict, `DONE`, and the reviewer-edit and run-limit stops: ticket 04.
- `start`, `prompt` and `HANDOFF`: later tickets.

## Done when

- On a fresh plan in a temp repo, `python3 scripts/flow.py f next` prints exactly `BUILD plans/f/tasks/01-a.md 01 <sha>` with `<sha>` equal to `git rev-parse HEAD`, exits 0, creates `.git/flow-f.state`, appends a `BUILD` line to `.git/flow-f.log`, and leaves `git status --porcelain` empty.
- After the ticket is set to `resolved` and committed, `next` prints `REVIEW plans/f/tasks/01-a.md 01 <the same sha>`, the state records the current `HEAD` as review sha, and the log has `GATE-PASS` and `GUARD-PASS` lines.
- A ticket still `claimed` is reset to `open` and BUILD is printed again; after `FLOW_MAX_RETRIES` attempts `next` prints `STOP 01-a is still unresolved after 2 attempt(s)` and exits 1.
- A failing `Test:` in commands.md appends `## Review findings (round 1, gate)`, commits `chore(f): 01 review findings, round 1`, and prints BUILD; on the 4th failure `next` prints `STOP 01-a still fails the gate after 3 round(s)` and exits 1. A resolved ticket with an uncommitted file prints the dirty-tree STOP.
- `python3 -m unittest discover -s tests/py` passes, `python3 -c 'import ast,sys; [ast.parse(open(f).read(), feature_version=(3, 9)) for f in sys.argv[1:]]' feature_flow/*.py scripts/flow.py` succeeds, and `grep -rlE '^(import|from) ' feature_flow | xargs grep -hE '^(import|from) ' | grep -vE '^(import|from) (feature_flow|\.|os|sys|re|subprocess|pathlib|argparse|secrets|time|datetime|shlex|typing|dataclasses|__future__|json|textwrap|tempfile|shutil|enum)\b'` prints nothing (standard library only).
- After `bash tests/run.sh`, `git status --porcelain` is empty.
- `bash tests/run.sh` exits 0 and has a `flow.py` section with a check for each bullet above.

## Reference

- spec.md § Interfaces, Edge cases
- scripts/auto-flow.sh (read only)
- scripts/flow-status.sh, scripts/gate.sh, scripts/floor-guard.sh (read only)
- tests/run.sh (the `newrepo` and `flow` helpers)
- plans/interactive-flow-python/map.md (the follow-up plan that ports the other scripts into `feature_flow/`)
- plans/in-session-mode/tasks/02-conductor-build-and-checks.md (the earlier version)

## Answer
