# Port the ticket graph reader to Python

Type: convert
Status: open
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
