# Rewrite the README for the one-skill interactive flow

Type: task
Status: resolved
Blocked by: 10
Test first: no
Floor: allow config

Rewrite `README.md` around `/feature-flow` (Claude Code) and `$feature-flow` (Codex). Keep the voice and the parts that still hold (how a ticket flows, plans and tickets, the graph, caution). Replace the skills table with the one skill and its three uses (plan, drive, show). Replace "Running unattended" with "Long features and handoff": `FLOW_TICKETS_PER_SESSION`, the `HANDOFF` line, resuming after a closed session, relay mode, and that a Claude cloud session keeps working with nobody watching. State plainly that the script verifies build, gate and floor guard from the repo, while the review verdict is relayed by the session. Add a short "Upgrading" note: the five old skills and `/run-flow` are gone and what replaces each. Remove every mention of the headless loop, `claude -p`, `codex exec`, the cost log and the headless settings listed in ticket 10, apart from the Upgrading note. Do not hard-code the test count anywhere. If the `.github/workflows/tests.yml` job names or steps mention removed scripts, update them.

The "What is tested" table gets a row for Claude Code with the real numbers from the acceptance run and a row for Codex with what the Codex hand run recorded, or "Not yet tested with a real run" if it has not run.

## Not in this ticket

- Distribution changes (pinned fetch, PyPI): a later plan.

## Done when

- `grep -c 'feature-flow' README.md` is at least 5, and `grep -cE 'auto-flow|/run-flow|/next-phase|/review-ticket' README.md` prints a number only from the Upgrading note (at most 4).
- `grep -cE '[0-9]+ (checks|passed)' README.md` prints `0`.
- `grep -c 'HANDOFF' README.md` and `grep -c 'FLOW_TICKETS_PER_SESSION' README.md` are each at least 1, and `bash tests/run.sh` exits 0.

## Reference

- README.md, spec.md § Goal, Decisions, Risks
- plans/interactive-flow/tasks/12-acceptance-claude-run.md (the real numbers)

## Answer

`README.md` is rewritten around `/feature-flow` and `$feature-flow`:
- The quick start covers the one command and its three uses (plan, build, show), plus `auto`.
- The installer table includes `.feature-flow/`.
- "How a ticket flows" now uses subagents, with a paragraph saying what the conductor verifies
  from the repo (resolved ticket, clean committed tree, gate, floor guard, a reviewer that
  changed nothing) and that the review verdict is relayed by the session.
- "The skill and the roles" replaces the seven-skill table.
- "Long features and handoff" replaces "Running unattended". It covers `FLOW_TICKETS_PER_SESSION`,
  the `HANDOFF` line, owner tokens and `FLOW_TAKEOVER`, relay mode, and a cloud session working
  with nobody watching. A settings table lists only the variables still read.
- "What is tested" has a Claude Code row with ticket 12's real run (two sessions, one
  `HANDOFF`, all 16 acceptance checks ok, about 23k output tokens). The Codex row reads "not yet
  tested with a real run", because ticket 13 was skipped.
- "Upgrading" says what replaces each old skill and `/run-flow`.
- The cost and headless sections are gone, and no test count is written down.

The workflow's job names and steps name no removed script, so `.github/workflows/tests.yml` is unchanged.

Proof:
- `grep -c 'feature-flow' README.md` prints `24`.
- `grep -cE 'auto-flow|/run-flow|/next-phase|/review-ticket' README.md` prints `2`, both lines
  in the Upgrading note.
- `grep -cE '[0-9]+ (checks|passed)' README.md` prints `0`.
- `grep -c 'HANDOFF' README.md` prints `8`, and `grep -c 'FLOW_TICKETS_PER_SESSION' README.md` prints `2`.
- `bash tests/run.sh` exits 0.
