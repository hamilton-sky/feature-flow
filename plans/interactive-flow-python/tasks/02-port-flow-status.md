# Port the ticket graph reader to Python

Type: convert
Status: resolved
Blocked by: 01
Test first: yes

Port `scripts/flow-status.sh` to `feature_flow/status.py`, with a shim `scripts/flow-status.py` that calls it. Read the bash script and its tests in `tests/run.sh` first. Same arguments, same environment variables, same stdout and stderr text, same exit codes; standard library only, at the Python floor recorded in ticket 01. Do not fix bugs you find: keep the behaviour, note the bug under Shortcuts taken, and leave the fix to a new ticket. Every mode must match: the default table, `--next` (exit 10 when done, 11 when stuck), `--counts`, `--check` (errors and warnings), `--mermaid`, `--mermaid plain` and `--json`. Put Markdown ticket parsing in `feature_flow/tickets.py` so the other ports reuse it.

Add a parity test to `tests/run.sh`: for every fixture the existing `flow-status.sh` checks use, run `bash scripts/flow-status.sh` and `python3 scripts/flow-status.py` with the same arguments and require identical stdout and exit code. Then change `feature_flow` to import the module where it shelled out to the bash script. Leave `scripts/flow-status.sh` in place; it is deleted when every port is done.

## Not in this ticket

- Deleting `scripts/flow-status.sh` or changing who calls it besides `feature_flow`: the switch-over ticket.
- Behaviour changes of any kind.

## Done when

- `python3 scripts/flow-status.py` exists and `python3 -m unittest discover -s tests/py` passes with unit tests for `feature_flow/status.py`.
- The parity section in `bash tests/run.sh` compares both versions on every existing `flow-status.sh` fixture, reports no difference, and the output names how many fixtures it compared.
- `grep -n 'flow-status.sh' feature_flow/*.py` prints nothing (the package no longer shells out to it).
- `bash tests/run.sh` exits 0 and `git status --porcelain` is empty afterwards.

## Reference

- scripts/flow-status.sh (read only)
- tests/run.sh (the existing `flow-status.sh` checks)
- spec.md § Decisions (parity first)

## Answer

Built: `feature_flow/status.py` (every mode: table, `--next`, `--counts`, `--check`, `--mermaid`, `--mermaid plain`, `--json`) and the ticket parsing it reads, `tickets.records`, `tickets.ticket_files` and `tickets.Graph` in `feature_flow/tickets.py`, which follow the awk program's arrays one to one. `scripts/flow-status.py` is a shim shaped like `scripts/flow.py`. `checks.flow_status` now calls `status.run` in process, so the conductor no longer starts bash for it.

Proof: the "flow-status.py, parity with flow-status.sh" section of `bash tests/run.sh` runs both versions on every fixture the flow-status.sh checks use (the status repo's f, stuck, done, aws, bad and nope plans, `.scratch/x` through FLOW_DIR and FLOW_TICKETS, the ordering plans g and h, the JSON plan), plus a new one with a duplicate number, CRLF lines and an empty file, and with no feature. Each in eight modes, including an unknown one: "flow-status.py matches flow-status.sh on 96 fixture runs", comparing stdout, stderr and the exit code. `tests/py/test_status.py` holds the unit tests. `bash tests/run.sh`: 512 passed, 0 failed, tree clean.

Shortcuts taken:
- `grep -n 'flow-status.sh' feature_flow/*.py` still prints three lines, all text a user reads: the usage line in `status.py`, which must match the bash script for parity, and two Stop messages in `conductor.py`, one telling the user to run `bash scripts/flow-status.sh`. Installed projects have no `flow-status.py` yet, so that hint must stay until ticket 07 installs the shims and switches the text. The package no longer shells out to the script.
- Bash bugs kept: an empty ticket file is skipped entirely (awk never starts it); for two tickets with the same number the second one's `Blocked by`, `Type`, `Test first` and title lines are ignored because the "seen" flags are not reset; a CRLF Status line reads as an unknown status.
- Ticket files are sorted by code point; bash sorts its glob by the locale's collation. They differ only for names that share a number and differ in case or punctuation.
