# Port the floor guard to Python

Type: convert
Status: open
Blocked by: 01
Test first: yes

Port `scripts/floor-guard.sh` to `feature_flow/floorguard.py`, with a shim `scripts/floor-guard.py` that calls it. Read the bash script and its tests in `tests/run.sh` first. Same arguments, same environment variables, same stdout and stderr text, same exit codes; standard library only, at the Python floor recorded in ticket 01. Do not fix bugs you find: keep the behaviour, note the bug under Shortcuts taken, and leave the fix to a new ticket. This is the riskiest port: the awk patterns become Python regexes. Keep every category (skip, suppress, empty-catch, test-delete, threshold, config, ticket-edit, commands-edit), the `Floor: allow` line read from the ticket at the base commit, and the plan-protection rules. Add fixtures for each category if `tests/run.sh` lacks one.

Add a parity test to `tests/run.sh`: for every fixture the existing `floor-guard.sh` checks use, run `bash scripts/floor-guard.sh` and `python3 scripts/floor-guard.py` with the same arguments and require identical stdout and exit code. Then change `feature_flow` to import the module where it shelled out to the bash script. Leave `scripts/floor-guard.sh` in place; it is deleted when every port is done.

## Not in this ticket

- Deleting `scripts/floor-guard.sh` or changing who calls it besides `feature_flow`: the switch-over ticket.
- Behaviour changes of any kind.

## Done when

- `python3 scripts/floor-guard.py` exists and `python3 -m unittest discover -s tests/py` passes with unit tests for `feature_flow/floorguard.py`.
- The parity section in `bash tests/run.sh` compares both versions on every existing `floor-guard.sh` fixture, reports no difference, and the output names how many fixtures it compared.
- `grep -n 'floor-guard.sh' feature_flow/*.py` prints nothing (the package no longer shells out to it).
- `bash tests/run.sh` exits 0 and `git status --porcelain` is empty afterwards.

## Reference

- scripts/floor-guard.sh (read only)
- tests/run.sh (the existing `floor-guard.sh` checks)
- spec.md § Decisions (parity first)

## Answer
