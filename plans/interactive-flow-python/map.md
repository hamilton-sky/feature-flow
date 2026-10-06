# Map: interactive-flow-python

## Destination

All of feature-flow runs as Python in the `feature_flow` package (standard library, 3.9+), with the same commands and output as the bash scripts it replaces, on Linux, macOS and Windows. This is round two of `plans/interactive-flow`, which wrote the conductor in Python and removed the headless loop.

**The bar.** CI green on Ubuntu, macOS and Windows: `python3 -m unittest discover -s tests/py` passes and a fixture plan driven with `python scripts/flow.py` reaches `REVIEW` on all three, and `ls scripts/*.sh` lists nothing. Ticket 08 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py interactive-flow-python`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py interactive-flow-python --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Start only after `plans/interactive-flow` ticket 03 (the Python conductor) is resolved; ticket 01 checks that. Tickets 05 and 06 also wait for interactive-flow ticket 10.

## Decisions so far

01 - prerequisites met (conductor on main); runners have Python 3.12 to 3.14 and Windows has git; the floor stays 3.9.
02 - flow-status ported to feature_flow/status.py, ticket parsing in tickets.Graph; the conductor calls it in process.
03 - gate ported to feature_flow/gate.py (byte-level, bash -c kept); checks.gate runs it in process; parity 15/15 in tests/run.sh
04 - floor guard ported to feature_flow/floorguard.py (bytes, mawk semantics), conductor calls it in-process; parity on 28 fixtures, bash bugs kept and listed in the ticket.
05 - flow-view ported to feature_flow/view.py (template and data as bytes, status read in process); parity on 22 fixture runs; the cost log was already gone with interactive-flow ticket 10; bash bugs kept and listed in the ticket.
06 - installer ported to feature_flow/install.py (root shim install.py), install.sh is a 4-line exec wrapper; parity 17/17 scenarios against tests/install-bash-reference.sh, deleted in 07.
07 - every caller (guides, both skills, README, demo, smoke-real, conductor messages, usage lines) switched to `python3 scripts/<name>.py`; the four bash scripts, the installer reference and every parity section deleted; the remaining tests/run.sh checks run the Python commands; the installer ships the `.py` shims and no `.sh`.

## Open questions

- Which Python versions the cloud environments ship (ticket 01). If one is older than 3.9, the floor moves down or the README names the requirement.
