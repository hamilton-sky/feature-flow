---
name: feature-flow
description: "Use to plan a feature (from the conversation so far, with a fresh planner and plan reviewer subagent) or build its tickets, one fresh builder and one fresh reviewer subagent per ticket, with scripts/flow.py deciding every step. Also draws the ticket graph with show."
---

`<arguments>` below stands for the text the user typed after `$feature-flow`.

Plan or build the feature in `<arguments>`.

The first word is the **feature**. `show` means draw the graph. `auto` means ask nothing and go. If no feature was given and the conversation so far describes work to build, plan it (below) and propose the feature's name in the brief. If no feature was given otherwise, list `plans/*/` and ask which one.

The conductor is `python3 scripts/flow.py <feature> <command>`. If `scripts/flow.py` exists in the repo and the feature-flow package is beside it (`.feature-flow/feature_flow/`, or `feature_flow/` in a feature-flow checkout), use it (the repo's own install wins; an unrelated `scripts/flow.py` does not count); otherwise use `python3 "${FEATURE_FLOW_HOME:-$HOME/.feature-flow}/scripts/flow.py"` (`~/.feature-flow/scripts/flow.py`). Wherever this skill or a message names `scripts/flow.py`, `scripts/flow-status.py` or `scripts/flow-view.py`, it means the same folder, and the guides are then in that folder's sibling `guides/` (`~/.feature-flow/guides/`, else `.feature-flow/guides/` in the repo). Run the conductor with the working directory in the repo: state and plans stay there. It decides the order, runs the gate and the floor guard, and keeps its state in `.feature-flow/state/`, a folder git ignores. You ask it, and you do what it says. The guides it uses are in `.feature-flow/guides/` (in a feature-flow checkout, `guides/`). Read the project's `AGENTS.md` for its conventions.

## Show

With `show`, follow `.feature-flow/guides/show.md` for the feature and stop.

## Plan

When `plans/<feature>/` does not exist, or you are planning from the conversation, follow `.feature-flow/guides/brief.md` with the user. You write the brief and ask for both yeses (unless `auto`); a child agent plans, another reviews, and you never draft the plan yourself. Once the brief names the feature, run `FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> start` and check that it prints `PLAN`, and check that `.agents/flow-roles/feature-planner.md` and `.agents/flow-roles/plan-reviewer.md` exist (see below).

- `plan-prompt <brief>`: start the planner with `spawn_agent(task_name="feature_planner", fork_turns="none", message=...)`. The message is "Work only in <repo>." followed by the whole output. Get its final reply with `wait_agent`. A child cannot be limited to the draft folder, so it works from its instructions, and `plan-accept` is the only way its draft reaches `plans/`. If web search is off in this Codex, the planner plans from the codebase and says so.
- `plan-review-prompt`: start a new reviewer the same way, with `task_name="plan_reviewer"` and `fork_turns="none"`, never with the planner's reply. Get its final reply with `wait_agent` and save it with the shell into `.feature-flow/state/plan-review-<feature>.txt`.
- `plan-accept`: writes `plans/<feature>/` from the draft, only after the second yes.

Then run `python3 scripts/flow-status.py <feature> --check` and list the files `plan-accept` wrote. The second yes also approves committing the plan, so commit the folder `plan-accept` printed (`OK <folder>`, `plans/<feature>` unless `FLOW_DIR` is set) and nothing else: `git add -- <folder> && git commit -m "docs(<feature>): plan" -- <folder>`. If the commit fails, report why and stop. Then go straight on to building it below, unless the user asked to stop after planning.

To add tickets to a plan that exists, edit it by hand following the ticket rules in `.feature-flow/guides/plan.md`.

## Before building

With a plan present, check these before `start`, and stop at the first that fails:

- `git status --porcelain` is empty, apart from untracked Python bytecode (`__pycache__/`, `*.pyc`) and files listed in `.feature-flow/installed.txt` and that list itself: those are feature-flow's own install or upgrade, so never stop for them (`next` still stops if one of them was edited). Suggest committing them (`git add --pathspec-from-file=.feature-flow/installed.txt && git commit -m "chore: install feature-flow"`) and carry on.
- `python3 scripts/flow-status.py <feature> --check` prints `OK`.
- `ticket-builder.md` and `ticket-reviewer.md` are in `.agents/flow-roles/` in the repo or in `~/.feature-flow/agents/`. If not, say to run `uvx feature-flow-cli install . --agent codex` in this repo, or `uvx feature-flow-cli install --user --agent codex` (once for every repo) (or `python3 install.py <repo> --agent codex` from a feature-flow clone).

Then run `FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> start`. It prints `OK <token>`. Keep the token and put `FLOW_SESSION=<token>` in front of **every** later conductor command, with `FLOW_INVOKE='$feature-flow'`. The conductor keeps its state in `.feature-flow/state/`, a git-ignored folder in the repo, so it never needs to write `.git`. If it prints `STOP cannot write the flow state`, tell the user this session must be allowed to write that folder.

If `start` prints `STOP` naming another owner, another session may still be working this feature. Ask the user whether that session is closed. Only on a clear yes, run `start` once more with `FLOW_TAKEOVER=1`. In `auto` mode, never take over: report and stop.

If the user says the flow is stuck on a ticket or asks for a reset, run `reset` (or `reset <NN>` to redo one ticket): it reopens a half-built ticket, commits that, and clears the run, then run `start` again. It needs `FLOW_TAKEOVER=1` while a session owns the feature, on the same clear yes. Never reset on your own.

Say what will happen: for each ticket, a builder subagent and then a reviewer subagent. After every few tickets (`FLOW_TICKETS_PER_SESSION`, default 4) you hand off to a new session. Ask for a yes, unless `auto` was given or you came straight from planning: the plan's yes already covered the build.

## The loop

Run `next`, act on its one line, and repeat:

- `BUILD <ticket> <NN> <sha>`: run `prompt`. Start the builder with `spawn_agent(task_name="ticket_builder_<NN>_<k>", fork_turns="none", message=...)`. The message is "Work only in <repo>." followed by the whole `prompt` output, which already starts with the builder role. Use a new `task_name` for every spawn: keep a count per ticket in this session, and `<k>` is the number of builders already started for this ticket, plus 1 (1 for the first, then up each time `next` sends the ticket back to a builder). Get its final reply with `wait_agent`, then run `next`.
- `REVIEW <ticket> <NN> <sha>`: run `prompt`. Start a new reviewer the same way, with `fork_turns="none"` so it never sees the builder's context, and a unique `task_name` per spawn: `ticket_reviewer_<NN>_<pass>_<k>`, where `<pass>` is `spec` or `quality` by the pass the prompt names (`(spec pass)` or `(quality pass)`; `review` if it names none) and `<k>` is the number of reviews already started for this ticket in this session, plus 1 (1 for the first). Count every review, also one that ended in `RETRY` or a failed review followed by a rebuild, so a repeated pass never reuses a name. Get its final reply with `wait_agent`. A child cannot be made read-only, so the reviewer works from its instructions; the conductor catches any edit it makes. Save the whole reply with the shell: `cat > .feature-flow/state/flow-review-<feature>.txt <<'EOF'` ... `EOF`. Then run `verdict .feature-flow/state/flow-review-<feature>.txt` and `next`. If `verdict` prints `RETRY`, just run `next`.
- `DONE <summary>`: report it and suggest `$feature-flow <feature> show`.
- `STOP <reason>`: report the reason, run `python3 scripts/flow-status.py <feature>`, show the table, and stop.
- `HANDOFF <line>`: stop here. Tell the user to open a new session and type exactly `<line>`. The new session resumes where this one stopped.

A conductor command looks like this:

    FLOW_SESSION=<token> FLOW_INVOKE='$feature-flow' python3 scripts/flow.py <feature> next

## Rules while building

These apply from `start` on, once a plan exists.

- Never run the gate, the floor guard or a review yourself. The conductor runs the checks, and the reviewer subagent reviews.
- Never edit a ticket, the plan or the code, and never commit, apart from the approved plan above. The builder does that.
- Never skip a step, reorder steps, or decide the next step yourself. Only `next` decides.
- Never read a ticket's `## Answer` into the reviewer's prompt. `prompt` already holds everything it needs.
- Tell the user one short line per phase (`01 built`, `01 review: PASS`), not the subagents' reports.
