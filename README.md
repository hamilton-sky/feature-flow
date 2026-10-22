# Feature Flow

**A ticket-graph workflow for coding agents.** Works with Claude Code and Codex.

[![tests](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml/badge.svg)](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml)

Plan a feature as a graph of small tickets, then build them in the session you are already in. One command, `/feature-flow`, does both. Every ticket is built by one fresh subagent and checked by another that never saw the builder's reasoning. A script, not the agent, decides the order of the steps, runs the build and tests, and watches for work that weakens the checks, and the whole run has limits.

One skill, 4 agent roles, a Python conductor, 6 Python scripts (`flow`, `flow-trust`, `flow-status`, `flow-view`, `gate`, `floor-guard`), an installer for both agents, a demo and a test suite. All of it is Python (standard library only), so it runs on Linux, macOS and Windows. MIT licensed.

- [Quick start](#quick-start) · [How a ticket flows](#how-a-ticket-flows) · [The skill and the roles](#the-skill-and-the-roles) · [Plans and tickets](#plans-and-tickets)
- [See the graph](#see-the-graph) · [Long features and handoff](#long-features-and-handoff) · [What is tested](#what-is-tested) · [Limits](#limits) · [Upgrading](#upgrading) · [Caution](#caution)

## Quick start

You need `git` and `python3` (3.9 or later, standard library only), and Claude Code or Codex. No `bash` or `awk` is needed to run feature-flow: every script is Python. On Windows use `python` where this page says `python3`.

```bash
git clone https://github.com/hamilton-sky/feature-flow.git
cd feature-flow

python3 install.py /path/to/your/repo                  # for Claude Code
python3 install.py /path/to/your/repo --agent codex    # for Codex
python3 install.py /path/to/your/repo --agent all      # both, side by side

# `bash install.sh ...` still works on Linux and macOS: it only runs install.py
```

Without a clone, the same installer runs from [PyPI](https://pypi.org/project/feature-flow-cli/):

```bash
uvx feature-flow-cli install /path/to/your/repo --agent all   # or: pipx run feature-flow-cli install ...
```

The package puts a `feature-flow` command on your PATH with `install`, `uninstall`, `status <feature>`, `view <feature>`, `reset <feature>` and `report <feature>`. It installs the same files, byte for byte, as `install.py` from a clone.

The installer lists what it wrote in `.feature-flow/installed.txt`, with each file's hash in `.feature-flow/installed.sha256`. Commit those files (`git add --pathspec-from-file=.feature-flow/installed.txt`); until you do, the flow does not count them as uncommitted changes. Installing a newer version over an older one updates every file nobody edited since it was installed, and keeps (and names) the ones you changed; `--force` replaces those too.

To keep the install out of git, so only your plans and tickets get committed, install with `--private`. It lists the installed files in `.git/info/exclude`, which git reads like `.gitignore` but never commits, and later installs keep that list up to date. If you already committed the install, it prints the `git rm --cached` command that untracks it and keeps the files. Every clone then needs its own install.

To remove it, run `feature-flow uninstall` (or `uvx feature-flow-cli uninstall`) in the repo. It removes exactly the files listed in `.feature-flow/installed.txt`, and only while they still hold the bytes the installer wrote: a file you edited is kept and named, and `--force` removes it too. It also drops the `--private` block from `.git/info/exclude`. Your `plans/`, your tickets and the run logs in `.feature-flow/state/` are never touched. `--dry-run` shows what would go. If you installed with `--user`, `feature-flow uninstall --user` removes the personal copy in `~/.claude` and `~/.agents`, and `~/.feature-flow`, the same way (the repo's own install is separate and needs its own `uninstall`).

Then, in your repo, in the agent:

| | Claude Code | Codex |
|---|---|---|
| Plan a feature (no plan yet) | `/feature-flow csv-export` | `$feature-flow csv-export` |
| Plan and build what you just talked through | `/feature-flow` | `$feature-flow` |
| Build its tickets (a plan exists) | `/feature-flow csv-export` | `$feature-flow csv-export` |
| The same, asking nothing | `/feature-flow csv-export auto` | `$feature-flow csv-export auto` |
| Watch the graph, animated | `/feature-flow csv-export show` | `$feature-flow csv-export show` |

The same command plans when `plans/csv-export/` does not exist yet and builds when it does. After your second yes it commits the new plan folder, and only that folder, then goes straight on to building it; say so if you want it to stop after planning.

**Planning asks you twice.** First the session shows a short feature brief, written from your conversation (what, why, scope, the bar, and anything it had to assume), and waits for yes, edit or cancel. Then a fresh `feature-planner` subagent, given only that brief, reads the code, looks up outside docs where the code cannot answer, and writes a draft plan into the git-ignored `.feature-flow/state/draft/`. The planner folds changes too small to stand alone into the ticket they belong to, and gives every ticket a level (1 light, 2 standard, 3 boundary) that decides how much review it gets. A fresh `plan-reviewer` checks the draft against the brief. The session shows you the goal, the commands, the ticket graph, what was dropped and the review result, and waits for a second yes. Only then does `flow.py plan-accept` copy the draft into `plans/<feature>/`, and the session commits it and starts the build.

Try the graph first, with no setup and no agent: `bash examples/demo.sh --open`.

### Two ways to install

- `feature-flow install --user`: once, for every repo. Skills and roles go to `~/.claude` / `~/.agents`, the conductor, guides and package to `~/.feature-flow/`. `FEATURE_FLOW_HOME` moves that folder. No repo files are written.
- `feature-flow install <repo>`: one repo. When a repo has its own copy, that copy wins over the user install.

### What the installer does

| | Claude Code (`--agent claude`, the default) | Codex (`--agent codex`) |
|---|---|---|
| The skill goes to | `<repo>/.claude/skills/` (`--user`: `~/.claude/skills/`) | `<repo>/.agents/skills/` (`--user`: `~/.agents/skills/`) |
| Roles go to | `<repo>/.claude/agents/` | `<repo>/.agents/flow-roles/`, put in front of each subagent's prompt |
| Scripts go to | `<repo>/scripts/` | `<repo>/scripts/` |
| Guides, roles and the conductor go to | `<repo>/.feature-flow/` | `<repo>/.feature-flow/` |

Next to the `feature-flow` skill it installs `architect-review` and `automation-design`. The installer never deletes anything. A file that already exists and differs is kept and reported; `--force` replaces it. `--dry-run` shows what would change and writes nothing. `CLAUDE_HOME` and `AGENTS_HOME` move the user folders. With `--user` the skill and roles go to the user folders, and the scripts, guides, conductor and package go to `~/.feature-flow/` (`FEATURE_FLOW_HOME` moves it); nothing is written into a repo.

The Claude Code skill is `skills/feature-flow/`. The Codex skill is written by hand in `adapters/codex/feature-flow/`, with an `agents/openai.yaml` that sets `allow_implicit_invocation: false`, so it runs only when you name it. The steps are the same; only the way a subagent is started differs. Your own `AGENTS.md` and `CLAUDE.md` are never touched.

## How a ticket flows

```
 smoke command (script): is the base healthy?   no ─► stop, spend nothing
        │ yes
        ▼
 pick ticket ─► builder subagent: claim, build, prove it (run fresh, read the output), commit
                                              │
                                              ▼
 gate (script):  Build, Test, Lint from commands.md           fail ─┐
                                              │ pass                │
                                              ▼                     │
 floor guard (script, no AI):                                       │
   tests skipped or deleted? checks silenced? empty catches?        │
   thresholds lowered? lint/test/CI config edited?             fail ─┤
   plan touched beyond own Status + Answer + appended lines?        │
                                              │ clean               │
                                              ▼                     │
 Done when checks (script): runs every ```check block          fail ─┤
 test-first check (script): Test first: yes needs a test-only        │
   commit that failed Test before the code                     fail ─┤
                                              │ pass                │
                                              ▼                     │
 spec review: fresh reviewer subagent, sees only the ticket         │
 + diff, re-runs every Done when                              FAIL ─┤
                                              │ PASS                │
                                              ▼                     │
 quality review: a second fresh reviewer subagent             FAIL ─┤
   (a level 1 or 2 ticket gets one combined review instead
    of these two; see "Ticket levels" below)
                                              │ PASS                ▼
                                              ▼        findings written into the ticket,
                                     next ticket       reopened, built again (rounds by level);
                                                       the builder's prompt then carries
                                                       a root-cause debugging guide
```

`scripts/flow.py` is the conductor. The session asks it `next`, and it answers with one line: `BUILD`, `REVIEW`, `DONE`, `STOP` or `HANDOFF`. It prints the full prompt for each subagent from runtime-neutral guides, so the session never writes one itself.

**What the script checks and what it trusts.** The conductor verifies the build from the repo: the ticket file must say `resolved`, the tree must be clean and committed, and it runs the gate and the floor guard itself. It also runs the `check` block under each ticket's Done when and compares the exit code and printed text, and for a `Test first: yes` ticket it proves the red test commit itself: it checks out the test-only commit, runs Test, and requires it to fail before the code. A failure of either goes back to the builder before any reviewer is started. It also checks that the reviewer changed no tracked file and made no commit. The review verdicts are different: each reviewer's reply (spec review, then quality review) is relayed by the session, which saves it to a file and hands it to `flow.py verdict`. The script reads `REVIEW: PASS` or `REVIEW: FAIL` from that reply; it cannot prove the session passed it on unedited. A ticket moves on only after two PASS verdicts, or one for a level 1 or 2 ticket (or, with no level, a ticket the conductor judged small). The size is measured from the repo (`git diff` against the commit the ticket started from), never taken from the builder.

**The gate: full or quick.** The gate runs Build, Test and Lint after every ticket. With an optional `Quick:` line in `commands.md` (a faster subset of `Test`), it runs Build, Quick and Lint after the tickets in the middle of a plan, and the full Build, Test and Lint after the last ticket, before a handoff, and under `FLOW_GATE_FULL=1`. A plan without `Quick:` runs the full gate every time. The test-first proof still runs the full `Test` command.

**Ticket levels.** The planner writes `Level: 1`, `2` or `3` in each ticket, the plan reviewer checks it against written rules, and you approve it with the plan.

| | Level 1 (light) | Level 2 (standard) | Level 3 (boundary) |
|---|---|---|---|
| For | tests, docs, prompt text, spikes, the acceptance ticket | ordinary feature code | auth, tokens, permissions, money and run limits, data loss, the flow's own code, anything a hostile caller reaches |
| Reviews | one combined review | one combined review, spec checklist first | spec review, then a quality review that probes every input as a hostile caller |
| Rework rounds | 1, then the run stops for you | 2; from round 3 only a `blocker` sends it back, majors go to `plans/<feature>/followups.md` and the ticket passes | `FLOW_MAX_REVIEW_ROUNDS` (3), then the run stops for you |

The gate does not depend on the level: it still runs Quick mid-plan and the full Test on the last ticket and before a handoff. Nobody but you can lower a level. The conductor reads `Level:` from the ticket as it was at the base commit, so a builder's edit does nothing (and the floor guard fails it). It raises the level from what it measures, never lowers it: `Review: full`, `Type: convert` and `Floor: allow flow-edit` make a ticket level 3, so does a diff that touches a path on the optional `Sensitive:` line of `commands.md` (frozen by the floor guard), and a level 1 diff over the small limits becomes level 2. A reviewer can raise it with a line `LEVEL: 3` above the verdict; a raise to 3 during a combined review adds a quality review. The log records `LEVEL-1`, `LEVEL-2` or `LEVEL-3` for each review round, and `feature-flow report` shows it.

**A rebuild reruns only the review that failed.** When a level 3 ticket fails its quality review, the rebuilt ticket gets the quality review only; the spec review it already passed is not repeated. The conductor's own checks (gate, floor guard, Done when, test first) still run on every rebuild.

**One review for a small ticket (no level).** A ticket with no `Level:` line, from a plan written before 0.9.0, keeps the 0.8.0 rules. A ticket whose built diff is 3 files and 60 changed lines at most (the plan folder left out), and whose `check` block ran and passed, gets one combined review instead of the spec and quality reviews. The conductor measures the diff itself. `Review: full` in the ticket (as it was at the start), `Type: convert`, no `check` block, or `FLOW_GATE=off` keep both reviews. Every other conductor check still runs on every ticket.

## The skill and the roles

| Skill | What it does |
|---|---|
| `feature-flow` | **Plan:** turns the conversation (or your answers) into a feature brief and waits for a yes, has a planner and a plan reviewer subagent draft and check `plans/<feature>/` (a spec, a map, commands, learnings and tickets), shows you the graph, and writes it after a second yes. **Build:** runs the tickets one by one, a builder and a reviewer subagent each, with `flow.py` deciding every step. **Show:** the animated ticket graph and a summary of what is ready and what blocks the finish. |
| `architect-review` | Architecture review of a file, diff or feature, with severity rated findings. Reads `CLAUDE.md` or `AGENTS.md` for the project's own rules. |
| `automation-design` | Blueprint for an automation pipeline. Hands off to `feature-flow` for the plan. |

| Role | Tools | Job |
|---|---|---|
| `ticket-builder` | Read, Glob, Grep, Edit, Write, Bash | Builds one ticket by the build guide in its prompt. |
| `ticket-reviewer` | Read, Glob, Grep, Bash (no Edit, no Write) | Reviews one ticket by the review guide in its prompt and ends with `REVIEW: PASS` or `REVIEW: FAIL`. |
| `feature-planner` | Read, Glob, Grep, Bash, Write, Edit, WebSearch, WebFetch | Plans one feature from the approved brief by the plan guide, writes only the draft, cites outside sources, and ends with `PLAN: READY` or `PLAN: QUESTIONS`. |
| `plan-reviewer` | Read, Glob, Grep, Bash (no Edit, no Write) | Checks the draft against the brief by the plan review guide and ends with `PLAN-REVIEW: PASS` or `PLAN-REVIEW: FAIL`. |

In Claude Code the reviewers' tool lists are enforced, so they cannot edit. A Codex subagent cannot be limited that way, so there the reviewers work from their instructions: the conductor stops the run if a ticket reviewer changed anything, and a planner's draft reaches `plans/` only through `plan-accept`. On Codex the planner can research the web only if web search is on; otherwise it plans from the code and says so. The Codex planning path has not been run by hand.

The guides in `guides/` (installed to `.feature-flow/guides/`) hold the protocol: how to build, review, write the brief, plan, review a plan and show. The skill holds only what differs per agent.

## Plans and tickets

```
plans/
└── csv-export/
    ├── spec.md          what and why
    ├── map.md           destination, the bar, decisions so far     (workers append only)
    ├── commands.md      build, test, lint, smoke commands           (frozen once approved)
    ├── learnings.md     traps workers found                         (workers append only)
    └── tasks/
        ├── 01-types.md
        ├── 02-service.md
        └── 03-acceptance.md
```

`commands.md` and `learnings.md` are separate from the map because they follow different rules. Commands are approved by a human and read by the scripts, so they are frozen. Learnings grow with every ticket, so they are append only and a human prunes them (`--check` warns past 40 lines). The map stays short.

One markdown file per ticket in `plans/<feature>/tasks/NN-slug.md`:

````
# Add the retry policy to the job runner

Type: task                 task | settle | convert
Status: open               open | claimed | resolved | parked
Blocked by: 01, 02         or —
Test first: yes            yes | no
Level: 2                   1 light | 2 standard | 3 boundary
Touches: src/export/       the paths it changes; a build outside them goes back
Floor: allow config        optional, only when a human decides the guard may let it through

...what to do and why...

## Not in this ticket
## Done when                 commands and the results they print
```check
$ python3 -m unittest discover -s tests/py
exit 0
prints OK
```
## Reference
## Answer                    Built, Proof, Decisions, Shortcuts taken, Review fixes, For later tickets
````

- **Order comes from `Blocked by`**, not from numbers. A ticket is *ready* when it is open and every ticket it is blocked by is resolved. Lowest number wins.
- **Status lives only in the ticket files.** `map.md` never repeats it.
- **The Answers are the handoff between subagents.** The next builder reads the Answers of the tickets it depends on.
- `settle` tickets record a decision. `convert` tickets migrate something and must be safe to run twice.
- **A worker may change only** its own Status line and Answer, lines appended to `map.md` and `learnings.md`, and the code the ticket calls for. Rewriting its own Done when, editing another ticket, or touching `commands.md` fails the guard.
- `Floor:` categories: `skip`, `suppress`, `empty-catch`, `test-delete`, `threshold`, `trivial-assert` (an assertion that cannot fail, added to a test file: `assert True`, `assertEqual(x, x)`, `expect(v).toBe(v)`), `config`, `ticket-edit`, `commands-edit`, and `flow-edit` (allows the conductor's code check below, for the build only). `skip` covers skipped, expected-fail and focused tests (`.only(`, `fit(`, `fdescribe(` on test paths); `config` covers more lint and test config files, the lint and test sections of `pyproject.toml` and `setup.cfg`, scripts and test keys in `package.json`, new skip or xfail words in `conftest.py`, and a `Makefile` only when `commands.md` uses `make`. A test file that loses assertions is shown to the reviewer as a warning, not a finding. The line is read from the ticket as it was before the work started, so a worker cannot excuse itself.
- The guard needs the plan to be tracked by git. If you keep tickets in an ignored folder, it cannot see changes to them.
- The commands in `commands.md` run with nobody watching and must exit non zero on failure.

## See the graph

![The animated ticket graph for the demo plan: five of ten tickets resolved, two ready, one in progress](docs/flow-view.png)

*The page `flow-view` writes, shown for the demo plan from `examples/demo.sh`: resolved tickets in green, ready ones in amber, the one being worked in blue, the rest waiting. Press Replay to watch the run back from git history.*

```bash
python3 scripts/flow-view.py csv-export            write the page and open it (or: feature-flow view csv-export)
python3 scripts/flow-view.py csv-export --watch    keep it updating while tickets are built
bash examples/demo.sh --open                    try it on a made up project, no setup needed
```

One self contained HTML file: no server, no libraries, no network, light and dark. It is written to `.git/flow-<feature>.html`, so it never dirties the tree (`--out FILE` writes it elsewhere).

```
  01 types ──► 02 service ──► 04 acceptance        ● resolved  ◉ ready (pulses)
        └────► 03 wire ──────────┘                 ◌ being worked (spins)  ○ waiting
  ▶ replay ──●──────●─────○──────────   drag to scrub through the run
```

- **Layered left to right**, so the order of work is visible. Dashes flow along the edges into tickets that are ready to start.
- **Replay** plays the run back from git history: tickets turn green in the order they resolved, and a ticket sent back by the gate, the guard or the reviewer flashes red.
- **Hover or click** a ticket for its blockers, Done when, Answer, and the rounds it was sent back.
- **Keys:** space plays or pauses, the arrows step, End shows now, `t` switches theme. Reduced motion is respected.
- **Safe by construction:** ticket text comes from files an agent wrote, so it is escaped when embedded and only ever inserted as text.
- `flow-status.py <feature> --json` prints the same data for other tools. Mermaid (`--mermaid`) remains the choice for pull requests, because GitHub renders it.

## Tickets side by side (lanes)

With `FLOW_LANES=2` (up to 4) on `start`, tickets that do not touch the same files are built at the same time, each with its own builder and reviewers in its own git worktree. Only the start and the end of a ticket change: the build, the gate, the floor guard and the reviews are the same as with one lane.

- **Plan.** Each ticket lists the paths it changes on a `Touches:` line (a folder ends with `/`, a `*` glob crosses folders). `commands.md` may name `Shared:` paths that many tickets change, and a `Setup:` command a fresh checkout needs. The plan reviewer checks the footprints; you approve them with the plan.
- **Schedule.** The conductor leases a ready ticket to a free lane only when its `Touches:` (read from the feature branch, never from a builder) does not overlap any running ticket's, it touches nothing on `Shared:`, and, when either ticket is level 3, the two keep to different top-level folders. A ticket with no `Touches:` line runs alone.
- **Lanes.** The lanes are worktrees in `.feature-flow/lanes/<feature>/` (git ignores the folder), created on first use, with `Setup:` run once in each. Each ticket gets a branch `ff/<feature>/<NN>` from the feature head.
- **Footprint check.** After every build, with or without lanes, a change to a path outside the ticket's `Touches:` sends the ticket back (`FOOTPRINT-FAIL` in the log).
- **Merge.** A ticket that passes its review is merged by the conductor, one at a time, in `.feature-flow/lanes/<feature>/integrate` with `git merge --no-ff`, so the reviewed commits land unchanged. The gate runs on the merge (Quick mid-plan, the full Test for the last ticket). Only a green merge fast-forwards the feature branch; then the ticket's branch is deleted with `git branch -d`. When two lanes both appended to `map.md`, `learnings.md` or `followups.md`, the conductor keeps both sides' lines; no agent ever resolves a conflict.
- **Rebuild.** Any other conflict, or a gate that fails on the merge, sends the ticket back to be built again from the feature branch as it is now, with what went wrong and its earlier commit in the ticket. A second collision stops the run for you: the plan's `Touches:` are likely wrong.
- **Level 3.** When another ticket merged after a level 3 ticket started, it is merged with the new feature head in its lane, gated, and given its quality review again before it merges.
- **The end.** After the last merge the lanes are removed. `reset` removes them too, with the ticket branches.

The session runs `prompt`, `next` and `verdict` with the lane from the `BUILD` or `REVIEW` line, and `next` answers `WAIT <lanes>` when every lane that can work is busy (see `## Lanes` in the skill).

## Scouts

Before a planner, builder or reviewer starts, the session can spawn cheap helpers that read ahead for it: `flow-scout` (read only, codebase) and `flow-web` (web only, for the planner). Both run on Haiku in Claude Code (`model: haiku` in their role files); in Codex the skill picks the lightest model `spawn_agent` allows. A scout looks at the code the way its role would (`ROLE: builder` looks for patterns and helpers to reuse, `ROLE: reviewer` for the rules the change must follow) and never decides anything.

| Before | Scouts |
|---|---|
| planning (`plan-scouts <brief>`) | one codebase scout and one web scout |
| a level 1 ticket | none |
| a build below level 3 (first attempt) | one builder scout on the ticket and its `Touches:` |
| a level 3 build (first attempt) | two builder scouts: the code it changes, and what depends on it |
| a level 3 ticket's spec review | one reviewer scout on the conventions the diff must follow |
| the feature review (fast path) | one reviewer scout |

`scouts [lane]` lists `SCOUT <k> <agent> <reply file>` lines (or `NONE`) and clears the last ones' replies; `scout-prompt <k> [lane]` prints one scout's prompt. The session saves each reply into its file, and the phase's `prompt` adds them under `## Scout findings (unverified)`, cut to 60 lines each. A reply saved for one phase never reaches another. Retries and later rounds get no scouts. `FLOW_SCOUTS=off` turns them off.

## Questions for the architect, designer or product owner

A builder, reviewer or planner that hits a question it should not decide alone asks it instead of guessing, and the flow pauses that job until the right role answers.

- **Who answers.** `flow-architect` answers technical design questions, `flow-designer` answers UI and UX questions, and `flow-po` answers what the feature must do where the spec is silent. Each is a fresh, read only agent that sees the plan, the ticket as it was planned and the code, never the asker's reasoning or a ticket's Answer. Each gets one scout with its own lens first.
- **A builder** appends `## Ask: architect|designer|po` with the question to its ticket and stops. `next` hands out `ASK <role> <ticket> <NN> <sha>`. The answer goes into the ticket under `## Consulted (<role>)`, and the ticket is built again. The question does not count as a failed attempt.
- **A reviewer** ends with a `## Question` and `REVIEW: ASK <role>`. The answer comes back in the next review's notes. On the fast path's feature review, the reviewer writes the question as a finding, and the fix ticket's builder can ask it.
- **The planner** starts each open question with `architect:`, `designer:`, `po:` or `user:`. The session runs `consult-prompt <role> <question file>` for the first three, adds the answers to the brief under `Consulted:`, kept apart from your `Decided:` lines, and plans again.
- **What still comes to you.** Any question the asker marks `user`, any answer a consultant ends with `ANSWER: USER` (it changes what you get, so its options come to you), and a third consultant question on one ticket all stop the run with the question, written into the ticket under `## Ask: user`. You answer under `## Consulted (user)` at the end of the ticket, commit, and run `next`. A reviewer's question for you reopens the ticket, so its builder builds again with your answer.

## The fast path

`/feature-flow <feature> fast` trades per-ticket reviews for speed. The planner gets `Pace: fast` in the brief and writes a short plan of fewer, larger tickets, and the plan reviewer is skipped. With `FLOW_FAST=1` on `start`, a ticket below level 3 (one with no `Level:` line too) that passes the gate, the floor guard and its Done when checks passes at once (`REVIEW-DEFERRED` in the log). With `FLOW_GATE=off` nothing would check it, so every ticket keeps its review. A level 3 ticket, or one that touches a `Sensitive:` path, still gets its own reviews.

- **The feature review.** Once every ticket is resolved, `next` hands out `REVIEW <plan folder> all <sha>`: one fresh reviewer reads the deferred tickets as they were planned and the whole diff from the oldest deferred ticket's base to HEAD, with `guides/review-feature.md`. It has no lane, even when lanes run.
- **A failed feature review** becomes a new ticket, `NN-feature-review-fixes-<round>.md`, with the findings in it. A builder fixes it, and the feature is reviewed again. After `FLOW_MAX_REVIEW_ROUNDS` failed rounds the run stops for you.
- **Mid-run.** `fast on` and `fast off` (through the runner, like `next`) switch it between phases. Asking the session to go faster runs `fast on`. Asking again while fast is on offers the re-plan below. Tickets already passed without a review still get the feature review, whichever way it is switched.
- **The cost.** A mistake in an early ticket is found at the end, when later tickets may have built on it. Use it for small or low-risk features. `reset` keeps the list of deferred tickets, so they still get the feature review.

## A time budget

`FLOW_BUDGET=<minutes>` on `start` gives the feature a budget of active minutes. The conductor counts the time between its steps, at most an hour for one step, so a session left open overnight does not eat the budget, and the time between two sessions does not count. `budget` (through the runner) reports it, and `budget <minutes>`, `budget +<minutes>` or `budget off` change it between phases.

- **Over the budget, fast mode first.** Before the next ticket starts, the conductor turns fast mode on by itself (`BUDGET-FAST` in the log).
- **Still over, a re-plan offer.** Once fast mode has finished a ticket and the run is still over (or at once, if fast mode was already on), the run stops once with the minutes spent, the tickets left, and an offer to re-plan. If one ticket took more than half the time over several attempts, the stop names it as stuck, since that is a stuck ticket, not a slow plan. `next` goes on as planned, and a new `budget` earns a new offer.
- **The re-plan needs your yes.** On your yes, between tickets, `replan-prompt` hands the `feature-planner` the open tickets with `guides/replan.md`. It folds them into fewer, larger tickets with the same bar: every Done when item and check moves into the ticket that takes over, folded tickets become `Status: parked (folded into NN)`, and resolved tickets stay as they are. The session shows you the change and commits it only on a second yes. The next `next` stops if the re-plan changed a resolved ticket. Nothing is ever cut without you.

## Long features and handoff

A session's context fills up, so the flow moves to a fresh session every few tickets. After `FLOW_TICKETS_PER_SESSION` tickets (default 4) pass review, `next` prints a `HANDOFF` line instead of the next ticket, for example `HANDOFF /feature-flow csv-export 3f9c0a1b2c3d4e5f.0a1b2c3d4e5f6a7b` (the last word is the runner's digest, which lets the new session check that the flow's files did not change in between). The session stops and tells you to open a new session and type that line. The new session picks up exactly where the last one stopped. Set `FLOW_TICKETS_PER_SESSION=0` to never hand off.

- **One owner at a time.** `start` gives the session a token, and every later call must carry it, so two sessions can never drive the same feature. `HANDOFF` and `DONE` release it.
- **Resuming after a closed session.** If a session ended without `HANDOFF` (you closed it, it crashed, it ran out of budget), the feature is still owned by it, and a new session stops and says so. Once you are sure the old session is gone, answer yes when the new session asks, or start it with `FLOW_TAKEOVER=1`. With `auto` the skill never takes over on its own.
- **Stuck on a ticket.** `python3 scripts/flow.py <feature> reset` (or `feature-flow reset <feature>`) reopens a ticket left `claimed` or `in-progress`, commits that, and clears the conductor's run state, so the next `/feature-flow <feature>` starts clean from the ticket files. `reset <NN>` reopens that one ticket, even a resolved one, to build it again. While a session owns the feature it needs `FLOW_TAKEOVER=1`. A mistyped command or feature name gets a `did you mean` hint.
- **Relay mode.** `FLOW_RELAY=1` hands off after every build and every review, so each phase gets a session of its own.
- **Nobody needs to watch.** With `auto` the skill asks nothing, and a Claude Code cloud session keeps working while you are away. You only come back to type the `HANDOFF` line.

The state lives in `.feature-flow/state/` (the state, a log of every step, and the last review reply). That folder ignores itself, so it never shows up in `git status`, and a normal Codex session can write it, which it cannot do under `.git`.

### Commands and settings

```bash
python3 scripts/flow.py <feature> start|reset [NN]          the conductor (the skill runs it; also plan-prompt, plan-review-prompt, plan-accept)
FLOW_TRUST=<digest|new> FLOW_SESSION=<token> python3 -I scripts/flow-trust.py <feature> next|prompt|verdict <file>|fast on|off   loop commands by hand, through the runner: prints TRUST <digest> first (no hash check, see below)
python3 scripts/flow-status.py <feature>                  table of tickets and which are READY
python3 scripts/flow-status.py <feature> --next           path of the next ready ticket (exit 10 = done, 11 = stuck)
python3 scripts/flow-status.py <feature> --ready          every ready ticket, one per line (the same exit codes)
python3 scripts/flow-status.py <feature> --counts         one line of counts
python3 scripts/flow-status.py <feature> --check          cycles, missing blockers, missing Done when, unordered mentions
python3 scripts/flow-status.py <feature> --lint           --check plus: a check block (or `Check: none <why>`) on every ticket, a Test command
feature-flow report <feature>                             what a run did, from its log: builds, reviews, failed checks, stops
python3 scripts/flow-status.py <feature> --mermaid        the ticket graph, coloured by status (add "plain" for none)
python3 scripts/flow-status.py <feature> --json           every ticket with status, blockers and readiness
python3 scripts/flow-view.py <feature> [--watch]          the animated graph page, opened in your browser
python3 scripts/gate.py <feature>                         run Build, Test and Lint from commands.md
python3 scripts/floor-guard.py <feature> <NN> [base]      check a ticket's diff, run from the repo root
```

`next`, `prompt` and `verdict` run directly stop with `STOP run the conductor through scripts/flow-trust.py, as the skill says`. Pass `FLOW_TRUST=new` on a first call, then the digest from the last `TRUST` line. Run by hand like this, nothing checks `flow-trust.py` itself, so it is for trying things out, not a protected run. The skills never run it this way: they start it through a loader line that first checks the file against the sha256 the skill pins, and stops with `flow-trust.py does not match this skill` if it differs (see `## Calling the conductor` in the skill). For a `--user` install the scripts are in `~/.feature-flow/scripts/` (or `$FEATURE_FLOW_HOME/scripts/`).

The commands in `commands.md` run through `bash -c` on Linux and macOS and through the system shell (`cmd.exe`) on Windows, so write them for the platform your team uses, or call `python` as in the examples.

`flow-status.py` also understands the `.scratch/<feature>/issues/` layout and the statuses `done`, `ready-for-agent`, `ready-for-human` and `closed`: `FLOW_DIR=.scratch FLOW_TICKETS=issues`.

| Variable | Default | Meaning |
|---|---|---|
| `FLOW_TICKETS_PER_SESSION` | `4` | tickets per session before `HANDOFF`; `0` never hands off |
| `FLOW_RELAY` | `0` | `1` hands off after every build and every review |
| `FLOW_LANES` | `1` | read by `start`: `2` to `4` builds tickets with disjoint `Touches:` side by side in worktrees (not with `FLOW_RELAY`) |
| `FLOW_FAST` | unset | read by `start`: `1` defers the reviews of tickets below level 3 to one feature review at the end, `0` turns it off; unset keeps the run's setting |
| `FLOW_BUDGET` | unset | read by `start`: minutes of active work before fast mode turns on, then a re-plan offer; `off` drops it |
| `FLOW_SCOUTS` | `on` | `off` lists no scouts before any phase |
| `FLOW_TAKEOVER` | unset | `1` lets `start` take a feature over from a session that is gone |
| `FLOW_MAX_RETRIES` | `2` | builds or reviews per step before the run stops |
| `FLOW_MAX_REVIEW_ROUNDS` | `3` | times a ticket may be sent back before the run stops (a level 1 ticket: once) |
| `FLOW_GATE` | `on` | `off` skips Build, Test and Lint after each ticket, and also the Done when and test-first checks |
| `FLOW_GATE_FULL` | unset | `1` runs the full Build, Test and Lint after every ticket, even when `commands.md` has a `Quick:` line |
| `FLOW_SMALL_FILES` | `3` | most files a ticket may change and still get the single review (no level), or stay level 1 |
| `FLOW_SMALL_LINES` | `60` | most changed lines for the single review; `0` turns the single review off |
| `FLOW_GATE_TIMEOUT` | `30` | minutes each gate command and the smoke test may run; `0` means no limit. A failed smoke test writes `.feature-flow/state/<feature>.smoke.log` |
| `FLOW_SMOKE` | the `Smoke:` line of `commands.md` | command run before every ticket; the run stops if it fails |
| `FLOW_DIR`, `FLOW_TICKETS` | `plans`, `tasks` | where the plans and the ticket folder live |
| `FLOW_NO_OPEN` | unset | `1` makes `flow-view.py` never open a browser |
| `FLOW_WATCH_SECONDS` | `3` | how often `flow-view.py --watch` rewrites the page |

The run also stops on its own after a number of phases (`BUILD` and `REVIEW` hand-outs, the spec review and the quality review each counting as one, a single review counting as one) that grows with the ticket count, recomputed at every pick, so a loop of failures cannot go on forever.

## What is tested

| Path | Tested |
|---|---|
| Claude Code | The offline suite, and **one real run of the bar**: the two-ticket demo in two `/feature-flow hello auto` sessions with one `HANDOFF` between them, each ticket built by a builder subagent and passed by a reviewer subagent, with all 16 acceptance checks ok. It used about 23k output tokens and 2M cached input tokens on Sonnet. |
| Codex | The install, offline, in CI on Linux and macOS. A probe in the Codex app showed that subagents with separate contexts work and that a reviewer's verdict reaches the session. The full flow is **not yet tested with a real run**. |
| Claude Code on the web | Documented, untested: commit `.claude/`, `scripts/` and `.feature-flow/` into the repo, because cloud sessions read only the repo's `.claude/`. |
| Copilot, Gemini CLI, Cursor | Not tested. Some read `.agents/skills`, so `--agent codex` may already work. |

### Trying it by hand

```bash
bash tests/smoke-real.sh --prepare /tmp/hello-try                    # the demo project, for Claude Code, no model is called
FLOW_AGENT=codex bash tests/smoke-real.sh --prepare /tmp/hello-codex # the same, for Codex
```

Then `cd` into it, start the agent and type `/feature-flow hello` (Codex: `$feature-flow hello`).

## Tests

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/py
```

Offline and free: no model is called. The suite covers the conductor's every answer and how a run stops, sessions, handoff and takeover, a `.git` the agent cannot write, the gate, the floor guard, plan protection, the prompts and guides, both skills, the installer for both agents, the graph page and its data, the Done when checks, the test-first check, the two reviews and the debugging guide on a send-back, and the acceptance harness. `tests/run.sh` also drives a prepared demo with no model through both checks and both reviews. The page's layout and replay logic are also tested under Node (`tests/viewer-logic.test.js`, skipped when Node is absent). `.github/workflows/tests.yml` runs it on every push to `main` and every pull request, on Ubuntu and on macOS. A fourth job runs the Python unit tests on Windows, including a fixture drive that takes a two-ticket plan through `python scripts/flow.py f start` and `next` to `BUILD` and then `REVIEW`, with `FLOW_TRUSTED=1` set as the runner sets it. `tests/run.sh` itself is a bash harness and does not run on Windows. Windows is tested this way only: no real agent run has been done there.

A `package` job builds the wheel and the sdist and runs `tests/package_smoke.py` on Ubuntu (Python 3.9 and the latest), macOS and Windows: it installs the wheel in a fresh virtual environment, runs `feature-flow install`, and checks that the repo gets the same files as from `install.py` in a clone. Run it locally with `python3 -m pip install build && python3 tests/package_smoke.py`.

`RUN_REAL=1 bash tests/smoke-real.sh --interactive` is the acceptance run with Claude Code. It runs real sessions on the demo project and spends money, which is why it asks for `RUN_REAL=1`.

## Limits

feature-flow's layers are tripwires, not a security boundary. They catch accidents and lazy shortcuts by an agent; a determined agent that controls the session could still get around them.

- **The verdict relay is trusted.** The session saves a reviewer's reply and hands it to `flow.py verdict`. The conductor reads `REVIEW: PASS` or `REVIEW: FAIL` from that file and cannot prove the session passed it on unedited.
- **The floor guard reads diffs with patterns.** It does not see a test made trivially true by other means (a mock that returns the expected answer, an `assert` on something that is always set, a test that no longer exercises the code), or an assertion weakened without being deleted. It does catch assertions that cannot fail (`trivial-assert`) and warns the reviewer when a test file loses assertions. A new test with no assertion at all is not caught. The red-first proof only covers tickets with `Test first: yes`.
- **A plan can be wrong and still pass.** The plan lint checks that every ticket has a way to be proven and that `commands.md` has a Test command. It cannot tell whether the plan builds the right thing; the second yes is yours.
- **The trust runner stops accidents, not the session.** It catches a builder editing the conductor mid-run. The session that runs it is the thing it cannot check; a hand-run `flow-trust.py` is unprotected (see above).
- **Little real-world use so far.** Almost everything has been built by feature-flow on its own repo. The Codex skill and the Codex planner have not been run by hand, and the Quick gate has only been run by tests. See [docs/field-run.md](docs/field-run.md) for how to try it on your own repo and what to send back.
- **One ticket at a time**, with a handoff to a new session every few tickets, unless you turn on lanes.
- **Lanes share one disk.** A builder in one lane can still write into another lane's folder or the main worktree. The conductor sees that as a dirty tree and stops, but only afterwards. Overlap of `Touches:` is judged from the patterns, so two tickets that could never meet may still run one after the other.

## Upgrading

Earlier versions had seven skills and an unattended loop. The five flow skills are gone, and `/feature-flow` replaces them:

- `plan-feature` → `/feature-flow <feature>` before a plan exists.
- `/next-phase` and `/review-ticket` → `/feature-flow <feature>`, which runs a builder and a fresh reviewer subagent for every ticket.
- `show-flow` → `/feature-flow <feature> show`.
- `/run-flow` and `scripts/auto-flow.sh` → `/feature-flow <feature> auto`, with a `HANDOFF` every few tickets. There is no cost log any more.

The installer never deletes the old skill folders, but it names any it finds. Delete them from `.claude/skills/` or `.agents/skills/` yourself.

## Releasing to PyPI

The package is [`feature-flow-cli`](https://pypi.org/project/feature-flow-cli/) (the shorter `feature-flow` is likely refused by PyPI as too close to the existing `featureflow`). Its version is `__version__` in `feature_flow/__init__.py`.

To release, bump `__version__`, merge it to `main`, then tag that commit and push the tag:

```bash
git tag v0.1.1 && git push origin v0.1.1
```

`.github/workflows/release.yml` checks that the tag matches `__version__`, builds the wheel and the sdist, runs `tests/package_smoke.py` on them and publishes them to PyPI. PyPI trusts the workflow as a trusted publisher (owner `hamilton-sky`, repository `feature-flow`, workflow `release.yml`, environment `pypi`), so no token is stored. PyPI never accepts the same version twice.

## Caution

The builder subagent has edit and shell access and commits after each ticket. Each ticket costs at least two subagents. Build on a branch you can throw away. Ignore build output in `.gitignore`, because the conductor stops if the tree is dirty after a ticket. The gate and the smoke test stop after 30 minutes (`FLOW_GATE_TIMEOUT`). The session runs every conductor call through `scripts/flow-trust.py`, which sits beside the conductor it runs (`scripts/` in the repo, or `~/.feature-flow/scripts/` for a `--user` install). The skill pins the runner's sha256 and starts it with a one-line loader that checks and runs those same bytes, so a subagent cannot change the check. The runner prints `TRUST <code>.<state>` before the conductor's output, and the session passes that digest to the next call as `FLOW_TRUST`.

**Protected:** edits by the builder, reviewer or planner subagents during a session to feature-flow's own files (its `feature_flow` package, its files in `scripts/` (`flow.py`, `flow-status.py`, `gate.py`, `floor-guard.py`, `flow-view.py`, `flow-trust.py`), the guides, the roles and the skill folders, in the repo and in the install folders) and to the run state in `.feature-flow/state/`. That includes edits made by code the conductor runs during a step, such as tests, `check` commands and git hooks. Any of these makes the runner print a `STOP` instead of `TRUST`, naming the changed files where it can, and the session stops. It also holds between sessions when the `HANDOFF` line carries its digest (`HANDOFF /feature-flow <feature> <digest>`). `Floor: allow flow-edit` on a ticket allows its build to change the flow's code (never the run state, and never `scripts/flow-trust.py`, whose hash the skill pins: change the runner outside the flow, or build it with a conductor from another install, then update the pinned sha in both skills); the runner then prints `FLOW-EDIT <files>`, and a session run without `auto` tells you which flow files changed.

**Not protected:** a subagent that changes `python3` on PATH or the system Python, the agent itself, or anything outside the repo and the install folders. The session's very first conductor call: whatever is on disk then is trusted. A background process left running by a step's own commands: it can swap a flow file in the instant between the runner's check and the conductor loading it, then put it back. A session that stops passing its digest, or a resume from a `HANDOFF` line without one (the session warns). The conductor's own code check (`STOP flow code changed while building <ticket>: <files>`) stays as a second line that catches accidental edits; on its own it cannot stop deliberate tampering.

The floor guard is pattern matching: it can miss things and it can raise false alarms, and `Floor: allow` is the release valve. The run stops on its own when a ticket stays unresolved, when the smoke test or the gate keeps failing, when a ticket keeps failing review, or when it reaches its phase limit.

## License

MIT. See `LICENSE`.
