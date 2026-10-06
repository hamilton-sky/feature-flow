# Check the prerequisites and the Python baseline

Type: settle
Status: open
Blocked by: —
Test first: no

This plan ports the remaining bash scripts and must not start before `plans/interactive-flow` has written the Python conductor and removed the headless loop. Confirm that, and record which Python the places feature-flow runs in actually have, so the ports target a version that exists everywhere.

1. Run `bash scripts/flow-status.sh interactive-flow`. Tickets 03 and 10 there must be resolved, and `scripts/auto-flow.sh` must not exist.
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
