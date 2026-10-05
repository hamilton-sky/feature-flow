# Feature flow skills for Claude Code

[![tests](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml/badge.svg)](https://github.com/hamilton-sky/feature-flow/actions/workflows/tests.yml)

Plan a feature as a graph of small tickets, then work the tickets one at a time or unattended. Every ticket is built by one session and checked by another, scripts check the build and watch for work that weakens the checks, and the whole run has cost and turn limits.

7 skills, 2 agents, 5 scripts, an installer, a demo and a test suite. MIT licensed.

## Install

```bash
bash install.sh /path/to/repo            # skills and agents into the repo's .claude/, scripts into scripts/
bash install.sh /path/to/repo --user     # skills and agents into ~/.claude/ for every project, scripts still into the repo
bash install.sh /path/to/repo --dry-run  # show what would change, write nothing
bash install.sh /path/to/repo --agent codex   # the same skills, rewritten for Codex, into the repo's .agents/
bash install.sh /path/to/repo --agent all     # Claude Code and Codex side by side
```

`--agent` is `claude` (the default, unchanged), `codex` or `all`. It never deletes anything. A file that already exists and differs is kept and reported; `--force` replaces it. Install `jq` if you want the cost log.

**For Codex** the skills are not a second copy: they are generated from `skills/` at install time by `adapters/codex/skill.awk`, so one edit reaches both agents. The Codex copy of each skill:

- keeps only `name` and a quoted `description` in its header, and gets an `agents/openai.yaml` beside it. `next-phase`, `review-ticket`, `run-flow` and `show-flow` are marked `allow_implicit_invocation: false`, so they run only when you name them (the same job `disable-model-invocation` does in Claude Code);
- says `$next-phase csv-export auto` where Claude Code says `/next-phase csv-export auto`, and `<arguments>` where Claude Code says `$ARGUMENTS`, with one line saying what that means;
- starts the manual review with `codex exec --sandbox read-only`, putting `.agents/flow-roles/ticket-reviewer.md` in front of the prompt, because Codex has no `--agent`;
- reads `AGENTS.md` where it read `CLAUDE.md`, and tells the agent to leave changes uncommitted when the sandbox refuses git writes.

The two agents become plain role files in `.agents/flow-roles/` (never your `AGENTS.md`). With `--user` the Codex skills go to `~/.agents/skills/` (`AGENTS_HOME` overrides it); the role files and the scripts stay in the repo, because the skills call them from there.

## Skills and agents

| Skill | What it does |
|---|---|
| `plan-feature` | Writes `plans/<feature>/` with a spec, a map, commands, learnings and tickets. Drops tickets that need not exist, shows you the graph, and waits for a yes first. |
| `next-phase` | Works the next ready ticket: claims it, builds it (test first when the ticket says so), proves each Done-when with fresh output, writes the Answer, commits with `auto`. |
| `review-ticket` | Reviews one finished ticket in a fresh session. Sees the ticket and the diff, not the author's account. Ends with `REVIEW: PASS` or `REVIEW: FAIL`. Refuses to review in a session that wrote the change. |
| `run-flow` | Runs every remaining ticket unattended: smoke test, build, gate, floor guard, review, repeat. |
| `show-flow` | Shows the ticket graph as an animated page that can replay the run from git history, and summarises what is ready and what blocks the finish. |
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
/show-flow csv-export           watch the ticket graph, animated
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

## See the graph

```bash
bash scripts/flow-view.sh csv-export            write the page and open it
bash scripts/flow-view.sh csv-export --watch    keep it updating during an unattended run
bash examples/demo.sh --open                    try it on a made up project, no setup needed
```

One self contained HTML file: no server, no libraries, no network, light and dark. It is written to `.git/flow-<feature>.html`, so it never dirties the tree.

```
  01 types ──► 02 service ──► 04 acceptance        ● resolved  ◉ ready (pulses)
        └────► 03 wire ──────────┘                 ◌ being worked (spins)  ○ waiting
  ▶ replay ──●──────●─────○──────────   drag to scrub through the run
```

- **Layered left to right**, so the order of work is visible. Dashes flow along the edges into tickets that are ready to start.
- **Replay** plays the run back from git history: tickets turn green in the order they resolved, and a ticket sent back by the gate, the guard or the reviewer flashes red.
- **Hover or click** a ticket for its blockers, Done when, Answer, the rounds it was sent back, and what it cost.
- **Keys:** space plays or pauses, the arrows step, End shows now, `t` switches theme. Reduced motion is respected.
- **Safe by construction:** ticket text comes from files an agent wrote, so it is escaped when embedded and only ever inserted as text.
- `flow-status.sh <feature> --json` prints the same data for other tools. Mermaid (`--mermaid`) remains the choice for pull requests, because GitHub renders it.

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
bash scripts/flow-status.sh <feature> --json           every ticket with status, blockers and readiness
bash scripts/flow-view.sh <feature> [--watch]          the animated graph page, opened in your browser
bash scripts/gate.sh <feature>                         run Build, Test and Lint from commands.md
bash scripts/floor-guard.sh <feature> <NN> [base]      check a ticket's diff, run from the repo root
bash scripts/auto-flow.sh <feature>                    the unattended loop
```

Settings, all optional environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `FLOW_AGENT` | `claude` | `claude` or `codex`: which CLI runs the sessions (see "Running the loop with Codex") |
| `FLOW_DIR`, `FLOW_TICKETS` | `plans`, `tasks` | where the plans and the ticket folder live |
| `FLOW_NO_OPEN` | unset | `1` makes `flow-view.sh` never open a browser |
| `FLOW_MAX_TOTAL_USD` | unset | stop the run when its total cost passes this (needs `jq`; claude only) |
| `FLOW_MAX_BUDGET_USD` | unset | per session, passed as `--max-budget-usd` (claude only) |
| `FLOW_MAX_TURNS` | unset | per session, passed as `--max-turns` (claude only) |
| `FLOW_MAX_RETRIES` | `2` | sessions per step before the run stops |
| `FLOW_MAX_REVIEW_ROUNDS` | `3` | times a ticket may be sent back before the run stops |
| `FLOW_REVIEW` | `on` | `off` skips the reviewer session and keeps the gate and the floor guard |
| `FLOW_GATE` | `on` | `off` skips Build, Test and Lint after each ticket |
| `FLOW_AGENTS` | `auto` | `auto` uses the agents when installed, `on` requires them, `off` never uses them. For codex they are the role files in `.agents/flow-roles/` |
| `FLOW_MODEL`, `FLOW_REVIEW_MODEL` | unset | model for building, model for reviewing (a different one removes some self-agreement) |
| `FLOW_SMOKE` | the `Smoke:` line of `commands.md` | command run before every ticket; the run stops if it fails |
| `FLOW_COST` | `on` | `off` turns the cost log off; the log is `.git/flow-cost-<feature>.log` |
| `FLOW_CLAUDE_ARGS` | unset | extra flags for every claude session, e.g. `--setting-sources project,local` |
| `FLOW_CODEX_ARGS` | unset | extra flags for every codex session, e.g. `-c model_reasoning_effort=low` |
| `FLOW_ALLOWED_TOOLS` | `Edit,Write,Read,Glob,Grep,Bash` | tools each building session may use (reviewers get read only tools plus Bash; claude only) |

### Running the loop with Codex

```bash
FLOW_AGENT=codex bash scripts/auto-flow.sh csv-export
```

Same loop, same gate, same floor guard, same ticket file as the judge. Only the session launcher changes, and Codex is different from Claude Code in ways the loop has to work around. These were measured with Codex 0.147.0 in one probe run:

| Codex does this | So the loop does this |
|---|---|
| Has no flag to run a whole session as a named agent | The builder runs with `--sandbox workspace-write` and the reviewer with `--sandbox read-only`. The role text from `.agents/flow-roles/` goes in front of the prompt (no role files: the bare `$next-phase ...` prompt). |
| Keeps `.git` read only in `workspace-write` (`git commit` failed with `index.lock: Operation not permitted`) | The loop commits for the builder once its ticket says `resolved`: `git add -A`, then `feat(<feature>): NN <ticket title>`. Work from a ticket that is not resolved is never committed. If the agent did commit, the loop adds nothing. |
| Has no network in `workspace-write` (a DNS lookup failed) | Nothing: a builder that needs `npm install` or a download will fail its ticket. Codex can be configured to allow it (`FLOW_CODEX_ARGS`), which is untested here. |
| Exits 0 even when the task half failed | Nothing new: the ticket file decides, as with Claude. |
| Reports tokens and no dollars | The cost log gets the tokens (the last two columns) and a dollar figure of 0, and the run prints `tokens this run`. The graph page therefore shows $0 for Codex runs. No prices are invented. |
| Has no turn limit, budget limit or dollar cap | `FLOW_MAX_TOTAL_USD`, `FLOW_MAX_BUDGET_USD`, `FLOW_MAX_TURNS` and `FLOW_ALLOWED_TOOLS` do not apply and the run says so when they are set. macOS has no `timeout` command either. **Only `FLOW_MAX_RETRIES`, `FLOW_MAX_REVIEW_ROUNDS` and the run limit (a few times the ticket count) stop a runaway Codex run**, so run it on a throwaway branch. |
| Writes its last message to the `-o` file | The reviewer's `REVIEW: PASS` or `REVIEW: FAIL` is read from that file, never from the event stream. |

Not yet known: whether a read only reviewer can re-run a Done when command that writes files (a test that writes a cache, say). If it cannot, you would see a `REVIEW: FAIL` with a command error in the findings.

The loop starts new Codex sessions, so start it from your own terminal. Started from inside an interactive Codex session it is blocked by that session's sandbox (no network, `.git` read only) unless you approve running it outside the sandbox.

`flow-status.sh` also understands the `.scratch/<feature>/issues/` layout and the statuses `done`, `ready-for-agent`, `ready-for-human` and `closed`: `FLOW_DIR=.scratch FLOW_TICKETS=issues`.

## Where it runs

```
 layer          what                                   works with
 1 plan files   tickets, spec, map, commands           anything, it is markdown
 2 scripts      flow-status, gate, floor-guard, view   anything with bash, git and awk
 3 skills       plan-feature, next-phase, ...          Claude Code (slash commands), Codex (generated)
 4 the loop     auto-flow.sh                           calls `claude -p`, or `codex exec` with FLOW_AGENT=codex
```

- **Headless** (`claude -p`): tested for real. This is what the loop does.
- **Interactive**: the skills are meant to be typed in a normal session. Only the headless path has been tested for real.
- **Codex skills**: `install.sh --agent codex` generates them. Tested offline: the transform rule by rule, the installed files, and that the generated headers and `openai.yaml` parse as strict YAML. Not yet run in interactive Codex.
- **Codex loop** (`FLOW_AGENT=codex`): tested offline with a fake `codex` that models the sandbox (it cannot commit), and probed once against the real CLI.
- **Claude Code on the web and other harnesses**: not tested. Layers 1 and 2 are portable as they are.
- The test suite passes in CI on Linux (with `mawk` and with `gawk`) and on macOS. It was developed on macOS with bash 3.2.

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

413 checks, offline, no cost. A fake `claude` and a fake `codex` stand in for the real ones, so the suite covers the loop, the retries, the stale claim reset, the gate, the guard, the plan protection, the review rounds, the agents, the cost log and caps, the smoke test, the installer for both agents, and the graph page and its data, and every way a run should stop. The page's layout and replay logic are also unit tested under Node (`tests/viewer-logic.test.js`, skipped when Node is absent). The checks were also run against deliberately broken copies of the code to confirm they fail when they should. `.github/workflows/tests.yml` runs the suite on every push to `main` and every pull request, on Ubuntu (once with `mawk`, once with `gawk`) and on macOS. `tests/smoke-real.sh` installs everything into a throwaway project and runs two tickets through the real agent (`claude` by default, `FLOW_AGENT=codex` for Codex); it spends money or plan quota, so it asks you to set `RUN_REAL=1`. `bash tests/smoke-real.sh --prepare DIR` builds the same project in an empty folder, installed for the agent, and stops: no model is called, so use it to try the skills by hand.

## Caution

`auto-flow.sh` runs headless sessions with edit and shell access and commits after each ticket. Each ticket costs at least two sessions. Run it on a clean branch you can throw away, set `FLOW_MAX_TOTAL_USD`, and narrow `FLOW_ALLOWED_TOOLS` where you can. Ignore build output in `.gitignore`, because the loop stops if the tree is dirty after a ticket. The gate runs your Build, Test and Lint commands with no time limit. The floor guard is pattern matching: it can miss things and it can raise false alarms, and `Floor: allow` is the release valve. The run stops on its own when a ticket stays unresolved, when the smoke test or the gate keeps failing, when a ticket keeps failing review, or when it reaches a limit.

## License

MIT. See `LICENSE`.
