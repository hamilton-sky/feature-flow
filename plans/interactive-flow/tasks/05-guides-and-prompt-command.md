# Turn the protocols into guides and add the prompt command

Type: task
Status: open
Blocked by: 01, 04
Test first: yes

The builder and reviewer protocols live today in `skills/next-phase/SKILL.md` and `skills/review-ticket/SKILL.md`, and planning in `skills/plan-feature/` with its templates. Move that text into `guides/`, written for any agent: `guides/build.md`, `guides/review.md`, `guides/plan.md` with `guides/templates/` (copied from `skills/plan-feature/templates/`), and `guides/show.md`. Runtime-neutral means no `/` or `$` skill invocations, no `$ARGUMENTS`, no `CLAUDE.md`-only wording (say "the project's agent instructions file, CLAUDE.md or AGENTS.md"). Keep every rule; this is a copy, not a rewrite. Leave the old skills and their templates in place until they are deleted with the headless loop.

Add `bash scripts/flow.sh <feature> prompt`. It prints the complete prompt for the phase `next` last printed, in the shape ticket 01 found works: for BUILD, the builder role from `agents/ticket-builder.md` (body, no frontmatter), then `guides/build.md`, then the ticket path, number and feature filled in; for REVIEW, the reviewer role, `guides/review.md`, ticket, number and base sha. With no BUILD or REVIEW pending it exits 2. `start` is not here.

Find `guides/` and `agents/` next to the script first (`$(dirname "$0")/../guides`), then at `.feature-flow/guides` in the repo, so the installer can place them.

## Not in this ticket

- The skills that call `prompt`, and removing the old skills: later.
- Changing what the builder or reviewer must do.

## Done when

- `ls guides/build.md guides/review.md guides/plan.md guides/show.md guides/templates/ticket.md` lists all five.
- `grep -cE '\$ARGUMENTS|/next-phase|/review-ticket|\$next-phase' guides/*.md` prints `0` for each file.
- In a temp repo after `next` printed BUILD, `bash scripts/flow.sh f prompt` contains the builder role text, a line from `guides/build.md`, and `plans/f/tasks/01-a.md`, with no `<ticket>`, `<NN>`, `<sha>` or `<feature>` placeholder left; after REVIEW it contains the reviewer role and the base sha. With nothing pending it exits 2.
- `bash tests/run.sh` exits 0 with checks for the bullets above.

## Reference

- plans/interactive-flow/tasks/01-probe-claude-subagents.md (the prompt shape that works)
- skills/next-phase, skills/review-ticket, skills/plan-feature, skills/show-flow (read only, copy from)
- agents/*.md

## Answer
