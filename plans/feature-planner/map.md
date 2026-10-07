# Map: feature-planner

## Destination

`/feature-flow` after a conversation shows a feature brief, waits for yes, has a fresh feature-planner subagent research and draft the plan in the state folder, has a fresh plan-reviewer check it, shows the plan, waits for a second yes, and only then writes `plans/<feature>/`. Works the same on Claude Code and Codex.

**The bar.** `bash tests/run.sh` passes, including the fixture drive of `plan-prompt`, `plan-review-prompt`, `plan-accept` and then `start`; and the hand run in ticket 08 turns a conversation into a plan that passes `python3 scripts/flow-status.py <feature> --check`. Ticket 08 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py feature-planner`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py feature-planner --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- The design and why a fresh planner was chosen over one in the user's session: `spec.md` § Decisions.

## Decisions so far

01 - feature-planner and plan-reviewer role files added; the installer picks them up unchanged.
02 - guides/brief.md (session), guides/plan.md (planner, draft folder) and guides/plan-review.md (reviewer) written; ticket rules unchanged apart from rule 12's wording.

## Open questions

- Should a Codex run without web search be refused, or plan from the codebase only? Assumed: plan from the codebase and say so.
