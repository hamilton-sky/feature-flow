# Brainstorm a feature with the user

You are the user's session. Before the brief, you help the user choose **how** to build an idea: you look around, lay out two or three ways to build it, each with a diagram, and the user picks one. You write the result into one file, the **brainstorm**, which the planner, the plan reviewer and a later re-plan read. You never write code here, and only you talk to the user.

The file is `.feature-flow/state/brainstorm-<feature>.md`, in the git-ignored state folder: `plans/<feature>/` must not exist before `plan-accept`. `plan-prompt` copies it into the draft, so it is committed with the plan as `plans/<feature>/brainstorm.md`.

## When

- **`careful`** (the word, `FLOW_PROFILE=careful`, or `Profile: careful` in the conversation): always.
- **`brainstorm`** in the arguments: always. **`brainstorm sketch`** starts from the user's own drawing (Sketch first, below).
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

Write the brainstorm file (below) with the options and no Chosen yet, then make it a review page: `python3 scripts/flow-status.py <feature> --brainstorm-page` writes `.feature-flow/state/brainstorm-<feature>.html` beside it, with a sidebar for the sections, a light, dark or system switch, diagrams whose boxes the user can drag, and an arrow animation they can turn on. The look is the brainstorm's `Style:` line: the style the user names, else the one that fits the subject (below). If you can publish an artifact, add `--fragment` and publish that file; otherwise give the user the file's path to open. Then show the options and your pick, and ask: which one? They may pick, edit, mix, or drop the brainstorm. On a drop, delete the file and write the brief as before.

Styles, and what each suits:

| Style | Suits |
|---|---|
| `route` | the default: most features |
| `blueprint` | architecture, backends, system design |
| `sketch` | early, fuzzy ideas, a first sketch |
| `paper` | a decision to share, print or send outside the team |
| `terminal` | infrastructure, CLIs, dev tools, pipelines, data jobs |
| `bright` | consumer apps, screens, onboarding, UI and UX |

Colour boxes by role, the same way on every diagram, so a colour means one thing: people `orange`, screens `purple`, services and jobs `blue`, stored data `green`, outside systems `grey`, and `red` for the part an option puts at risk. Leave other boxes plain. In mermaid that is a `classDef <colour> ...` and a `class <ids> <colour>` line per colour; the page reads the colour name. The page's Arrange button re-lays a diagram (left to right, top to bottom, radial, grid), so draw for meaning, not for layout.

Write the file with the shell, not a file tool, from [templates/brainstorm.md](templates/brainstorm.md), and again with Chosen and Rejected filled in once the user picks (make the page again if they want to see it):

```
cat > .feature-flow/state/brainstorm-<feature>.md <<'BRAINSTORM'
<the brainstorm>
BRAINSTORM
```

Then write the brief (brief guide, Step 1) from the chosen option, with the line `Brainstorm: .feature-flow/state/brainstorm-<feature>.md`: its What and In scope follow the chosen option, its Out names the rejected ones, and the brainstorm's Open lines go under Unsure. The user's pick and the brief share one yes (approval 1): show the brief right after the pick, and the yes covers both.

## The live page

When you can publish an artifact (Claude Code with the Artifact tool), make the page live instead. Then the user, and the people they invite, can each save their own version of a diagram, compare it with the original (added, removed and renamed boxes are marked), ask Claude in the page to change a diagram, and send you questions. Each person they invite needs a claude.ai sign-in and edit access from the page's Share menu.

1. `python3 scripts/flow-status.py <feature> --brainstorm-page --live .feature-flow/state/brainstorm-<feature>-live` writes `index.html` and `state.json` into that folder.
2. Publish `index.html`, with `state.json` as a file beside it and the capabilities `{"artifact": {}, "user": {"scopes": ["profile"]}, "sample": {}}`. Publish from the same path every round so the link stays the same. Give the user the link, and tell them it starts private and that they share it from its Share menu.
3. End your turn. A save on the page republishes it, and that wakes you. Read the page's `state.json` (the Artifact tool's read, with path `state.json`) and copy it over the one in the live folder.
4. `--brainstorm-page --asks <live folder>` lists the open asks, each with the asker's version of the diagram. Answer each one:
   - Change the brainstorm when the ask calls for it. `--brainstorm-page --apply <live folder> <figure> <version>` puts that person's version of a figure into the file, and `original` as the version puts the original back.
   - Then run `--brainstorm-page --answer <live folder> <n> "<answer>"`, with a short answer that says what you changed.
5. Run step 1 again, which keeps the saved versions and asks, and publish both files to the same link. If a publish is refused because the page has a newer version, take that version's `state.json` and go back to step 4.

A save that only adds a version, with no ask, needs nothing from you. The user still picks in the chat, as in Step 4. Without an Artifact tool, or on Codex, make the plain page.

## Sketch first

Use this with `brainstorm sketch` in the arguments, or when the user would rather draw than describe.

1. After Step 1, write the brainstorm with only the Idea section and a `## Sketch` section. The Sketch holds one small flowchart of the idea as you understand it, two to four boxes.
2. Make the live page, and ask the user to draw their idea on it: add, rename, colour and connect boxes, press Save as my version, then send you a note with Send to Claude.
3. When the ask comes, `--apply` their version into the Sketch and treat it as the idea in their words.
4. Go on with Step 2 and Step 3. Your options build on their sketch, and your answer on the page says how.

Sketch first needs the live page. Without an Artifact tool, ask the user to describe the idea instead.

## Rules

- One question at a time; never a list of questions.
- Always recommend one option. Never decide for the user, except as the driving agent with `agent`.
- Never change files outside the state folder, and never commit: the brainstorm is committed with the plan.
- Helpers are read only, and a hook makes them so; they never write the brainstorm and never ask the user.
- Keep it short: a brainstorm that runs longer than the plan will is too long.
