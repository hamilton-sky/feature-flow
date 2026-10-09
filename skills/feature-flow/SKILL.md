---
name: feature-flow
description: Use to plan a feature (from the conversation so far, with a fresh planner and plan reviewer subagent) or build its tickets, a fresh builder subagent per build and a fresh reviewer subagent per review pass, with scripts/flow.py deciding every step. Also draws the ticket graph with show.
argument-hint: "[feature] [show] [auto]"
disable-model-invocation: true
---

Plan or build the feature in `$ARGUMENTS`.

The first word is the **feature**. `show` means draw the graph. `auto` means ask nothing and go. If no feature was given and the conversation so far describes work to build, plan it (below) and propose the feature's name in the brief. If no feature was given otherwise, list `plans/*/` and ask which one.

The conductor is `python3 scripts/flow.py <feature> <command>`. If `scripts/flow.py` exists in the repo and the feature-flow package is beside it (`.feature-flow/feature_flow/`, or `feature_flow/` in a feature-flow checkout), use it (the repo's own install wins; an unrelated `scripts/flow.py` does not count); otherwise use `python3 "${FEATURE_FLOW_HOME:-$HOME/.feature-flow}/scripts/flow.py"` (`~/.feature-flow/scripts/flow.py`). Wherever this skill or a message names `scripts/flow.py`, `scripts/flow-status.py` or `scripts/flow-view.py`, it means the same folder, and the guides are then in that folder's sibling `guides/` (`~/.feature-flow/guides/`, else `.feature-flow/guides/` in the repo). Run the conductor with the working directory in the repo: state and plans stay there. It decides the order, runs the gate and the floor guard, and keeps its state in `.feature-flow/state/`, a folder git ignores. You ask it, and you do what it says. The guides it uses are in `guides/` or `.feature-flow/guides/`.

## Calling the conductor

Every conductor command (`start`, `next`, `prompt`, `verdict`, `reset`, `plan-prompt`, `plan-review-prompt`, `plan-accept`) runs through `flow-trust.py`, never `flow.py` itself. `<S>` below is the folder of the `flow.py` picked above: `scripts` for the repo's own install, else `"${FEATURE_FLOW_HOME:-$HOME/.feature-flow}/scripts"`. `flow-trust.py` is started by this loader line, which checks the file against the sha256 pinned here and runs those same bytes. Copy it exactly, replacing only `<S>`:

    python3 -I -c "import hashlib,sys;b=open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n');sys.exit(exec(compile(b,'flow-trust','exec')) if hashlib.sha256(b).hexdigest()==sys.argv[2] else 'flow-trust.py does not match this skill')" <S>/flow-trust.py e1d7ddd9dd940cb9fe9f72cc310d3ddfcb197b03de26b03d371f66b48e77ef2b

A full conductor command, here `next` (any other command and its arguments go where `next` is):

    FLOW_TRUST=<digest> FLOW_SESSION=<token> FLOW_INVOKE=/feature-flow python3 -I -c "import hashlib,sys;b=open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n');sys.exit(exec(compile(b,'flow-trust','exec')) if hashlib.sha256(b).hexdigest()==sys.argv[2] else 'flow-trust.py does not match this skill')" <S>/flow-trust.py e1d7ddd9dd940cb9fe9f72cc310d3ddfcb197b03de26b03d371f66b48e77ef2b <feature> next

- The first line of the output is `TRUST <digest>`. Keep that digest and pass it as `FLOW_TRUST` on the next conductor call. Treat the rest as the conductor's output and act on it as below (for `prompt`, `plan-prompt` and `plan-review-prompt`, the subagent's prompt is everything after the `TRUST` line). Use `FLOW_TRUST=new` only on this session's first conductor call, or when resuming from an old-style `HANDOFF` line (below).
- If you no longer have the last `TRUST` digest, stop and say so. Never guess it, and never use `new` in its place.
- On the `next` right after a `BUILD <ticket> <NN> <sha>`, add `--after-build <ticket> <sha>` before the feature: `... <S>/flow-trust.py e1d7ddd9dd940cb9fe9f72cc310d3ddfcb197b03de26b03d371f66b48e77ef2b --after-build <ticket> <sha> <feature> next`. If the output has a `FLOW-EDIT <paths>` line after `TRUST`, the build changed feature-flow's own files and its ticket allows that: carry on; without `auto`, first tell the user which flow files changed.
- If the first line is `STOP` (from `flow-trust.py`), or the loader prints `flow-trust.py does not match this skill` (say to reinstall feature-flow: the skill and `flow-trust.py` do not match), report it, show the `python3 <S>/flow-status.py <feature>` table, and stop. A `STOP` first line may be followed by the conductor's own output: never act on that. Never fix it and carry on.
- A `HANDOFF` line from `flow-trust.py` has a third field after the invocation and the feature: the digest. When the feature is followed by a `<16 hex>.<16 hex>` word, the user is resuming from a `HANDOFF` line and that word is the digest: pass it as `FLOW_TRUST` on `start`. When a resumed session gets no digest (an old-style `HANDOFF` line), use `FLOW_TRUST=new` and warn the user that the flow's files could not be checked since the last session.

## Show

With `show`, follow `guides/show.md` for the feature and stop.

## Plan

