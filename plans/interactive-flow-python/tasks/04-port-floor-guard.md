# Port the floor guard to Python

Type: convert
Status: resolved
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

`feature_flow/floorguard.py` is the port (stdlib only, 3.9 syntax, git through `subprocess`), `scripts/floor-guard.py` is a shim shaped like `scripts/flow.py`, and `floor_guard()` in `feature_flow/checks.py` now calls `floorguard.run()` in-process (same signature, same `Result`: exit code and stdout plus stderr in the order written). `grep -n 'floor-guard.sh' feature_flow/*.py` prints only the usage line (see Shortcuts taken); nothing shells out to it. `scripts/floor-guard.sh` is untouched.

The diff is handled as bytes, like mawk (the awk on Ubuntu and in this container): bytes regexes, `substr(text, 1, 100)` cuts at 100 bytes, `tolower` is ASCII only, and the escapes `awk -v allow=...` interprets (`\t`, `\\`, octal, `\x`) are applied as mawk does. Text is decoded with `surrogateescape`, so the shim writes back exactly the bytes git gave.

Parity: `tests/run.sh` now runs every existing floor-guard call (the guard repo cases and all 14 `tamper` cases) through `guard_both`, which runs `bash scripts/floor-guard.sh` and `python3 scripts/floor-guard.py` with the same arguments and compares stdout, stderr and exit code. Nine parity-only fixtures cover what the old checks did not reach: JS, Rust and Go skips and suppressions, both `catch {}` forms, a `--cov-fail-under` threshold, a workflow config file, a line cut inside a two byte character, `Floor:` without `allow`, the default and the empty base, a bad base (git's exit 128), missing arguments, and `FLOW_DIR` / `FLOW_TICKETS`. Result: `compared floor-guard.sh and floor-guard.py on 28 fixtures`, no difference. `bash tests/run.sh`: 512 passed, 0 failed. `python3 -m unittest discover -s tests/py`: 36 tests OK, 22 of them new in `tests/py/test_floorguard.py`.

Shortcuts taken:
- Bugs kept from the bash version: a `Floor:` line without `allow` still allows its words (`Floor: skip` allows skip); an added line starting `++ ` shows as `+++ ` in the diff and is read as a file header; a removed map.md or learnings.md line starting `--` is skipped as a `---` header; the assertion count also counts `--- a/...` and `+++ b/...` header lines whose path contains `assert`. Each wants its own ticket after the switch-over.
- The usage line still says `usage: bash scripts/floor-guard.sh ...` for parity, so the Done-when grep prints that one line. The switch-over ticket (07) changes it to `.py`.
- Platform details not reproduced: bash's glob order follows the locale collation, the port sorts by code point (the same for ASCII names); bash drops NUL bytes from `$(...)`; GNU grep's `.` may not match invalid UTF-8 in a UTF-8 locale; gawk (character based `substr`, unicode `tolower`) would differ from mawk on non-ASCII lines, and the port follows mawk.
- In-process, `checks.floor_guard` decodes undecodable bytes with replacement characters, where the old subprocess call would have raised on them.
- On CI the gawk job showed that mawk and gawk disagree on a finding line with non-ASCII text before the 100th byte (mawk cuts bytes, gawk characters), so no parity fixture can hold such a line. The parity fixtures are ASCII; `test_text_is_cut_at_100_bytes` pins the port's mawk behaviour, which can cut inside a character. A later ticket should cut at a character boundary.
