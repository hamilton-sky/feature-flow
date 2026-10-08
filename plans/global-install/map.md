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
- 01 — `install --user` writes scripts, guides, agents, feature_flow and feature-flow.sha256 to `$FEATURE_FLOW_HOME` or `~/.feature-flow`, nothing into a repo; test_uninstall points `FEATURE_FLOW_HOME` outside the temp home until ticket 02.
- 02 — `uninstall --user` also walks `flow_home()` (shared with the installer), prunes bytecode there via `owned`, and removes the empty home folder.
- 03 — `prompts.build`/`plan` rewrite `python3 scripts/` in role and guide to the running scripts folder (absolute, quoted if it has a space) unless it is `cwd/scripts`.
- 04 — the home conductor runs from a repo and the code-hash tripwire already covers the home files (no code change); `Repo(local=False)` + `repo.script` for tests.
- 05 — both skills prefer the repo's `scripts/flow.py`, else `${FEATURE_FLOW_HOME:-$HOME/.feature-flow}/scripts/flow.py`; install-check lines also offer `install --user`.
