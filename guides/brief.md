# Plan a feature with the user

You are the user's session. You turn what the user wants into an approved **feature brief**, have a fresh planner draft the plan and a fresh plan reviewer check it, and write the plan into the repo only after the user says yes twice. You never draft the plan yourself, and only you talk to the user.

The conductor commands below are `python3 scripts/flow.py <feature> <command>`. The state folder is `.feature-flow/state/`, which git ignores.

## Step 1: Write the brief

If the conversation before this already describes the work, write the brief from it. If it does not, ask only what the code cannot tell you (what it does and why, what is in and out of scope, dependencies on other work, and the bar), then write the brief from the answers.

```
Feature: <folder name, lowercase-with-dashes>
What: <one or two sentences>
Why: <the problem, in the user's words where you can>
In scope: <what this covers>
Out: <what it does not cover, and anything the conversation set aside>
The bar: <one command and what it should print, or the observable outcome that proves the whole feature>
Unsure: <each thing you assumed, marked as an assumption>
```

Every line comes from the conversation or is marked as an assumption under Unsure. Never fill a gap with a guess. If there is no bar, ask for one: the brief is not ready without it. If `plans/<feature>/` already exists, say so and ask for another name; adding tickets to an existing plan is a hand edit that follows the ticket rules in the plan guide, not this flow.

## Step 2: Approval 1

Show the brief and ask: plan this? yes, edit, or cancel. On an edit, change the brief and show it again. On cancel, stop. Skip the question only in auto mode.

On yes, save the brief with the shell, not a file tool:

```
cat > .feature-flow/state/brief-<feature>.md <<'BRIEF'
<the brief>
BRIEF
```

## Step 3: The planner

Run `plan-prompt .feature-flow/state/brief-<feature>.md`. Start a fresh `feature-planner` subagent with the whole output as its prompt, and wait for its final reply. It writes the draft into `.feature-flow/state/draft/<feature>/` and ends with `PLAN: READY` or `PLAN: QUESTIONS`.

On `PLAN: QUESTIONS`, ask the user the questions, add the answers to the brief under a `Decided:` line, save it again, and start a new planner with a new `plan-prompt`. After two rounds of questions, show the user what is still open and ask whether to go on.

## Step 4: The plan reviewer

Run `plan-review-prompt`. Start a fresh `plan-reviewer` subagent with the whole output, never with the planner's reply, and wait for its final reply. Save the whole reply with the shell into `.feature-flow/state/plan-review-<feature>.txt`.

If it ends `PLAN-REVIEW: FAIL`, run the planner once more with the findings, `plan-prompt .feature-flow/state/brief-<feature>.md .feature-flow/state/plan-review-<feature>.txt`, then review again. A second FAIL is not retried: show its findings to the user at approval 2.

## Step 5: Approval 2

Show, from the planner's reply and the draft:

- the goal and the bar
- the build, test and smoke commands it found (they are frozen once approved)
- the tickets as a compact graph, for example `02 Build the service   after 01`
- what it dropped, so the user can overrule it
- what it assumed, its open questions, and any outside sources it relied on
- the plan review result, and its findings if it failed

Ask: write this plan, commit it and start building? yes, edit, or cancel (say if you want it to stop after the commit). On an edit, add it to the brief under `Decided:`, save, and go back to Step 3. On cancel, stop: the draft stays in the state folder and nothing in the repo changed. Skip the question only in auto mode.

## Step 6: Accept

Run `plan-accept`. It copies the draft into `plans/<feature>/` (or the project's `FLOW_DIR`) and checks it, then prints `OK <folder>`, or `STOP <reason>`: report the reason and stop. It never overwrites a plan and never commits: the skill commits the new folder, and only it, then goes on to build it.