When `plans/<feature>/` does not exist, or you are planning from the conversation, follow `guides/brief.md` with the user. You write the brief and ask for both yeses (unless `auto`); a subagent plans, another reviews, and you never draft the plan yourself. Once the brief names the feature, run `start` through `flow-trust.py` (see Calling the conductor) with `FLOW_INVOKE=/feature-flow`, and check that it prints `PLAN` after the `TRUST` line, and check that `feature-planner.md` and `plan-reviewer.md` are installed where the builder's role is (see below).

- `plan-prompt <brief>`: spawn a `feature-planner` subagent with the whole output as its prompt. Wait for its final reply.
- `plan-review-prompt`: spawn a `plan-reviewer` subagent with the whole output, never with the planner's reply. Wait for its final reply and save it with Bash into `.feature-flow/state/plan-review-<feature>.txt`.
- `plan-accept`: writes `plans/<feature>/` from the draft, only after the second yes.

Then run `python3 scripts/flow-status.py <feature> --check` and list the files `plan-accept` wrote. The second yes also approves committing the plan, so commit the folder `plan-accept` printed (`OK <folder>`, `plans/<feature>` unless `FLOW_DIR` is set) and nothing else: `git add -- <folder> && git commit -m "docs(<feature>): plan" -- <folder>`. If the commit fails, report why and stop. Then go straight on to building it below, unless the user asked to stop after planning.

To add tickets to a plan that exists, edit it by hand following the ticket rules in `guides/plan.md`.

## Before building

With a plan present, check these before `start`, and stop at the first that fails:

- `git status --porcelain` is empty, apart from untracked Python bytecode (`__pycache__/`, `*.pyc`) and files listed in `.feature-flow/installed.txt` and that list itself: those are feature-flow's own install or upgrade, so never stop for them (`next` still stops if one of them was edited). Suggest committing them (`git add --pathspec-from-file=.feature-flow/installed.txt && git commit -m "chore: install feature-flow"`) and carry on.
- `python3 scripts/flow-status.py <feature> --check` prints `OK`.
- `ticket-builder.md` and `ticket-reviewer.md` are in `.claude/agents/`, `~/.claude/agents/`, or `$CLAUDE_HOME/agents/` when `CLAUDE_HOME` is set. If not, say to run `uvx feature-flow-cli install .` in this repo, or `uvx feature-flow-cli install --user` (once for every repo) (or `python3 install.py <repo>` from a feature-flow clone).

Then run `start` through `flow-trust.py` with `FLOW_INVOKE=/feature-flow`. After the `TRUST` line it prints `OK <token>`. Keep the token and put `FLOW_SESSION=<token>` in front of **every** later conductor command, with `FLOW_INVOKE=/feature-flow` and the last `FLOW_TRUST`.

If `start` prints `STOP` naming another owner, another session may still be working this feature. Ask the user whether that session is closed. Only on a clear yes, run `start` once more with `FLOW_TAKEOVER=1`. In `auto` mode, never take over: report and stop.

If the user says the flow is stuck on a ticket or asks for a reset, run `reset` (or `reset <NN>` to redo one ticket): it reopens a half-built ticket, commits that, and clears the run, then run `start` again. It needs `FLOW_TAKEOVER=1` while a session owns the feature, on the same clear yes. Never reset on your own.

Say what will happen: for each ticket, a builder subagent and then a fresh reviewer subagent for each review pass. After every few tickets (`FLOW_TICKETS_PER_SESSION`, default 4) you hand off to a new session. Ask for a yes, unless `auto` was given or you came straight from planning: the plan's yes already covered the build.

## The loop

Run `next`, act on its one line after `TRUST` (and any `FLOW-EDIT` line), and repeat:

- `BUILD <ticket> <NN> <sha>`: run `prompt`. Spawn a `ticket-builder` subagent with that output as its whole prompt, and ask for a short summary back. Wait for its final reply: an Agent call can return before the subagent finishes, and the reply then arrives as a notification. Then run `next` with `--after-build <ticket> <sha>` from that `BUILD` line.
- `REVIEW <ticket> <NN> <sha>`: run `prompt` and spawn a `ticket-reviewer` subagent with it. Wait for its final reply. Save the whole reply with Bash, not the Write tool, into the conductor's git-ignored state folder: `cat > .feature-flow/state/flow-review-<feature>.txt <<'EOF'` ... `EOF`. Never under `.git`: an unattended session is refused there as a sensitive file. Then, as separate commands, run `verdict .feature-flow/state/flow-review-<feature>.txt` and `next`. If `verdict` prints `RETRY`, just run `next`.
- `DONE <summary>`: report it and suggest `/feature-flow <feature> show`.
- `STOP <reason>`: report the reason, run `python3 scripts/flow-status.py <feature>`, show the table, and stop.
- `HANDOFF <line>`: stop here. Tell the user to open a new session and type exactly `<line>`, the whole line with its digest at the end. The new session resumes where this one stopped.

## Rules while building

These apply from `start` on, once a plan exists.

- Never run the gate, the floor guard or a review yourself. The conductor runs the checks, and the reviewer subagent reviews.
- Never edit a ticket, the plan or the code, and never commit, apart from the approved plan above. The builder does that.
- Never skip a step, reorder steps, or decide the next step yourself. Only `next` decides.
- Never read a ticket's `## Answer` into the reviewer's prompt. `prompt` already holds everything it needs.
- Tell the user one short line per phase (`01 built`, `01 review: PASS`), not the subagents' reports.
