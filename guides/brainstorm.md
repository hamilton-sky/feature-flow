# Brainstorm a feature with the user

You are the user's session. Before the brief, you help the user choose **how** to build an idea: you look around, lay out two or three ways to build it, each with a diagram, and the user picks one. You write the result into one file, the **brainstorm**, which the planner, the plan reviewer and a later re-plan read. You never write code here, and only you talk to the user.

The file is `.feature-flow/state/brainstorm-<feature>.md`, in the git-ignored state folder: `plans/<feature>/` must not exist before `plan-accept`. `plan-prompt` copies it into the draft, so it is committed with the plan as `plans/<feature>/brainstorm.md`.

## When

- **`careful`** (the word, `FLOW_PROFILE=careful`, or `Profile: careful` in the conversation): always.
- **`brainstorm`** in the arguments: always.
- **Otherwise**, offer it in one line when the idea is fuzzy: there is no bar yet, there are two real ways to build it, or the brief would carry more than two Unsure lines. On a no, go to the brief.
- **Never** with `fast` (unless the user typed `brainstorm`), for a Spec Kit or OpenSpec import, or when a plan exists.
- With **`auto`** and no person to ask, skip it. With **`agent`** (another agent drives), the driving agent answers for the user and picks the option: write `Picked by: agent`.

## Step 1: Understand the idea

Ask at most three questions, one at a time, only about what the code cannot tell you: who it is for, what success looks like, what is off limits. Skip any the conversation already answers.

## The helpers

Six read only helpers work for you, never for each other, and never talk to the user. Each one gets its prompt from `brainstorm-prompt <helper> <question file>`, run through `flow-trust.py` like every conductor command: write the question into `.feature-flow/state/ask-<feature>-brainstorm.md` with the shell, run the command, spawn the subagent with the whole output as its prompt (in the background, several at once when they do not depend on each other), and save its whole reply with the shell into `.feature-flow/state/brainstorm-<feature>-<helper>-<n>.txt`. You copy what matters into the brainstorm; a helper never writes it.

| Helper | Subagent | Asks | Its reply goes to |
|---|---|---|---|
| `scout` | `flow-scout` | how the code does the nearest thing today, which files would change | What exists, unverified |
| `web` | `flow-web` | prior art, library docs, how others solved it | What exists, with links |
| `architect` | `flow-architect` | does an option fit the module boundaries, data shapes, patterns | Consulted |
| `designer` | `flow-designer` | how an option looks and behaves for its user | Consulted, the option's diagram |
| `po` | `flow-po` | what an option gives the user, what to cut | Consulted, Out in the brief |
| `skeptic` | `flow-skeptic` | the strongest objection to each finished option | each option's Cons and Risky areas |
| a lens | `flow-lens` | the options through one lens (below) | the option it speaks to, or a new option |

A lens is one way of looking, and its name is the helper's name: `positive` (the best case for each option), `researcher` (what the repository's own evidence says), `open-minded` (the option nobody drafted), `artistic` (how it feels to the person who meets it), `ux` (usability and accessibility) or `security` (what a hostile caller or a mistake could do). Pick the lenses that fit the idea: a screen the user sees gets `ux` and often `artistic`; anything that touches data, money, accounts or limits gets `security`; a vague or new idea gets `open-minded`; a choice that rests on a guess gets `researcher`. Ask a lens after the options are written, as the skeptic is.

The script counts them per brainstorm and stops past the limit: `normal` allows 2 scouts, 1 web, 2 consultants (architect, designer and po together), 1 skeptic and 2 lenses; `careful` allows 3, 2, 3, 1 and 3. `FLOW_SCOUTS=off` allows no scout or web. Past a limit, go on without. A reply that ends `ANSWER: USER` is a question for the user: ask it.

## Step 2: Look around

Ask one `scout`: how does this codebase already do the nearest thing, and which files would change? When the idea leans on an outside library, API or a known hard problem, ask a `web` helper at the same time: how have others solved it? Their replies are leads, not facts: check what an option depends on yourself.

## Step 3: Draw the options

Write two or three options that really differ (not one idea and two straw men). For each:

- a **mermaid diagram** in a ```mermaid block: a `flowchart` of the parts and what calls what, or a `sequenceDiagram` of the main flow. Show only what the feature adds or changes, at most about 12 nodes, labels in plain words.
- two or three pros and cons, a rough size (tickets, or S, M, L), and the risky areas: anything that touches auth, secrets, money, data that could be lost, limits, or what a hostile caller reaches.

If the choice turns on module boundaries, a screen or scope, ask the `architect`, `designer` or `po`. Then, with the options written, ask the `skeptic` (always in `careful`, otherwise when there are two options or more): its question is the Options section as you wrote it, never your reasons. Fold its objections into each option's cons and risky areas, add its simpler option when there is one, and only then recommend one option and say why in a sentence.

## Step 4: The user picks

Write the brainstorm file (below) with the options and no Chosen yet, then make it a review page: `python3 scripts/flow-status.py <feature> --brainstorm-page` writes `.feature-flow/state/brainstorm-<feature>.html` beside it, with a sidebar for the sections, a light, dark or system switch, diagrams whose boxes the user can drag, and an arrow animation they can turn on. The look is the brainstorm's `Style:` line (`route` unless the user asks for another style in `guides/styles/`). If you can publish an artifact, add `--fragment` and publish that file; otherwise give the user the file's path to open. Then show the options and your pick, and ask: which one? They may pick, edit, mix, or drop the brainstorm. On a drop, delete the file and write the brief as before.

Write the file with the shell, not a file tool, from [templates/brainstorm.md](templates/brainstorm.md), and again with Chosen and Rejected filled in once the user picks (make the page again if they want to see it):

```
cat > .feature-flow/state/brainstorm-<feature>.md <<'BRAINSTORM'
<the brainstorm>
BRAINSTORM
```

Then write the brief (brief guide, Step 1) from the chosen option, with the line `Brainstorm: .feature-flow/state/brainstorm-<feature>.md`: its What and In scope follow the chosen option, its Out names the rejected ones, and the brainstorm's Open lines go under Unsure. The user's pick and the brief share one yes (approval 1): show the brief right after the pick, and the yes covers both.

## Rules

- One question at a time; never a list of questions.
- Always recommend one option. Never decide for the user, except as the driving agent with `agent`.
- Never change files outside the state folder, and never commit: the brainstorm is committed with the plan.
- Helpers are read only, and a hook makes them so; they never write the brainstorm and never ask the user.
- Keep it short: a brainstorm that runs longer than the plan will is too long.
