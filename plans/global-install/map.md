# Map: global-install

## Destination

`feature-flow install --user` installs the whole flow under `~/.feature-flow/` plus the skills and roles in `~/.claude` / `~/.agents`, so `/feature-flow` works in any git repo. A repo's own install still wins. `uninstall --user` removes it all. Version 0.4.0.

**The bar.** In a fresh git repo, after `HOME=<tmp> feature-flow install --user`, `python3 $HOME/.feature-flow/scripts/flow.py demo start` prints the same first line as the repo install's `python3 scripts/flow.py demo start`; `feature-flow uninstall --user` leaves the home folder without feature-flow files; `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 07 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py global-install`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to Decisions so far below.
- See the graph: `python3 scripts/flow-status.py global-install --mermaid`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.

## Decisions so far

- Plan — layout `~/.feature-flow/{scripts,guides,agents,feature_flow,feature-flow.sha256}`, override `FEATURE_FLOW_HOME`; see spec.md Decisions.
- Plan — the existing `uninstall --user` (already in the repo, 0.3.1) is extended, not rewritten; the brief assumed PR #37 would land first and it has.
- Plan — no outside sources were needed: everything is decided by this repo's code (`feature_flow/install.py`, `uninstall.py`, `codehash.py`, `prompts.py`, `scripts/flow.py`).

## Open questions

- none
