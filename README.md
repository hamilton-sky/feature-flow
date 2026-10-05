# Feature flow skills for Claude Code

Plan a feature as a graph of small tickets, then work the tickets one at a time or unattended. Every ticket is built by one session and checked by another, scripts check the build and watch for work that weakens the checks, and the whole run has cost and turn limits.

6 skills, 2 agents, 4 scripts, an installer and a test suite. MIT licensed.

## Install

```bash
bash install.sh /path/to/repo            # skills and agents into the repo's .claude/, scripts into scripts/
bash install.sh /path/to/repo --user     # skills and agents into ~/.claude/ for every project, scripts still into the repo
bash install.sh /path/to/repo --dry-run  # show what would change, write nothing
```

It never deletes anything. A file that already exists and differs is kept and reported; `--force` replaces it. Install `jq` if you want the cost log.

## Skills and agents

| Skill | What it does |
|---|---|
| `plan-feature` | Writes `plans/<feature>/` with a spec, a map, commands, learnings and tickets. Drops tickets that need not exist, shows you the graph, and waits for a yes first. |
| `next-phase` | Works the next ready ticket: claims it, builds it (test first when the ticket says so), proves each Done-when with fresh output, writes the Answer, commits with `auto`. |
| `review-ticket` | Reviews one finished ticket in a fresh session. Sees the ticket and the diff, not the author's account. Ends with `REVIEW: PASS` or `REVIEW: FAIL`. Refuses to review in a session that wrote the change. |
| `run-flow` | Runs every remaining ticket unattended: smoke test, build, gate, floor guard, review, repeat. |
| `architect-review` | Architecture review of a file, diff or feature, with severity rated findings. Reads CLAUDE.md for the project's own rules. |
| `automation-design` | Blueprint for an automation pipeline. Hands off to `plan-feature`. |

| Agent | Tools | Role |
|---|---|---|
| `ticket-builder` | Read, Glob, Grep, Edit, Write, Bash | Runs `next-phase` in a lean session. |
| `ticket-reviewer` | Read, Glob, Grep, Bash (no Edit, no Write) | Runs `review-ticket`. The harness enforces that it cannot edit. |

The skills hold the protocol. The agents add what a skill cannot: tool limits the harness enforces, a model setting, and a much smaller starting context. The loop uses them automatically when they are installed.

```
/plan-feature csv-export        plan it
/next-phase csv-export          do one ticket, you watch
/review-ticket csv-export 02    have a fresh session check ticket 02
/run-flow csv-export            do all of them unattended
```

## What a plan looks like

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

## How one ticket flows

```
 smoke command (script): is the base healthy?   no ─► stop, spend nothing
        │ yes
        ▼
 pick ticket ─► claim ─► build ─► prove it (run fresh, read the output)
        (ticket-builder agent)                │
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
 fresh reviewer (ticket-reviewer agent): sees only the              │
 ticket + diff, re-runs every Done when                       FAIL ─┤
                                              │ PASS                ▼
                                              ▼        findings written into the ticket,
                         Answer written, resolved      reopened, built again (3 rounds max)
                         and committed
```

## The ticket format

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
- **The Answers are the handoff between sessions.** The next worker reads the Answers of the tickets it depends on.
- `settle` tickets record a decision. `convert` tickets migrate something and must be safe to run twice.
- **A worker may change only** its own Status line and Answer, lines appended to `map.md` and `learnings.md`, and the code the ticket calls for. Rewriting its own Done when, editing another ticket, or touching `commands.md` fails the guard.
- `Floor:` categories: `skip`, `suppress`, `empty-catch`, `test-delete`, `threshold`, `config`, `ticket-edit`, `commands-edit`. The line is read from the ticket as it was before the work started, so a worker cannot excuse itself.
- The guard needs the plan to be tracked by git. If you keep tickets in an ignored folder, it cannot see changes to them.
- The commands in `commands.md` run unattended and must exit non zero on failure.

## Scripts

```bash
bash scripts/flow-status.sh <feature>                  table of tickets and which are READY
bash scripts/flow-status.sh <feature> --next           path of the next ready ticket (exit 10 = done, 11 = stuck)
bash scripts/flow-status.sh <feature> --counts         one line of counts
bash scripts/flow-status.sh <feature> --check          cycles, missing blockers, missing Done when, unordered mentions
bash scripts/flow-status.sh <feature> --mermaid        the ticket graph, coloured by status (add "plain" for none)
bash scripts/gate.sh <feature>                         run Build, Test and Lint from commands.md
bash scripts/floor-guard.sh <feature> <NN> [base]      check a ticket's diff, run from the repo root
bash scripts/auto-flow.sh <feature>                    the unattended loop
```

