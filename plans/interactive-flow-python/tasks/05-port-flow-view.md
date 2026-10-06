# Port the graph page generator to Python

Type: convert
Status: open
Blocked by: 01
Test first: yes

Start only after `plans/interactive-flow` ticket 10 is resolved: it removes the cost log from `flow-view.sh`, and the port must not carry it.

Port `scripts/flow-view.sh` to `feature_flow/view.py`, with a shim `scripts/flow-view.py` that calls it. Read the bash script and its tests in `tests/run.sh` first. Same arguments, same environment variables, same stdout and stderr text, same exit codes; standard library only, at the Python floor recorded in ticket 01. Do not fix bugs you find: keep the behaviour, note the bug under Shortcuts taken, and leave the fix to a new ticket. The HTML page it writes must be byte for byte the same for the same plan and git history; `scripts/flow-view.html` stays the template.

Add a parity test to `tests/run.sh`: for every fixture the existing `flow-view.sh` checks use, run `bash scripts/flow-view.sh` and `python3 scripts/flow-view.py` with the same arguments and require identical stdout and exit code. Then change `feature_flow` to import the module where it shelled out to the bash script. Leave `scripts/flow-view.sh` in place; it is deleted when every port is done.

## Not in this ticket

- Deleting `scripts/flow-view.sh` or changing who calls it besides `feature_flow`: the switch-over ticket.
- Behaviour changes of any kind.

## Done when

- `python3 scripts/flow-view.py` exists and `python3 -m unittest discover -s tests/py` passes with unit tests for `feature_flow/view.py`.
- The parity section in `bash tests/run.sh` compares both versions on every existing `flow-view.sh` fixture, reports no difference, and the output names how many fixtures it compared.
- `grep -n 'flow-view.sh' feature_flow/*.py` prints nothing (the package no longer shells out to it).
- `bash tests/run.sh` exits 0 and `git status --porcelain` is empty afterwards.

## Reference

- scripts/flow-view.sh (read only)
- tests/run.sh (the existing `flow-view.sh` checks)
- spec.md § Decisions (parity first)

## Answer
