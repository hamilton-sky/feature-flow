# Feature Flow

**A ticket-graph workflow for coding agents.** Works with Claude Code and Codex.

[![tests](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml/badge.svg)](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml)

Plan a feature as a graph of small tickets, then build them in the session you are already in. One command, `/feature-flow`, does both. Every ticket is built by one fresh subagent and checked by another that never saw the builder's reasoning. A script, not the agent, decides the order of the steps, runs the build and tests, and watches for work that weakens the checks, and the whole run has limits.

One skill, 2 agent roles, a Python conductor, 4 scripts, an installer for both agents, a demo and a test suite. MIT licensed.

- [Quick start](#quick-start) · [How a ticket flows](#how-a-ticket-flows) · [The skill and the roles](#the-skill-and-the-roles) · [Plans and tickets](#plans-and-tickets)
- [See the graph](#see-the-graph) · [Long features and handoff](#long-features-and-handoff) · [What is tested](#what-is-tested) · [Upgrading](#upgrading) · [Caution](#caution)

## Quick start

You need `bash`, `git`, `awk` and `python3` (3.9 or later, standard library only), and Claude Code or Codex.

```bash
git clone https://github.com/hamilton-sky/feature-flow.git
cd feature-flow

bash install.sh /path/to/your/repo                  # for Claude Code
bash install.sh /path/to/your/repo --agent codex    # for Codex
bash install.sh /path/to/your/repo --agent all      # both, side by side
```

Then, in your repo, in the agent:

| | Claude Code | Codex |
|---|---|---|
| Plan a feature (no plan yet) | `/feature-flow csv-export` | `$feature-flow csv-export` |
| Build its tickets (a plan exists) | `/feature-flow csv-export` | `$feature-flow csv-export` |
| The same, asking nothing | `/feature-flow csv-export auto` | `$feature-flow csv-export auto` |
| Watch the graph, animated | `/feature-flow csv-export show` | `$feature-flow csv-export show` |

The same command plans when `plans/csv-export/` does not exist yet and builds when it does. Commit the plan before you build it.

Try the graph first, with no setup and no agent: `bash examples/demo.sh --open`.

### What the installer does

| | Claude Code (`--agent claude`, the default) | Codex (`--agent codex`) |
|---|---|---|
| The skill goes to | `<repo>/.claude/skills/` (`--user`: `~/.claude/skills/`) | `<repo>/.agents/skills/` (`--user`: `~/.agents/skills/`) |
| Roles go to | `<repo>/.claude/agents/` | `<repo>/.agents/flow-roles/`, put in front of each subagent's prompt |
| Scripts go to | `<repo>/scripts/` | `<repo>/scripts/` |
| Guides, roles and the conductor go to | `<repo>/.feature-flow/` | `<repo>/.feature-flow/` |

Next to the `feature-flow` skill it installs `architect-review` and `automation-design`. The installer never deletes anything. A file that already exists and differs is kept and reported; `--force` replaces it. `--dry-run` shows what would change and writes nothing. `CLAUDE_HOME` and `AGENTS_HOME` move the user folders. With `--user` the skill goes to the user folder, but the scripts and `.feature-flow/` stay in the repo, because the skill runs them from there.

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
 fresh reviewer subagent: sees only the ticket + diff,              │
 re-runs every Done when                                      FAIL ─┤
                                              │ PASS                ▼
                                              ▼        findings written into the ticket,
                                     next ticket       reopened, built again (3 rounds max)
```

`scripts/flow.py` is the conductor. The session asks it `next`, and it answers with one line: `BUILD`, `REVIEW`, `DONE`, `STOP` or `HANDOFF`. It prints the full prompt for each subagent from runtime-neutral guides, so the session never writes one itself.

**What the script checks and what it trusts.** The conductor verifies the build from the repo: the ticket file must say `resolved`, the tree must be clean and committed, and it runs the gate and the floor guard itself. It also checks that the reviewer changed no tracked file and made no commit. The review verdict is different: the reviewer's reply is relayed by the session, which saves it to a file and hands it to `flow.py verdict`. The script reads `REVIEW: PASS` or `REVIEW: FAIL` from that reply; it cannot prove the session passed it on unedited.

## The skill and the roles

| Skill | What it does |
|---|---|
| `feature-flow` | **Plan:** writes `plans/<feature>/` with a spec, a map, commands, learnings and tickets, shows you the graph, and waits for a yes. **Build:** runs the tickets one by one, a builder and a reviewer subagent each, with `flow.py` deciding every step. **Show:** the animated ticket graph and a summary of what is ready and what blocks the finish. |
| `architect-review` | Architecture review of a file, diff or feature, with severity rated findings. Reads `CLAUDE.md` or `AGENTS.md` for the project's own rules. |
| `automation-design` | Blueprint for an automation pipeline. Hands off to `feature-flow` for the plan. |

| Role | Tools | Job |
|---|---|---|
| `ticket-builder` | Read, Glob, Grep, Edit, Write, Bash | Builds one ticket by the build guide in its prompt. |
| `ticket-reviewer` | Read, Glob, Grep, Bash (no Edit, no Write) | Reviews one ticket by the review guide in its prompt and ends with `REVIEW: PASS` or `REVIEW: FAIL`. |

In Claude Code the reviewer's tool list is enforced, so it cannot edit. A Codex subagent cannot be limited that way, so there the reviewer works from its instructions, and the conductor stops the run if it changed anything.

The guides in `guides/` (installed to `.feature-flow/guides/`) hold the protocol: how to build, review, plan and show. The skill holds only what differs per agent.

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

```
# Add the retry policy to the job runner

Type: task                 task | settle | convert
Status: open               open | claimed | resolved | parked
Blocked by: 01, 02         or —
Test first: yes            yes | no
Floor: allow config        optional, only when a human decides the guard may let it through

...what to do and why...

## Not in this ticket
## Done when                 commands and the results they print
## Reference
## Answer                    Built, Proof, Decisions, Shortcuts taken, Review fixes, For later tickets
```

- **Order comes from `Blocked by`**, not from numbers. A ticket is *ready* when it is open and every ticket it is blocked by is resolved. Lowest number wins.
- **Status lives only in the ticket files.** `map.md` never repeats it.
- **The Answers are the handoff between subagents.** The next builder reads the Answers of the tickets it depends on.
- `settle` tickets record a decision. `convert` tickets migrate something and must be safe to run twice.
- **A worker may change only** its own Status line and Answer, lines appended to `map.md` and `learnings.md`, and the code the ticket calls for. Rewriting its own Done when, editing another ticket, or touching `commands.md` fails the guard.
- `Floor:` categories: `skip`, `suppress`, `empty-catch`, `test-delete`, `threshold`, `config`, `ticket-edit`, `commands-edit`. The line is read from the ticket as it was before the work started, so a worker cannot excuse itself.
- The guard needs the plan to be tracked by git. If you keep tickets in an ignored folder, it cannot see changes to them.
- The commands in `commands.md` run with nobody watching and must exit non zero on failure.

## See the graph

```bash
bash scripts/flow-view.sh csv-export            write the page and open it
bash scripts/flow-view.sh csv-export --watch    keep it updating while tickets are built
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
- `flow-status.sh <feature> --json` prints the same data for other tools. Mermaid (`--mermaid`) remains the choice for pull requests, because GitHub renders it.

## Long features and handoff

A session's context fills up, so the flow moves to a fresh session every few tickets. After `FLOW_TICKETS_PER_SESSION` tickets (default 4) pass review, `next` prints a `HANDOFF` line instead of the next ticket, for example `HANDOFF /feature-flow csv-export`. The session stops and tells you to open a new session and type that line. The new session picks up exactly where the last one stopped. Set `FLOW_TICKETS_PER_SESSION=0` to never hand off.

- **One owner at a time.** `start` gives the session a token, and every later call must carry it, so two sessions can never drive the same feature. `HANDOFF` and `DONE` release it.
- **Resuming after a closed session.** If a session ended without `HANDOFF` (you closed it, it crashed, it ran out of budget), the feature is still owned by it, and a new session stops and says so. Once you are sure the old session is gone, answer yes when the new session asks, or start it with `FLOW_TAKEOVER=1`. With `auto` the skill never takes over on its own.
- **Relay mode.** `FLOW_RELAY=1` hands off after every build and every review, so each phase gets a session of its own.
- **Nobody needs to watch.** With `auto` the skill asks nothing, and a Claude Code cloud session keeps working while you are away. You only come back to type the `HANDOFF` line.

The state lives in `.feature-flow/state/` (the state, a log of every step, and the last review reply). That folder ignores itself, so it never shows up in `git status`, and a normal Codex session can write it, which it cannot do under `.git`.

### Commands and settings

```bash
python3 scripts/flow.py <feature> start|next|prompt|verdict <file>   the conductor (the skill runs it)
bash scripts/flow-status.sh <feature>                  table of tickets and which are READY
bash scripts/flow-status.sh <feature> --next           path of the next ready ticket (exit 10 = done, 11 = stuck)
bash scripts/flow-status.sh <feature> --counts         one line of counts
bash scripts/flow-status.sh <feature> --check          cycles, missing blockers, missing Done when, unordered mentions
bash scripts/flow-status.sh <feature> --mermaid        the ticket graph, coloured by status (add "plain" for none)
bash scripts/flow-status.sh <feature> --json           every ticket with status, blockers and readiness
bash scripts/flow-view.sh <feature> [--watch]          the animated graph page, opened in your browser
bash scripts/gate.sh <feature>                         run Build, Test and Lint from commands.md
bash scripts/floor-guard.sh <feature> <NN> [base]      check a ticket's diff, run from the repo root
```

`scripts/flow-status.py`, `gate.py` and `floor-guard.py` are Python ports of the bash scripts of the same name and print the same output. The bash versions go once the port is finished.

`flow-status.sh` also understands the `.scratch/<feature>/issues/` layout and the statuses `done`, `ready-for-agent`, `ready-for-human` and `closed`: `FLOW_DIR=.scratch FLOW_TICKETS=issues`.

| Variable | Default | Meaning |
|---|---|---|
| `FLOW_TICKETS_PER_SESSION` | `4` | tickets per session before `HANDOFF`; `0` never hands off |
| `FLOW_RELAY` | `0` | `1` hands off after every build and every review |
| `FLOW_TAKEOVER` | unset | `1` lets `start` take a feature over from a session that is gone |
| `FLOW_MAX_RETRIES` | `2` | builds or reviews per step before the run stops |
| `FLOW_MAX_REVIEW_ROUNDS` | `3` | times a ticket may be sent back before the run stops |
| `FLOW_GATE` | `on` | `off` skips Build, Test and Lint after each ticket |
| `FLOW_SMOKE` | the `Smoke:` line of `commands.md` | command run before every ticket; the run stops if it fails |
| `FLOW_DIR`, `FLOW_TICKETS` | `plans`, `tasks` | where the plans and the ticket folder live |
| `FLOW_NO_OPEN` | unset | `1` makes `flow-view.sh` never open a browser |
| `FLOW_WATCH_SECONDS` | `3` | how often `flow-view.sh --watch` rewrites the page |

The run also stops on its own after a number of steps that grows with the ticket count, so a loop of failures cannot go on forever.

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

Offline and free: no model is called. The suite covers the conductor's every answer and how a run stops, sessions, handoff and takeover, a `.git` the agent cannot write, the gate, the floor guard, plan protection, the prompts and guides, both skills, the installer for both agents, the graph page and its data, and the acceptance harness. The page's layout and replay logic are also tested under Node (`tests/viewer-logic.test.js`, skipped when Node is absent). `.github/workflows/tests.yml` runs it on every push to `main` and every pull request, on Ubuntu (once with `mawk`, once with `gawk`) and on macOS.

`RUN_REAL=1 bash tests/smoke-real.sh --interactive` is the acceptance run with Claude Code. It runs real sessions on the demo project and spends money, which is why it asks for `RUN_REAL=1`.

## Upgrading

Earlier versions had seven skills and an unattended loop. The five flow skills are gone, and `/feature-flow` replaces them:

- `plan-feature` → `/feature-flow <feature>` before a plan exists.
- `/next-phase` and `/review-ticket` → `/feature-flow <feature>`, which runs a builder and a fresh reviewer subagent for every ticket.
- `show-flow` → `/feature-flow <feature> show`.
- `/run-flow` and `scripts/auto-flow.sh` → `/feature-flow <feature> auto`, with a `HANDOFF` every few tickets. There is no cost log any more.

The installer never deletes the old skill folders, but it names any it finds. Delete them from `.claude/skills/` or `.agents/skills/` yourself.

## Caution

The builder subagent has edit and shell access and commits after each ticket. Each ticket costs at least two subagents. Build on a branch you can throw away. Ignore build output in `.gitignore`, because the conductor stops if the tree is dirty after a ticket. The gate runs your Build, Test and Lint commands with no time limit. The floor guard is pattern matching: it can miss things and it can raise false alarms, and `Floor: allow` is the release valve. The run stops on its own when a ticket stays unresolved, when the smoke test or the gate keeps failing, when a ticket keeps failing review, or when it reaches its step limit.

## License

MIT. See `LICENSE`.
