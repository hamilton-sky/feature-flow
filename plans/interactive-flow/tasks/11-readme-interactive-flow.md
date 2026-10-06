# Rewrite the README for the one-skill interactive flow

Type: task
Status: open
Blocked by: 10
Test first: no
Floor: allow config

Rewrite `README.md` around `/feature-flow` (Claude Code) and `$feature-flow` (Codex). Keep the voice and the parts that still hold (how a ticket flows, plans and tickets, the graph, caution). Replace the skills table with the one skill and its three uses (plan, drive, show). Replace "Running unattended" with "Long features and handoff": `FLOW_TICKETS_PER_SESSION`, the `HANDOFF` line, resuming after a closed session, relay mode, and that a Claude cloud session keeps working with nobody watching. State plainly that the script verifies build, gate and floor guard from the repo, while the review verdict is relayed by the session. Add a short "Upgrading" note: the five old skills and `/run-flow` are gone and what replaces each. Do not hard-code the test count anywhere. If the `.github/workflows/tests.yml` job names or steps mention removed scripts, update them.

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
