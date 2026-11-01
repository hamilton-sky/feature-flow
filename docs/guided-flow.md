# A guided run, from your side of the chat

This page walks through the guided flow: the path from an idea to a running build with three stops. The rules the session follows are in [guides/brainstorm.md](../guides/brainstorm.md) and [guides/brief.md](../guides/brief.md); the [README](../README.md#the-guided-flow) has the summary.

![The guided flow: Setup, Options, Plan and Build on one page, with a stop before each of the first three steps](images/guided-flow.svg)

The pictures below are the page for a sample `csv-export` feature, taken at each stop.

Every stop is skippable. Say "ok" and the session takes its pick. With `auto`, `agent` or `fast` it asks nothing and takes the defaults. No stop has a timer, so a stop waits for you.

## Stop 1: the start card

```
/feature-flow rate-limits brainstorm
```

When you name no type, the session asks one question:

> Do you know the domain, the codebase, both, or are you just exploring?

Your answer picks the [brainstorm type](../README.md#brainstorm-before-planning):

| You say | Type | What changes |
|---|---|---|
| new to the domain | `learn` | ideas are explained as they come, with a cited Glossary; deep web scouts |
| new to this code | `map` | scouts map the repository first; deep code scouts |
| I know both | `standard` (or `quick` to keep it short) | the usual brainstorm (`quick`: one or two options, few helpers) |
| just exploring | `explore` | it ends in a Go or No-go, and only a Go goes on to a brief |

Then it shows the setup in one line, for example:

> `learn`: web scouts deep, code light, with the product owner, the skeptic and the `ux` lens. ok, or change it?

"ok" takes it. To change it, say so ("no skeptic", "code=deep"), or, on the live page, click the Setup step's buttons. The setup is written into the brainstorm's header (`Type:`, `Scouts:`, `Helpers:`), and later the plan's scouts and the build's scouts follow the same levels.

![The page at stop 1: the steps bar with Setup current, and the Setup step's choices for the type, the code scouts and the web scouts](images/guided-setup.png)

To skip the card, name the type yourself: `/feature-flow rate-limits brainstorm map code=deep`.

## Stop 2: the brainstorm's pick

The session asks its helpers, then shows two or three options on the page, each with a diagram you can edit, its pros, cons, size and risky areas, and the option it recommends. Each idea that came from a helper says so in brackets (`[architect]`, `[ux]`).

![Option B of three on the page at stop 2: its editable diagram (Admin, Export endpoint, Job queue, Export job, Tasks table, File store), and its pros, cons, size and risky areas, with the architect's and the skeptic's ideas tagged](images/guided-options.png)

Pick one, mix two, change one (edit its diagram and copy it back as mermaid), or drop the brainstorm. The same yes approves the brief that follows. [brainstorm.md](brainstorm.md) shows how to use the page.

## Stop 3: the plan's yes

The planner drafts the tickets, and the session shows them on the page's Plan step, with one line that sums up the build, for example:

> standard, up to 3 at once, gate + typecheck. Write this plan, commit it and start building? yes, edit, or cancel.

What the Plan step shows:

- **The tickets and their order**, as a diagram and a table with each ticket's level, its review and the paths it changes.
- **The width**: how many tickets can build at once, and why each waiting ticket waits (`04 waits for 03: level 3 shares the folder app/`). The same comes from `python3 scripts/flow-status.py <feature> --width`.
- **The checks** every ticket must pass: the gate's commands, the floor guard, the footprint, Done when and test first.

![The page at stop 3: the Plan step's ticket graph, the width line (up to 3 at once, 04 waits for 03) and the table of each ticket's level, review and paths](images/guided-plan.png)

What you can change before you say yes:

| Choice | Options | Written to the draft |
|---|---|---|
| Profile | `fast`, `standard`, `careful`, `normal` | `Profile:` in `commands.md` |
| Tickets building at once | Auto (the plan's width, at most 4, at most 2 with `careful`, 1 with `fast`), or 1 to 4 | `Lanes:` in `commands.md` |
| Full review | any tickets, which then get a spec review and a quality review | `Review: full` in the ticket |
| Builder notes | none, `frontend`, `backend` or `docs` per ticket; the page shows what its paths suggest | `Builder:` in the ticket |
| Add a check | ask in the chat: a type check, a security scan, or a command for one part of the repo | `Typecheck:`, `Security:` or `Check <path>:` in `commands.md` |
| Relax a check | ask in the chat, and give the reason | `Floor: allow <category>, reason: <why>` in `commands.md`, and the reason in `decisions.md` |

![The Plan step's Build flow: the gate's checks, the floor guard and the footprint, then the choices for the profile, tickets building at once, full reviews and builder notes](images/guided-plan-choices.png)

Turning the gate off is possible only as `Gate: off unsafe`. The session says plainly that the run is then unsafe, and the report and eval say so in their first line.

One yes approves the plan and its build setup together. Both are frozen with the plan, so nothing on the page can change them once the build starts. To change them later, ask for a re-plan.

## The build

The page's Build step shows each ticket's status as the run goes. Nothing on it is a choice. A ticket is built, gated and reviewed as [How a ticket flows](../README.md#how-a-ticket-flows) says, in as many [lanes](../README.md#tickets-side-by-side-lanes) as the plan's yes allowed. `FLOW_LANES` on `start` still overrides the plan's `Lanes:` line.

![The page during the build: Setup, Options and Plan folded into one-line summaries, and the Build step with 3 of 6 tickets done](images/guided-build.png)

After the plan is accepted, the session offers to clean up the brainstorm's spent files: `python3 scripts/flow-status.py <feature> --clean` lists them, and `--clean --yes` deletes them.

## How it is measured

`feature-flow eval <feature>` prints two lines for the guided flow:

```
guided stops: 3 (setup, options, plan; the aim is 3 or fewer)
helpers' ideas (asked, ideas, in the pick): architect 2/3/1, skeptic 1/2/0, ux 1/1/1
```

A run that stopped more than three times shows where the extra stops came from. A helper that is asked often but whose ideas never reach the pick is one to drop from the setup. [field-run.md](field-run.md) says what to send back.

## Without the live page

On Codex, or when the session cannot publish artifacts, the page is a plain HTML file beside the brainstorm (`.feature-flow/state/brainstorm-<feature>.html`), and you answer each stop in the chat. The stops, the choices and what gets written are the same.
