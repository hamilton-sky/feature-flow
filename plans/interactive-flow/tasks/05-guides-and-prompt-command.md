# Turn the protocols into guides and add the prompt command

Type: task
Status: resolved
Blocked by: 01, 04
Test first: yes

The builder and reviewer protocols live today in `skills/next-phase/SKILL.md` and `skills/review-ticket/SKILL.md`, and planning in `skills/plan-feature/` with its templates. Move that text into `guides/`, written for any agent: `guides/build.md`, `guides/review.md`, `guides/plan.md` with `guides/templates/` (copied from `skills/plan-feature/templates/`), and `guides/show.md`. Runtime-neutral means no `/` or `$` skill invocations, no `$ARGUMENTS`, no `CLAUDE.md`-only wording (say "the project's agent instructions file, CLAUDE.md or AGENTS.md"). Keep every rule; this is a copy, not a rewrite. Leave the old skills and their templates in place until they are deleted with the headless loop.

Add `python3 scripts/flow.py <feature> prompt`. It prints the complete prompt for the phase `next` last printed, in the shape ticket 01 found works: for BUILD, the builder role from `agents/ticket-builder.md` (body, no frontmatter), then `guides/build.md`, then the ticket path, number and feature filled in; for REVIEW, the reviewer role, `guides/review.md`, ticket, number and base sha. With no BUILD or REVIEW pending it exits 2. `start` is not here.

Find `guides/` and `agents/` next to the script first (`$(dirname "$0")/../guides`), then at `.feature-flow/guides` in the repo, so the installer can place them.

## Not in this ticket

- The skills that call `prompt`, and removing the old skills: later.
- Changing what the builder or reviewer must do.

## Done when

- `ls guides/build.md guides/review.md guides/plan.md guides/show.md guides/templates/ticket.md` lists all five.
- `grep -cE '\$ARGUMENTS|/next-phase|/review-ticket|\$next-phase' guides/*.md` prints `0` for each file.
- In a temp repo after `next` printed BUILD, `python3 scripts/flow.py f prompt` contains the builder role text, a line from `guides/build.md`, and `plans/f/tasks/01-a.md`, with no `<ticket>`, `<NN>`, `<sha>` or `<feature>` placeholder left; after REVIEW it contains the reviewer role and the base sha. With nothing pending it exits 2.
- `bash tests/run.sh` exits 0 with checks for the bullets above.

## Reference

- plans/interactive-flow/tasks/01-probe-claude-subagents.md (the prompt shape that works)
- skills/next-phase, skills/review-ticket, skills/plan-feature, skills/show-flow (read only, copy from)
- agents/*.md

## Answer

Built: `guides/build.md`, `guides/review.md`, `guides/plan.md` and `guides/show.md`, copied from the `next-phase`, `review-ticket` (with the three probe fixes from ticket 01), `plan-feature` and `show-flow` skills. `guides/templates/` is copied from `skills/plan-feature/templates/`. Each guide drops its frontmatter and gets a heading. Every rule is kept. Only runtime wording changed:
- `$ARGUMENTS` is now "you are given ...".
- The `claude -p "/review-ticket ..."` commands are now "hand it to a fresh reviewer (a subagent, or a new session) with the ticket-reviewer role and the review guide".
- `CLAUDE.md` is now "the project's agent instructions file, CLAUDE.md or AGENTS.md".
- The `/next-phase` and `auto-flow.sh` "what next" lines now point at the feature-flow skill.
- "The unattended loop" is now "the flow" (also in `guides/templates/commands.md`).

The old skills are untouched. I also added `python3 scripts/flow.py <feature> prompt` (`feature_flow/prompts.py`, `Conductor.prompt`).

Proven: `bash tests/run.sh` 522 passed, 0 failed, with a `flow.py, guides and prompt` section covering each bullet. All five `ls` paths exist. The grep prints 0 for each guide. The build prompt contains the builder role, a guide line and `plans/f/tasks/01-a.md`, with no `<ticket>`, `<NN>`, `<sha>` or `<feature>` left. The review prompt contains the reviewer role and the base sha. `prompt` exits 2 before the first `next` and after DONE. `git status --porcelain` was empty afterwards.

Decisions: the prompt pastes the role and the guide rather than naming files. Ticket 01 found both work and naming is cheaper. Pasting needs no path that a subagent might resolve differently (`guides/` beside `scripts/`, or `.feature-flow/guides/`), and it is what this ticket's Done when checks. If cost matters later, switching to a file-named prompt is a change inside `prompts.build`. The guide's generic placeholders `<feature>`, `<NN>`, `<base>`, `<base-commit>` and `<start-commit>` are filled with the real values.

Shortcuts taken: none.

For later tickets:
- Prompt layout: role body, `---`, one line saying the guide is the skill the role names, the guide, `---`, then the task. The task gives the ticket path, number, base sha and the `auto` arguments, and tells the agent to run `git log`/`git status` itself (ticket 01's stale-snapshot finding). The review task ends with "Your final reply must end with exactly `REVIEW: PASS` or `REVIEW: FAIL`", which is ticket 02's wording.
- `prompt` honours `FLOW_SESSION` like `next` and `verdict`. It exits 2 when no BUILD or REVIEW is pending, and STOPs when `agents/` or `guides/` can't be found.
- The skills (07, 08) must still tell the session three things: an Agent call returns before the reply (wait for the notification, or `wait_agent` in Codex), save the reply with Bash to `.git/flow-review-<feature>.txt`, then run `verdict` on that file.
- Ticket 09 must install `guides/` and `agents/` (or the role files) into `.feature-flow/`, along with `feature_flow/`.
