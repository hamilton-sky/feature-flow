# Check the prerequisites and the Python baseline

Type: settle
Status: resolved
Blocked by: —
Test first: no

This plan ports the remaining bash scripts and must not start before `plans/interactive-flow` has written the Python conductor. Confirm that, and record which Python the places feature-flow runs in actually have, so the ports target a version that exists everywhere.

The user chose on 2026-10-06 to start the ports before the headless loop is removed. Only two ports touch what `plans/interactive-flow` ticket 10 deletes: ticket 05 (the cost log leaves `flow-view.sh`) and ticket 06 (`install.sh` stops installing the headless parts). Both wait for it and say so.

1. Run `bash scripts/flow-status.sh interactive-flow`. Ticket 03 there must be resolved and `feature_flow/conductor.py` must exist.
2. Record `python3 --version` (or `python --version`) in a Claude Code cloud session, a Codex cloud task, the GitHub macOS and Windows runners, and the maintainer's own machine. Record whether `git` is on the PATH on the Windows runner.

Put these lines in the Answer exactly:

```
Prerequisites met: yes|no
Lowest Python found: 3.<minor>
Python floor: 3.<minor>
Windows runner has git: yes|no
```

The floor is 3.9 unless a place above has something older.

## Not in this ticket

- Any port: the later tickets.

## Done when

- `grep -cE '^Prerequisites met: yes$' plans/interactive-flow-python/tasks/01-prerequisites-and-python-baseline.md` prints `1`.
- `grep -cE '^(Lowest Python found|Python floor): 3\.[0-9]+$' plans/interactive-flow-python/tasks/01-prerequisites-and-python-baseline.md` prints `2`, and `grep -cE '^Windows runner has git: (yes|no)$'` on the same file prints `1`.
- The Answer lists each place with the version it reported.

## Reference

- plans/interactive-flow/map.md
- pyproject.toml (`requires-python`)

## Answer

```
Prerequisites met: yes
Lowest Python found: 3.12
Python floor: 3.9
Windows runner has git: yes
```

Prerequisites, checked on main at 011bfde: interactive-flow ticket 03 is resolved and `feature_flow/conductor.py` exists. Ticket 10 is still open, which the user accepted on 2026-10-06; tickets 05 and 06 here wait for interactive-flow ticket 10.

Python found, per place:
- Claude Code cloud session: Python 3.13.16.
- GitHub ubuntu-latest (ubuntu24 20260927.320.1): Python 3.12.3, git 2.55.0.
- GitHub macos-latest (macos26 20260907.0351.1): Python 3.14.7, git 2.55.0.
- GitHub windows-latest (win25-vs2026 20260925.250.1): Python 3.12.10 as both `python3` and `python`; git 2.55.0.windows.5 on the PATH.
- Codex cloud task: not checked. The user has no Codex tokens left.
- The maintainer's own machine: not checked from a cloud session.

The runners were read by a temporary workflow on PR #11 (run 37458561009), removed after this answer. Nothing found is older than 3.9, so the floor stays at `requires-python = ">=3.9"` in pyproject.toml. Two places were not checked; if either has a Python older than 3.9, the README names the requirement.
