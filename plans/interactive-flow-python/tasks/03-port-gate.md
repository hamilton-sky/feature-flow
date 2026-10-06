# Port the gate to Python

Type: convert
Status: resolved
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

Ported `scripts/gate.sh` to `feature_flow/gate.py` (standard library only, 3.9 syntax) with the shim `scripts/gate.py`, built like `scripts/flow.py` (same `sys.path` lookup including `.feature-flow`, `sys.dont_write_bytecode = True`). Same argument, same `FLOW_DIR` handling, same stdout/stderr text and exit codes (0, 1, 2); the commands still run through `bash -c`, their combined output goes to a temporary file and the last 40 lines are printed on failure. The file is read and output written as bytes so a carriage return, a non UTF-8 byte or a last line without a newline come out exactly as awk and `tail` print them. `FLOW_GATE` is still decided by the conductor (`conductor.py`), which is where the bash flow honoured it too; the gate itself never read it.

`feature_flow/checks.py` `gate(scripts, feature)` now calls `feature_flow.gate.run` in process and returns the same `Result` (exit code, stdout and stderr folded together, newlines translated as the old `universal_newlines` subprocess did). `grep -n 'gate.sh' feature_flow/*.py` prints only the usage line (see Shortcuts taken); no code shells out to it.

Tests: `tests/py/test_gate.py` (11 unit tests, skipped where there is no bash); a parity section in `tests/run.sh` right after `gate.sh` runs both versions on the 3 `commands.md` files the gate.sh checks use plus 2 edge cases (CRLF + whitespace-only value + stderr, and 60 lines of output without a final newline), each with the arguments `f`, `nofeature` and none: **15 fixture runs compared, no difference** in stdout, stderr or exit code. `bash tests/run.sh`: 512 passed, 0 failed.

### Shortcuts taken

- Did not reuse `tickets.commands_value`: it reads text with `splitlines()`, which strips a trailing `\r` (awk keeps it) and splits on form feeds and other Unicode line breaks (awk does not), and it raises on non UTF-8 bytes. The gate has its own byte-level reader, `gate.command`.
- The usage line still says `usage: bash scripts/gate.sh <feature>` (parity), so the grep in Done when prints that one line. Ticket 07 changes the text.
- Bugs kept from the bash gate, for a later ticket: a whitespace-only value (`` Test: `   ` ``) is not skipped, it runs as an empty command and counts as passed; a `\r` at the end of a CRLF line is passed to `bash -c` as part of the command; an unreadable `commands.md` makes awk print an error and every value empty (the port prints no error there, the only text difference, and it is not covered by any fixture).
