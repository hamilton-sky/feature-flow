# Map: in-session-mode

## Destination

A Claude Code user can type `/drive-flow <feature>` and have the whole planned feature built in that one session. A script, `scripts/flow-step.sh`, owns the order of phases and the limits and tells the session what to do next. The session spawns a `ticket-builder` subagent to build and a `ticket-reviewer` subagent to review, and the script runs the gate and the floor guard itself. The skill is installed for Claude Code and left out for Codex, and the README says what is and is not tested.

**The bar.** `RUN_REAL=1 bash tests/smoke-real.sh --drive` runs `claude -p "/drive-flow hello auto"` on the demo project and ends with both tickets resolved, a clean tree, the gate and the floor guard run after each ticket and a reviewer subagent's `REVIEW: PASS` for each: a list of `ok` checks, no `FAIL`, exit 0. The last ticket runs it.

## How to work this

- See what is ready: `bash scripts/flow-status.sh in-session-mode`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `bash scripts/flow-status.sh in-session-mode --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Ticket 01 and the paid run in the last ticket cannot be done by the unattended loop (its builder has no Agent tool and must not spend money twice). Work them by hand with `/next-phase`. Both tell an unattended builder to stop at once, so a `/run-flow` that reaches them ends there instead of spending anything.
- Order: 01, 02, 03 in a line; 05 can go at any time but must land before 04 (the exclusion must exist before the skill, or the Codex install checks fail); then 06 and 07.

## Decisions so far

<One line per resolved ticket.>

## Open questions

- Whether `--allowedTools` must name the subagent tool `Agent` or `Task` in a headless run. Ticket 07 finds out.
- What exactly a subagent can do (read a skill file, return a verdict, stay independent) is settled by the first ticket and may change the conductor's protocol.
- Whether Codex can spawn agents from a session. That is a probe and a plan of its own, not part of this one.
