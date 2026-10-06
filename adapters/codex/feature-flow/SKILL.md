---
name: feature-flow
description: "Use to plan a feature or build its tickets, one fresh builder and one fresh reviewer subagent per ticket, with scripts/flow.py deciding every step. Also draws the ticket graph with show."
---

`<arguments>` below stands for the text the user typed after `$feature-flow`.

Plan or build the feature in `<arguments>`.

The first word is the **feature**. `show` means draw the graph. `auto` means ask nothing and go. If no feature was given, list `plans/*/` and ask which one.

The conductor is `python3 scripts/flow.py <feature> <command>`. It decides the order, runs the gate and the floor guard, and keeps its state under `.git`. You ask it, and you do what it says. The guides it uses are in `.feature-flow/guides/` (in a feature-flow checkout, `guides/`). Read the project's `AGENTS.md` for its conventions.

## Show

With `show`, follow `.feature-flow/guides/show.md` for the feature and stop.

## Plan

If `plans/<feature>/` does not exist, run `FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> start` and check that it prints `PLAN`. Then:

1. Follow `.feature-flow/guides/plan.md` with the user.
2. Run `bash scripts/flow-status.sh <feature> --check` and fix every problem.
3. Stop. List the files you created and suggest the commit command (`git add plans/<feature> && git commit -m "docs(<feature>): plan"`). Say to commit the plan and run `$feature-flow <feature>` again. While the plan is uncommitted, do not say the feature is ready to build.

## Before building

With a plan present, check these before `start`, and stop at the first that fails:

- `git status --porcelain` is empty.
- `bash scripts/flow-status.sh <feature> --check` prints `OK`.
- `.agents/flow-roles/ticket-builder.md` and `.agents/flow-roles/ticket-reviewer.md` exist. If not, say to run `bash install.sh --agent codex` from feature-flow.

Then run `FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> start`. It prints `OK <token>`. Keep the token and put `FLOW_SESSION=<token>` in front of **every** later conductor command, with `FLOW_INVOKE='$feature-flow'`. The conductor writes its state under `.git`; if the sandbox refuses that, stop and tell the user this session needs to be allowed to write `.git`.

If `start` prints `STOP` naming another owner, another session may still be working this feature. Ask the user whether that session is closed. Only on a clear yes, run `start` once more with `FLOW_TAKEOVER=1`. In `auto` mode, never take over: report and stop.

Say what will happen: for each ticket, a builder subagent and then a reviewer subagent. After every few tickets (`FLOW_TICKETS_PER_SESSION`, default 4) you hand off to a new session. Ask for a yes, unless `auto` was given.

## The loop

Run `next`, act on its one line, and repeat:

- `BUILD <ticket> <NN> <sha>`: run `prompt`. Start the builder with `spawn_agent(task_name="ticket_builder", fork_turns="none", message=...)`. The message is "Work only in <repo>." followed by the whole `prompt` output, which already starts with the builder role. Get its final reply with `wait_agent`, then run `next`.
- `REVIEW <ticket> <NN> <sha>`: run `prompt`. Start a new reviewer the same way, with `task_name="ticket_reviewer"` and `fork_turns="none"` so it never sees the builder's context. Get its final reply with `wait_agent`. A child cannot be made read-only, so the reviewer works from its instructions; the conductor catches any edit it makes. Save the whole reply with the shell: `cat > .git/flow-review-<feature>.txt <<'EOF'` ... `EOF`. Then run `verdict .git/flow-review-<feature>.txt` and `next`. If `verdict` prints `RETRY`, just run `next`.
- `DONE <summary>`: report it and suggest `$feature-flow <feature> show`.
- `STOP <reason>`: report the reason, run `bash scripts/flow-status.sh <feature>`, show the table, and stop.
- `HANDOFF <line>`: stop here. Tell the user to open a new session and type exactly `<line>`. The new session resumes where this one stopped.

A conductor command looks like this:

    FLOW_SESSION=<token> FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> next

If the user wants a reviewer that cannot write at all, run the review as a fresh read-only Codex session instead of a subagent, then run `verdict` on its reply as above:

    FLOW_SESSION=<token> FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> prompt | codex exec --sandbox read-only -o .git/flow-review-<feature>.txt -

## Rules

- Never run the gate, the floor guard or a review yourself. The conductor runs the checks, and the reviewer subagent reviews.
- Never edit a ticket, the plan or the code, and never commit. The builder does that.
- Never skip a step, reorder steps, or decide the next step yourself. Only `next` decides.
- Never read a ticket's `## Answer` into the reviewer's prompt. `prompt` already holds everything it needs.
- Tell the user one short line per phase (`01 built`, `01 review: PASS`), not the subagents' reports.
