# Plan a feature

Plan the **feature** you were given (called `<feature>` below) as one spec, one map and a graph of small tickets.

## Where the files go

First look for a documented convention (CLAUDE.md, AGENTS.md, `docs/`). If the repo already says where tickets live, use that place, and tell the user the two environment variables the scripts need (`FLOW_DIR`, `FLOW_TICKETS`).

Otherwise create a `plans/` folder at the repo root if there is none, then one folder named after the feature inside it:

```
plans/
└── <feature>/
    ├── spec.md            what and why
    ├── map.md             destination, decisions so far, open questions
    └── tasks/
        ├── 01-slug.md     one ticket per file
        └── 02-slug.md
```

If the folder already exists, stop and ask: add tickets after the highest number, or pick another name. Never overwrite.

## Step 1: Understand the feature

If the user already described it well, skip to Step 2. Otherwise ask only what the code cannot tell you:

- **What** it does and what problem it solves
- **Scope**: backend, frontend or both; what is explicitly out
- **Dependencies** on other work
- **The bar**: how will we know the whole feature works? One command and the output it should print.

## Step 2: Research the codebase

Find similar features and how they were built, the files that will change, the existing types and APIs the feature touches, and the test conventions. Also find the **real** build, test and lint commands. Tickets will quote them and `commands.md` will record them, so read them from `package.json`, `Makefile`, `Taskfile.yml`, CI config or the project's agent instructions file (CLAUDE.md or AGENTS.md). Do not guess. Also pick a **smoke command**: the quickest one that proves the base is healthy (usually build plus the fast tests). The flow runs it before every ticket, and runs Build, Test and Lint after every ticket, so all of them must run without asking anything and exit non zero on failure.

## Step 3: Draft the graph and get a yes

First, a lazy pass over your draft. For each ticket ask, in order: does the bar still hold without it? does the codebase already do it? does the standard library, the platform or an installed dependency already do it? can it be one line, or merged into another ticket? Drop or shrink what fails, and list what you dropped so the user can overrule you. Never drop: validation at trust boundaries, handling that prevents data loss, security, accessibility, or anything the user asked for.

Then, before writing any file, show the user the goal, the bar, the build, test and smoke commands you found, the tickets as a compact graph, and the dropped list:

```
01 Define the types
02 Build the service            after 01
03 Wire it into the API         after 02
04 Acceptance                   after 03
```

Ask them to confirm, edit or cancel. Write nothing until they say yes. Skip this only if they already approved a ticket list.

## Step 4: Write the files

- `spec.md` from [templates/spec.md](templates/spec.md). One document. Remove the sections that do not apply.
- `map.md` from [templates/map.md](templates/map.md).
- `commands.md` from [templates/commands.md](templates/commands.md), filled with the real commands from Step 2. Show it to the user with the graph: it is frozen once approved.
- `learnings.md` from [templates/learnings.md](templates/learnings.md), left empty. Workers append to it; it is separate from the map because it grows and the map should stay short.
- One `tasks/NN-slug.md` per ticket from [templates/ticket.md](templates/ticket.md).
- Screens? Add mockups to the spec using [templates/ui-mockup.md](templates/ui-mockup.md).

### Ticket rules

1. **One ticket is one change that leaves the build green**, small enough for one session. If Done when needs more than about 5 bullets, or Not in this ticket spans two areas, split it.
2. **`Blocked by` only for a real dependency**: the ticket cannot start without another's output. Independent tickets stay unblocked. Do not chain tickets just because of their numbers.
3. **Types**:
   - `task`: normal work.
   - `settle`: a decision that later tickets depend on. The Answer is the decision. Use it when two tickets would otherwise decide the same thing differently.
   - `convert`: migrating data, code or a format. It must be a script that gives the same result when run twice, list every transform, leave anything that does not match unchanged and print it, state expected counts in Done when ("reports N converted, M left alone"), include a test that no old shape survives, and change the writer or generator so new output is already the new shape.
4. **Done when must be checkable by a stranger**: the command and the result it prints. Never hard code the count of existing tests; "all existing tests still pass" is enough. A measured invariant is fine ("24 of 24 files round trip").
5. **Not in this ticket** names the nearest thing a reader would assume is included, and where it lives instead.
6. **Survive code drift**: no line numbers. Name functions and classes, and give a search hint for insertion points ("after the call to `parseConfig()`").
7. **Tests ride with the code they cover**: every ticket adds its own. Frontend tickets come after the API shape is stable.
8. **Set `Test first:`** on every ticket. `yes` for anything that adds or changes logic (the worker writes the failing test before the code), `no` for config, docs, renames and migrations that a command already proves.
9. **The last ticket is the acceptance ticket**: it runs the map's bar end to end and is blocked by every ticket that leaves the bar unproven.
10. **Number from 01 and never renumber.** Tickets added later get the next number.
11. **More than about 12 tickets?** Plan in rounds: `plans/<feature>/` first, then `plans/<feature>-round-two/` with its own map that links back.
12. **`Floor: allow <categories>` only when the user says so.** The floor guard fails a ticket whose diff skips or deletes tests, silences checks, adds empty catches, lowers thresholds, or edits lint, test or CI config. It also fails a worker that edits anything in the plan except its own Status and Answer, appended lines in `map.md` and `learnings.md`, and it fails any change to `commands.md`. If a ticket legitimately has to (for example "migrate the test runner", which changes `commands.md`), add a line such as `Floor: allow config, test-delete, commands-edit` to that ticket, and tell the user you did. Categories: `skip`, `suppress`, `empty-catch`, `test-delete`, `threshold`, `config`, `ticket-edit`, `commands-edit`. The line is read from the ticket as it was before the work started, so a worker cannot add it for itself.
13. **Name a ticket in prose only if it is ordered against this one.** If a ticket's text says "uses the output of ticket 02", list 02 under `Blocked by`. `--check` warns about mentions that are not ordered.

## Step 5: Check

Run `bash scripts/flow-status.sh <feature> --check`. It fails on a missing blocker, a cycle, a missing Done when, a duplicate number, a bad `Test first` value, or no ready ticket, and it warns about tickets that name another ticket in their text without being ordered against it. If the script is not installed, check those by hand. Fix every problem and every warning before reporting.

## Step 6: Report

```
Planned: plans/<feature>/
Tickets: N (M ready now)
The bar: <the command and expected output>

Graph: bash scripts/flow-status.sh <feature> --mermaid

Next: commit the plan, then start the feature-flow skill for <feature>
```
