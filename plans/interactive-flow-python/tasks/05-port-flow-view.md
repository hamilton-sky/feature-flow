# Port the graph page generator to Python

Type: convert
Status: resolved
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

Built: `feature_flow/view.py` ports `scripts/flow-view.sh` as it is on main after interactive-flow ticket 10: the same arguments (`--watch`, `--no-open`, `--out FILE`), environment variables (`FLOW_DIR`, `FLOW_TICKETS`, `FLOW_NO_OPEN`, `FLOW_WATCH_SECONDS`, `TMPDIR`), messages and exit codes, and the page is still `scripts/flow-view.html` with the data put in. The template and the data are handled as bytes. The core data comes from `status.run(... --json)` in process, and the watch loop's completion check is `status.run(... --next)`, so neither starts bash. The history still comes from `git log` and `git show` through `subprocess`. `scripts/flow-view.py` is a shim shaped like `scripts/flow.py`. Nothing in `feature_flow` called `flow-view.sh` before, so no caller had to be switched. `scripts/flow-view.sh` is untouched. Standard library only: `os`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `time`, all already on the allowlist.

Dropped because ticket 10 removed it: the cost log. The script on main no longer reads `.git/flow-cost-<feature>.log` and has no `ticket_cost` or per-ticket `"cost"` field. The port has none of them either, and a unit test checks that the details carry no `cost` key.

Proof: the "flow-view.py, parity with flow-view.sh" section of `bash tests/run.sh` runs `bash scripts/flow-view.sh` and `python3 scripts/flow-view.py` with the same arguments and environment. It compares stdout, stderr, the exit code and the written page, after blanking the page's `"generated"` clock stamp, which is the only part allowed to differ. The runs use a clone of the view repo, checked out at each state the flow-view.sh checks saw. They cover every fixture those checks use: `--out`, the default `.git` location, a missing feature, an unknown option, no feature, outside git into `TMPDIR`, watching a finished feature and a live watch (both versions run at once, then stopped). There are also edge cases: `--out` without a value or empty, a relative `--out` in a new folder, repeated options, `FLOW_DIR` and `FLOW_TICKETS`, a 0 byte ticket, an empty ticket folder (the status reader fails), a missing template, and an ASCII plan with capitalised headings, more than 8 Done when bullets, a 300 character bullet, a 900 character Answer, quotes, backslashes and tabs, review rounds with and without a number or source, the Answer placeholder, a CRLF Status line and a two commit history. Result: "compared flow-view.sh and flow-view.py on 22 fixture runs", no difference. Breaking the 240 character cut in the port made the section fail, so it does catch a change. The live watch polls for both pages instead of sleeping a fixed time, so the section adds a few seconds at most. `tests/py/test_view.py` has 23 unit tests. `python3 -m unittest discover -s tests/py`: 81 tests OK. `bash tests/run.sh`: 365 passed, 0 failed, tree clean.

Shortcuts taken:
- `grep -n 'flow-view.sh' feature_flow/*.py` prints one line: the usage text in `view.py`, which must read `usage: bash scripts/flow-view.sh ...` for stderr parity. Ticket 07 switches it. The package does not shell out to the script.
- Bash bugs kept: the `mktemp` file is left behind when the status reader fails (for example an empty ticket folder); `--out` naming an existing folder moves the page into it as `<folder>/<name>.tmp` while it prints `wrote <folder>`; a ticket's label (its file name up to the first `-`) goes into the JSON unescaped, and two tickets with the same label give duplicate keys; history reads the ticket through `git show <sha>:./<path>`, so an absolute `FLOW_DIR` gives no history; a CRLF Status line reads as `open` in the history; a `\001` byte in ticket text comes out as `\n`; the page's auto refresh is always 3 seconds, whatever `FLOW_WATCH_SECONDS` says. Each wants its own ticket after the switch-over.
- Where the awks disagree, the port picks one behaviour and `tests/py/test_view.py` pins it, while the parity fixtures stay ASCII. The 240 and 700 character cuts count characters, as gawk in a UTF-8 locale does, so a cut never splits a character (mawk counts bytes). A line made only of spaces, tabs, `\r`, `\v` or `\f` counts as blank in the Answer, as in mawk (gawk and BSD awk count `\r` as text). `tolower` is ASCII only.
- Platform details not reproduced: the ticket glob is sorted by code point, not by locale collation (the same for ASCII names); a bad `FLOW_WATCH_SECONDS` prints GNU sleep's message with straight quotes (BSD sleep and a UTF-8 GNU locale word it differently); filesystem errors (an unwritable `--out`) print `flow-view: <error>` and exit 1, where bash printed the mkdir, awk or mv message; Ctrl-C in `--watch` exits 130 instead of dying of the signal (the `signal` module is not on the allowlist); `open` and `xdg-open` are looked up on `PATH` only.
