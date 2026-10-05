---
name: run-flow
description: Use to run every remaining ticket of a planned feature unattended, one fresh agent session per ticket, until the feature is complete or stuck. Needs scripts/auto-flow.sh and scripts/flow-status.sh and a clean git tree.
argument-hint: "[feature]"
disable-model-invocation: true
---

Run the whole feature in `$ARGUMENTS` unattended.

If no feature was given, list `plans/*/` and ask which one.

## What the script does

`bash scripts/auto-flow.sh <feature>` repeats this until nothing is left:

1. Ask `flow-status.sh` for the next ready ticket.
2. Run the **smoke command** (the `Smoke:` line of `commands.md`, or `FLOW_SMOKE`). If the base is already broken, stop before spending a session.
3. Start a fresh agent session on the prompt `/next-phase <feature> auto`. It starts with clean context, and runs with the builder role: the `ticket-builder` agent when that agent is installed.
4. Read the ticket file. If it is now `resolved`, go on. If not, reset a stale claim and retry (2 attempts by default), then stop.
5. Stop if the working tree is dirty afterwards, because each ticket should end committed.
6. Run the **gate**: the `Build`, `Test` and `Lint` commands from `commands.md`. A script runs them, so "the tests pass" is checked, not claimed.
7. Run the **floor guard** on the ticket's diff. It fails the ticket if the work skipped or deleted tests, silenced checks, added empty catches, lowered thresholds, edited lint, test or CI config, or touched the plan beyond its own Status, Answer, and appended lines in `map.md` and `learnings.md`.
8. Start a second fresh session, `/review-ticket` (as the read only `ticket-reviewer` agent when installed), that sees only the ticket and the diff, re-runs every Done when and ends with `REVIEW: PASS` or `REVIEW: FAIL`.
9. If the gate, the guard or the reviewer objects, write their findings into the ticket as `## Review findings`, reopen it, and go back to step 3. After 3 rounds the run stops.
10. Log the cost of every session (needs `jq`) and stop if the run's total passes `FLOW_MAX_TOTAL_USD`.

The ticket file decides success, not the exit code of the session. It stops when every ticket is resolved, nothing is ready, or a limit is hit.

## Before running

1. `git status --porcelain` must be empty. If not, show it and stop.
2. `bash scripts/flow-status.sh <feature> --check` must print `OK`. If not, show the problems and stop.
3. `bash scripts/flow-status.sh <feature> --counts`. If every ticket is resolved, say so and stop.
4. Tell the user this will make commits and spend money, and that every ticket costs at least two sessions (one to build, one to review). Show what limits it: `FLOW_MAX_TOTAL_USD` (stop the run past this total), `FLOW_MAX_BUDGET_USD` and `FLOW_MAX_TURNS` (per session), `FLOW_MAX_RETRIES` (default 2), `FLOW_MAX_REVIEW_ROUNDS` (default 3), `FLOW_REVIEW=off` (skip the reviewer, keep the gate and the guard), `FLOW_GATE=off`, `FLOW_AGENTS=off`, `FLOW_REVIEW_MODEL` (review with a different or cheaper model), `FLOW_ALLOWED_TOOLS` (default allows Bash; narrow it, for example `Edit,Write,Read,Glob,Grep,Bash(git *),Bash(npm *)`). A default session starts with about 43k tokens of context before it does anything, while the installed agents start with 5k to 7k, so check that the agents are installed and keep the number of sessions down. Ask for a yes.

## Run it

Run the script with the Bash tool in the background so it is not cut off by the foreground time limit, then tell the user it is running and that you will report when it ends. Do not poll. For a long feature, suggest they run it in their own terminal instead.

## When it ends

- Always report the cost line the script prints (`cost this run: $X over N session(s)`), and where the per-session log is (`.git/flow-cost-<feature>.log`).
- Exit 0: run `--counts` and report how many tickets were resolved.
- Exit 1: run `bash scripts/flow-status.sh <feature>` and show the table. Say which ticket failed and suggest `/next-phase <feature>` to work it by hand.
