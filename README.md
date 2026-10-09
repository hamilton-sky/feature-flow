# Feature Flow

**A ticket-graph workflow for coding agents.** Works with Claude Code and Codex.

[![tests](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml/badge.svg)](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml)

Plan a feature as a graph of small tickets, then build them in the session you are already in. One command, `/feature-flow`, does both. Every ticket is built by one fresh subagent and checked by another that never saw the builder's reasoning. A script, not the agent, decides the order of the steps, runs the build and tests, and watches for work that weakens the checks, and the whole run has limits.

One skill, 2 agent roles, a Python conductor, 4 Python scripts, an installer for both agents, a demo and a test suite. All of it is Python (standard library only), so it runs on Linux, macOS and Windows. MIT licensed.

- [Quick start](#quick-start) · [How a ticket flows](#how-a-ticket-flows) · [The skill and the roles](#the-skill-and-the-roles) · [Plans and tickets](#plans-and-tickets)
- [See the graph](#see-the-graph) · [Long features and handoff](#long-features-and-handoff) · [What is tested](#what-is-tested) · [Upgrading](#upgrading) · [Caution](#caution)

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

The package puts a `feature-flow` command on your PATH with `install`, `status <feature>` and `view <feature>`. It installs the same files, byte for byte, as `install.py` from a clone.

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

**Planning asks you twice.** First the session shows a short feature brief, written from your conversation (what, why, scope, the bar, and anything it had to assume), and waits for yes, edit or cancel. Then a fresh `feature-planner` subagent, given only that brief, reads the code, looks up outside docs where the code cannot answer, and writes a draft plan into the git-ignored `.feature-flow/state/draft/`. A fresh `plan-reviewer` checks the draft against the brief. The session shows you the goal, the commands, the ticket graph, what was dropped and the review result, and waits for a second yes. Only then does `flow.py plan-accept` copy the draft into `plans/<feature>/`, and the session commits it and starts the build.

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
                                              │ PASS                ▼
                                              ▼        findings written into the ticket,
                                     next ticket       reopened, built again (3 rounds max);
                                                       the builder's prompt then carries
                                                       a root-cause debugging guide
```

`scripts/flow.py` is the conductor. The session asks it `next`, and it answers with one line: `BUILD`, `REVIEW`, `DONE`, `STOP` or `HANDOFF`. It prints the full prompt for each subagent from runtime-neutral guides, so the session never writes one itself.

**What the script checks and what it trusts.** The conductor verifies the build from the repo: the ticket file must say `resolved`, the tree must be clean and committed, and it runs the gate and the floor guard itself. It also runs the `check` block under each ticket's Done when and compares the exit code and printed text, and for a `Test first: yes` ticket it proves the red test commit itself: it checks out the test-only commit, runs Test, and requires it to fail before the code. A failure of either goes back to the builder before any reviewer is started. It also checks that the reviewer changed no tracked file and made no commit. The review verdicts are different: each reviewer's reply (spec review, then quality review) is relayed by the session, which saves it to a file and hands it to `flow.py verdict`. The script reads `REVIEW: PASS` or `REVIEW: FAIL` from that reply; it cannot prove the session passed it on unedited. A ticket moves on only after two PASS verdicts.

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
- `Floor:` categories: `skip`, `suppress`, `empty-catch`, `test-delete`, `threshold`, `config`, `ticket-edit`, `commands-edit`, and `flow-edit` (allows the conductor's code check below, for the build only). `skip` covers skipped, expected-fail and focused tests (`.only(`, `fit(`, `fdescribe(` on test paths); `config` covers more lint and test config files, the lint and test sections of `pyproject.toml` and `setup.cfg`, scripts and test keys in `package.json`, new skip or xfail words in `conftest.py`, and a `Makefile` only when `commands.md` uses `make`. A test file that loses assertions is shown to the reviewer as a warning, not a finding. The line is read from the ticket as it was before the work started, so a worker cannot excuse itself.
- The guard needs the plan to be tracked by git. If you keep tickets in an ignored folder, it cannot see changes to them.
- The commands in `commands.md` run with nobody watching and must exit non zero on failure.

## See the graph

```bash
python3 scripts/flow-view.py csv-export            write the page and open it
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
FLOW_TRUST=<digest|new> FLOW_SESSION=<token> python3 -I scripts/flow-trust.py <feature> next|prompt|verdict <file>   loop commands by hand, through the runner: prints TRUST <digest> first (no hash check, see below)
python3 scripts/flow-status.py <feature>                  table of tickets and which are READY
python3 scripts/flow-status.py <feature> --next           path of the next ready ticket (exit 10 = done, 11 = stuck)
python3 scripts/flow-status.py <feature> --counts         one line of counts
python3 scripts/flow-status.py <feature> --check          cycles, missing blockers, missing Done when, unordered mentions
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
| `FLOW_TAKEOVER` | unset | `1` lets `start` take a feature over from a session that is gone |
| `FLOW_MAX_RETRIES` | `2` | builds or reviews per step before the run stops |
| `FLOW_MAX_REVIEW_ROUNDS` | `3` | times a ticket may be sent back before the run stops |
| `FLOW_GATE` | `on` | `off` skips Build, Test and Lint after each ticket, and also the Done when and test-first checks |
| `FLOW_GATE_TIMEOUT` | `30` | minutes each gate command and the smoke test may run; `0` means no limit. A failed smoke test writes `.feature-flow/state/<feature>.smoke.log` |
| `FLOW_SMOKE` | the `Smoke:` line of `commands.md` | command run before every ticket; the run stops if it fails |
| `FLOW_DIR`, `FLOW_TICKETS` | `plans`, `tasks` | where the plans and the ticket folder live |
| `FLOW_NO_OPEN` | unset | `1` makes `flow-view.py` never open a browser |
| `FLOW_WATCH_SECONDS` | `3` | how often `flow-view.py --watch` rewrites the page |

The run also stops on its own after a number of phases (`BUILD` and `REVIEW` hand-outs, the spec review and the quality review each counting as one) that grows with the ticket count, recomputed at every pick, so a loop of failures cannot go on forever.

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

**Protected:** edits by the builder, reviewer or planner subagents during a session to feature-flow's own files (its `feature_flow` package, its files in `scripts/` (`flow.py`, `flow-status.py`, `gate.py`, `floor-guard.py`, `flow-view.py`, `flow-trust.py`), the guides, the roles and the skill folders, in the repo and in the install folders) and to the run state in `.feature-flow/state/`. That includes edits made by code the conductor runs during a step, such as tests, `check` commands and git hooks. Any of these makes the runner print a `STOP` instead of `TRUST`, naming the changed files where it can, and the session stops. It also holds between sessions when the `HANDOFF` line carries its digest (`HANDOFF /feature-flow <feature> <digest>`). `Floor: allow flow-edit` on a ticket allows its build to change the flow's code (never the run state); the runner then prints `FLOW-EDIT <files>`, and a session run without `auto` tells you which flow files changed.

**Not protected:** a subagent that changes `python3` on PATH or the system Python, the agent itself, or anything outside the repo and the install folders. The session's very first conductor call: whatever is on disk then is trusted. A background process left running by a step's own commands: it can swap a flow file in the instant between the runner's check and the conductor loading it, then put it back. A session that stops passing its digest, or a resume from a `HANDOFF` line without one (the session warns). The conductor's own code check (`STOP flow code changed while building <ticket>: <files>`) stays as a second line that catches accidental edits; on its own it cannot stop deliberate tampering.

The floor guard is pattern matching: it can miss things and it can raise false alarms, and `Floor: allow` is the release valve. The run stops on its own when a ticket stays unresolved, when the smoke test or the gate keeps failing, when a ticket keeps failing review, or when it reaches its phase limit.

## License

MIT. See `LICENSE`.
