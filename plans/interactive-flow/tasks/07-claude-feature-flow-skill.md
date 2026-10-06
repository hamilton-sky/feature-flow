# Add the feature-flow skill for Claude Code

Type: task
Status: resolved
Blocked by: 05, 06
Test first: no

Add `skills/feature-flow/SKILL.md`, the one skill a Claude Code user types: `/feature-flow <feature> [show] [auto]`. Frontmatter: `name: feature-flow`, a `description`, `argument-hint: "[feature] [show] [auto]"`, `disable-model-invocation: true`. Keep it short; the guides hold the detail.

What it says, in order:

1. Take the feature from `$ARGUMENTS`; if none, list `plans/*/` and ask. With `show`, follow `guides/show.md` and stop.
2. If the plan folder is absent, run `FLOW_INVOKE=/feature-flow python3 scripts/flow.py <feature> start` and require `PLAN`. Follow `guides/plan.md` with the user, run `flow-status.sh <feature> --check`, then stop with the created files and a suggested plan commit command. Say to commit the plan and run the skill again; do not claim it is ready while the tree is dirty.
3. With a plan present, before `start`: require a clean tree, `flow-status.sh <feature> --check` printing `OK`, and `ticket-builder` and `ticket-reviewer` installed (`.claude/agents/` or `~/.claude/agents/`), else stop and say to run `bash install.sh`. Then run `start`, keep the token from `OK <token>` and pass it as `FLOW_SESSION=<token>` to every later conductor command. If `start` reports another owner, ask before retrying once with `FLOW_TAKEOVER=1`; never take over in `auto` mode. Say what will happen (two subagents per ticket, a handoff every `FLOW_TICKETS_PER_SESSION` tickets) and ask for a yes, unless `auto` was given.
4. The loop: `next`, act on that line only. `BUILD`: run `prompt` and spawn a `ticket-builder` subagent with its output, asking for a short summary back. `REVIEW`: run `prompt`, spawn `ticket-reviewer`, save its whole reply as the probe found works, run `verdict`, then `next`. Every conductor call carries the same `FLOW_SESSION`. `DONE`: report and suggest `/feature-flow <feature> show`. `STOP`: report the reason and show `flow-status.sh <feature>`. `HANDOFF`: stop and give the user the exact line to type in a new session.
5. Rules: never run the gate, floor guard or a review yourself, never edit a ticket or commit, never skip or reorder, one short line per phase to the user.

## Not in this ticket

- The Codex skill and the installer: later tickets.
- Removing the old skills.

## Done when

- `sed -n 1,6p skills/feature-flow/SKILL.md` shows `name: feature-flow`, an `argument-hint:` line and `disable-model-invocation: true`.
- `for a in PLAN BUILD REVIEW DONE STOP HANDOFF; do grep -c "$a" skills/feature-flow/SKILL.md; done` prints six numbers each at least 1, and `grep -cE 'bash scripts/(gate|floor-guard)\.sh' skills/feature-flow/SKILL.md` prints `0`.
- `grep -c 'prompt' skills/feature-flow/SKILL.md` is at least 1, and the skill holds no copy of the builder or reviewer protocol: `grep -c 'Done when' skills/feature-flow/SKILL.md` is at most 2.
- `wc -l < skills/feature-flow/SKILL.md` is under 90, and `bash tests/run.sh` exits 0.

## Reference

- spec.md § Happy path, Interfaces
- skills/run-flow/SKILL.md (voice and structure)
- guides/ and scripts/flow.py

## Answer

Built: `skills/feature-flow/SKILL.md`, which is 60 lines long and organized as Show, Plan, Before building, The loop and Rules. It calls `scripts/flow.py` for every step with `FLOW_INVOKE=/feature-flow`, and passes `FLOW_SESSION=<token>` from `start` on every later call. On BUILD it spawns `ticket-builder` with the `prompt` output. On REVIEW it spawns `ticket-reviewer`, waits for the final reply (an Agent call can return before the subagent finishes), saves the reply with Bash to `.git/flow-review-<feature>.txt`, then runs `verdict`. It never runs the gate, the guard or a review itself, and it takes over only on the user's clear yes, never in `auto` mode.

Proven:
- `sed -n 1,6p` shows `name: feature-flow`, `argument-hint:` and `disable-model-invocation: true`.
- The six status words count `1 1 1 1 2 1`.
- The gate/floor-guard grep prints `0`, `prompt` occurs 3 times, and `Done when` occurs 0 times.
- `wc -l` is 60.
- `bash tests/run.sh` exits 0 at ticket 09's commit, with a `feature-flow skills` section covering these bullets. That suite can't be green before 09, because the old installer copies every folder under `skills/`, the new one included, and its counts and Codex rewrite checks move with it.

Decisions:
- The skill runs `start` for the PLAN check only when `plans/<feature>/` is missing, because `start` on an existing plan would create an owner before the pre-checks.
- The prompt is not pasted into the skill. `prompt` pastes the role and guide, so the skill stays short.

Shortcuts taken: none.

For later tickets: ticket 12's real run will be the first time this skill drives Claude Code. Watch whether the session waits for the reviewer's notification before `verdict`. If it doesn't, `verdict` records "no verdict" and the review is handed out again.