Settings, all optional environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `FLOW_DIR`, `FLOW_TICKETS` | `plans`, `tasks` | where the plans and the ticket folder live |
| `FLOW_MAX_TOTAL_USD` | unset | stop the run when its total cost passes this (needs `jq`) |
| `FLOW_MAX_BUDGET_USD` | unset | per session, passed as `--max-budget-usd` |
| `FLOW_MAX_TURNS` | unset | per session, passed as `--max-turns` |
| `FLOW_MAX_RETRIES` | `2` | sessions per step before the run stops |
| `FLOW_MAX_REVIEW_ROUNDS` | `3` | times a ticket may be sent back before the run stops |
| `FLOW_REVIEW` | `on` | `off` skips the reviewer session and keeps the gate and the floor guard |
| `FLOW_GATE` | `on` | `off` skips Build, Test and Lint after each ticket |
| `FLOW_AGENTS` | `auto` | `auto` uses the agents when installed, `on` requires them, `off` never uses them |
| `FLOW_MODEL`, `FLOW_REVIEW_MODEL` | unset | model for building, model for reviewing (a different one removes some self-agreement) |
| `FLOW_SMOKE` | the `Smoke:` line of `commands.md` | command run before every ticket; the run stops if it fails |
| `FLOW_COST` | `on` | `off` turns the cost log off; the log is `.git/flow-cost-<feature>.log` |
| `FLOW_CLAUDE_ARGS` | unset | extra flags for every session, e.g. `--setting-sources project,local` |
| `FLOW_ALLOWED_TOOLS` | `Edit,Write,Read,Glob,Grep,Bash` | tools each building session may use (reviewers get read only tools plus Bash) |

`flow-status.sh` also understands the `.scratch/<feature>/issues/` layout and the statuses `done`, `ready-for-agent`, `ready-for-human` and `closed`: `FLOW_DIR=.scratch FLOW_TICKETS=issues`.

## Where it runs

```
 layer          what                                   works with
 1 plan files   tickets, spec, map, commands           anything, it is markdown
 2 scripts      flow-status, gate, floor-guard         anything with bash, git and awk
 3 skills       plan-feature, next-phase, ...          Claude Code (SKILL.md, slash commands)
 4 the loop     auto-flow.sh                           calls `claude -p`
```

- **Headless** (`claude -p`): tested for real. This is what the loop does.
- **Interactive**: the skills are meant to be typed in a normal session. Only the headless path has been tested for real.
- **Claude Code on the web, Codex and other harnesses**: not tested. Layers 1 and 2 are portable as they are. Layer 3 uses Claude Code features (`disable-model-invocation`, `$ARGUMENTS`, `--allowedTools`), and layer 4 calls `claude`.
- Tested on macOS (BSD awk, bash 3.2). Not yet tried on Linux.

## What a session costs

Measured with the cheapest model and a one-word reply, in tokens of context before the session did anything:

| Session | Starting context |
|---|---|
| Default Claude Code session on one machine | 43,041 |
| Run as the `ticket-builder` agent (edit, write, shell) | 7,007 |
| Run as a read only agent like `ticket-reviewer` | 4,536 |

The default session pays for Claude Code's full prompt and tool list, your skills, MCP tools and hooks. A session run with `--agent` pays only for its own small prompt and its own tools, and slash command skills still work in it. That is why the loop uses the agents when they are installed. `--bare` goes lower but needs an `ANTHROPIC_API_KEY`.

Every ticket still costs at least two sessions (build and review). Use `FLOW_REVIEW_MODEL` for a cheaper reviewer, `FLOW_REVIEW=off` for low risk work, and read the cost log to see where the money went.

## Tests

```bash
bash tests/run.sh
```

154 checks, offline, no cost. A fake `claude` stands in for the real one, so the suite covers the loop, the retries, the stale claim reset, the gate, the guard, the plan protection, the review rounds, the agents, the cost log and caps, the smoke test, the installer, and every way a run should stop. The checks were also run against deliberately broken copies of the code to confirm they fail when they should. `.github/workflows/tests.yml` runs the suite on every push to `main` and every pull request, on Ubuntu (once with `mawk`, once with `gawk`) and on macOS. `tests/smoke-real.sh` installs everything into a throwaway project and runs two tickets through the real `claude`; it spends money, so it asks you to set `RUN_REAL=1`.

## Caution

`auto-flow.sh` runs headless sessions with edit and shell access and commits after each ticket. Each ticket costs at least two sessions. Run it on a clean branch you can throw away, set `FLOW_MAX_TOTAL_USD`, and narrow `FLOW_ALLOWED_TOOLS` where you can. Ignore build output in `.gitignore`, because the loop stops if the tree is dirty after a ticket. The gate runs your Build, Test and Lint commands with no time limit. The floor guard is pattern matching: it can miss things and it can raise false alarms, and `Floor: allow` is the release valve. The run stops on its own when a ticket stays unresolved, when the smoke test or the gate keeps failing, when a ticket keeps failing review, or when it reaches a limit.

## License

MIT. See `LICENSE`.
