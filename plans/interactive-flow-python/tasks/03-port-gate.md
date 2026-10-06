# Port the gate to Python

Type: convert
Status: open
Blocked by: 01
Test first: yes

Port `scripts/gate.sh` to `feature_flow/gate.py`, with a shim `scripts/gate.py` that calls it. Read the bash script and its tests in `tests/run.sh` first. Same arguments, same environment variables, same stdout and stderr text, same exit codes; standard library only, at the Python floor recorded in ticket 01. Do not fix bugs you find: keep the behaviour, note the bug under Shortcuts taken, and leave the fix to a new ticket. Commands from `commands.md` are still run through the platform shell exactly as the bash gate runs them (they are the user's own command lines), and `FLOW_GATE` is honoured.

Add a parity test to `tests/run.sh`: for every fixture the existing `gate.sh` checks use, run `bash scripts/gate.sh` and `python3 scripts/gate.py` with the same arguments and require identical stdout and exit code. Then change `feature_flow` to import the module where it shelled out to the bash script. Leave `scripts/gate.sh` in place; it is deleted when every port is done.

## Not in this ticket

- Deleting `scripts/gate.sh` or changing who calls it besides `feature_flow`: the switch-over ticket.
- Behaviour changes of any kind.

## Done when

- `python3 scripts/gate.py` exists and `python3 -m unittest discover -s tests/py` passes with unit tests for `feature_flow/gate.py`.
- The parity section in `bash tests/run.sh` compares both versions on every existing `gate.sh` fixture, reports no difference, and the output names how many fixtures it compared.
- `grep -n 'gate.sh' feature_flow/*.py` prints nothing (the package no longer shells out to it).
- `bash tests/run.sh` exits 0 and `git status --porcelain` is empty afterwards.

## Reference

- scripts/gate.sh (read only)
- tests/run.sh (the existing `gate.sh` checks)
- spec.md § Decisions (parity first)

## Answer
