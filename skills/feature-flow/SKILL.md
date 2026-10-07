---
name: feature-flow
description: Use to plan a feature or build its tickets, one fresh builder and one fresh reviewer subagent per ticket, with scripts/flow.py deciding every step. Also draws the ticket graph with show.
argument-hint: "[feature] [show] [auto]"
disable-model-invocation: true
---

Plan or build the feature in `$ARGUMENTS`.

The first word is the **feature**. `show` means draw the graph. `auto` means ask nothing and go. If no feature was given, list `plans/*/` and ask which one.

The conductor is `python3 scripts/flow.py <feature> <command>`. It decides the order, runs the gate and the floor guard, and keeps its state in `.feature-flow/state/`, a folder git ignores. You ask it, and you do what it says. The guides it uses are in `guides/` or `.feature-flow/guides/`.

## Show

With `show`, follow `guides/show.md` for the feature and stop.

## Plan

If `plans/<feature>/` does not exist, run `FLOW_INVOKE=/feature-flow python3 scripts/flow.py <feature> start` and check that it prints `PLAN`. Then:

1. Follow `guides/plan.md` with the user.
2. Run `python3 scripts/flow-status.py <feature> --check` and fix every problem.
3. Stop. List the files you created and suggest the commit command (`git add plans/<feature> && git commit -m "docs(<feature>): plan"`). Say to commit the plan and run `/feature-flow <feature>` again. While the plan is uncommitted, do not say the feature is ready to build.

## Before building

With a plan present, check these before `start`, and stop at the first that fails:

- `git status --porcelain` is empty, apart from untracked files listed in `.feature-flow/installed.txt`: those are feature-flow's own install, so never stop for them. Suggest committing them (`git add --pathspec-from-file=.feature-flow/installed.txt && git commit -m "chore: install feature-flow"`) and carry on.
- `python3 scripts/flow-status.py <feature> --check` prints `OK`.
- `ticket-builder.md` and `ticket-reviewer.md` are in `.claude/agents/`, `~/.claude/agents/`, or `$CLAUDE_HOME/agents/` when `CLAUDE_HOME` is set. If not, say to run `uvx feature-flow-cli install .` in this repo (or `python3 install.py <repo>` from a feature-flow clone).

Then run `FLOW_INVOKE=/feature-flow python3 scripts/flow.py <feature> start`. It prints `OK <token>`. Keep the token and put `FLOW_SESSION=<token>` in front of **every** later conductor command, with `FLOW_INVOKE=/feature-flow`.

If `start` prints `STOP` naming another owner, another session may still be working this feature. Ask the user whether that session is closed. Only on a clear yes, run `start` once more with `FLOW_TAKEOVER=1`. In `auto` mode, never take over: report and stop.

Say what will happen: for each ticket, a builder subagent and then a reviewer subagent. After every few tickets (`FLOW_TICKETS_PER_SESSION`, default 4) you hand off to a new session. Ask for a yes, unless `auto` was given.

## The loop

Run `next`, act on its one line, and repeat:

- `BUILD <ticket> <NN> <sha>`: run `prompt`. Spawn a `ticket-builder` subagent with that output as its whole prompt, and ask for a short summary back. Wait for its final reply: an Agent call can return before the subagent finishes, and the reply then arrives as a notification. Then run `next`.
- `REVIEW <ticket> <NN> <sha>`: run `prompt` and spawn a `ticket-reviewer` subagent with it. Wait for its final reply. Save the whole reply with Bash, not the Write tool, into the conductor's git-ignored state folder: `cat > .feature-flow/state/flow-review-<feature>.txt <<'EOF'` ... `EOF`. Never under `.git`: an unattended session is refused there as a sensitive file. Then, as separate commands, run `verdict .feature-flow/state/flow-review-<feature>.txt` and `next`. If `verdict` prints `RETRY`, just run `next`.
- `DONE <summary>`: report it and suggest `/feature-flow <feature> show`.
- `STOP <reason>`: report the reason, run `python3 scripts/flow-status.py <feature>`, show the table, and stop.
- `HANDOFF <line>`: stop here. Tell the user to open a new session and type exactly `<line>`. The new session resumes where this one stopped.

A conductor command looks like this:

    FLOW_SESSION=<token> FLOW_INVOKE=/feature-flow python3 scripts/flow.py <feature> next

## Rules while building

These apply from `start` on, once a plan exists. Planning (above) writes the plan files itself.

- Never run the gate, the floor guard or a review yourself. The conductor runs the checks, and the reviewer subagent reviews.
- Never edit a ticket, the plan or the code, and never commit. The builder does that.
- Never skip a step, reorder steps, or decide the next step yourself. Only `next` decides.
- Never read a ticket's `## Answer` into the reviewer's prompt. `prompt` already holds everything it needs.
- Tell the user one short line per phase (`01 built`, `01 review: PASS`), not the subagents' reports.
