# Interactive flow — Spec

## Problem

Feature Flow runs a planned feature in two ways today. `/next-phase` does one ticket in the session you are typing in. `/run-flow` starts `scripts/auto-flow.sh`, which runs every ticket in separate headless `claude -p` or `codex exec` processes. The headless loop is where most of the complexity lives: 422 lines of `auto-flow.sh`, a CLI adapter per agent (`run_claude`, `run_codex`), cost logs and budgets, a Codex CLI flag surface that changes under it, and a large fake-CLI test harness. The two follow-up plans make it bigger still: `plans/in-session-mode` adds a second state machine (`flow-step.sh`) that must stay in parity with `auto-flow.sh`, and `plans/portable-runtime-skills` adds canonical metadata, two renderers, a Codex preflight, structured reviews, review worktrees and commit checks, mostly to keep seven skills and the headless loop working in two runtimes.

Users also see seven skills in their agent, copied into every repo, and rewritten for Codex by `adapters/codex/skill.awk`.

## Goal and the bar

One interactive way to run a feature, in one skill. The user types `/feature-flow <feature>` in Claude Code (or `$feature-flow <feature>` in Codex), locally or in the cloud. A script, `scripts/flow.py`, owns the order of phases and the limits and tells the session what to do next. The session hands each build and each review to a fresh subagent. When a session has done enough tickets, the script tells it to hand off, and the user continues in a new session with one line. Where a runtime cannot start subagents, every phase runs in its own session through the same handoff. The headless loop is removed.

The bar: `RUN_REAL=1 FLOW_TICKETS_PER_SESSION=1 bash tests/smoke-real.sh --interactive` runs `claude -p "/feature-flow hello auto"` twice on the demo project. The first session builds and reviews ticket 01 and stops on `HANDOFF`; the second resumes and finishes ticket 02. It ends with both tickets resolved, a clean tree, the gate and the floor guard run after each ticket, a reviewer subagent's `REVIEW: PASS` for each, a list of `ok` checks, no `FAIL`, and exit 0.

## Stories

### Run a feature from one skill

**As a** Claude Code or Codex user, **I want** to type one skill name with a feature and have it plan or build, **so that** I don't learn seven commands and my agent isn't crowded with skills.

- [ ] With no plan, the skill plans the feature with me (today's `plan-feature`).
- [ ] With a plan, it drives the tickets: builder subagent, gate, floor guard, reviewer subagent, in that order, every time.
- [ ] `show` draws the graph (today's `show-flow`).

### Trust the order

**As the** author of a feature, **I want** the order of phases to come from a script that reads the repo, **so that** a session that skips or forgets a step cannot get a ticket past the gate, the guard or the review.

- [ ] The session never decides the next step; it asks `flow.py` and does what it is told.
- [ ] The script judges build, gate and floor guard from the ticket file and git. The review verdict is the one thing the session relays.

### Keep going across sessions

**As a** user with a long plan, **I want** the session to stop at a clean point and give me one line to continue, **so that** a growing context never degrades the work.

- [ ] After `FLOW_TICKETS_PER_SESSION` tickets (default 4), the next step is `HANDOFF` with the exact line to type in a new session.
- [ ] A new session started with that line, or any session started on the same feature, resumes where the last one stopped, including after a crash or a closed window.
- [ ] In relay mode, for runtimes without subagents, every phase hands off, so each build and each review still gets a fresh context.

## Scope

In: `scripts/flow.py` (conductor, prompts, handoff); runtime-neutral guides for planning, building and reviewing; one `feature-flow` skill for Claude Code and one for Codex, written by hand; the installer installing only that skill plus the role files, scripts and guides; removing the headless loop; the README; one paid Claude acceptance run and one hand-run Codex check.

Not in scope:
- Fetching feature-flow at run time from a pinned tag, or a PyPI package for the CLI. Delivery stays `install.sh` in this plan; distribution is its own later plan once `flow.py`'s commands are stable.
- Porting the existing bash scripts (`flow-status.sh`, `gate.sh`, `floor-guard.sh`, `flow-view.sh`, `install.sh`) to Python. That is `plans/interactive-flow-python`, which starts once this plan has removed the headless loop, so dead code is never ported. The new conductor is written in Python from the start, so nothing new is written twice.
- `architect-review` and `automation-design`. They are standalone skills, not part of the ticket loop, and stay as they are.
- A server, MCP or otherwise.
- Measuring a session's context percentage, unless ticket 02 finds a runtime exposes it. The handoff is count based because the script can count reliably and a model cannot measure its own context.

## Happy path

1. `/feature-flow csv-export` with no `plans/csv-export/` → the session follows `guides/plan.md` with the user, writes and validates the plan, then stops with the exact files and suggested commit command. It does not claim that the flow is ready while the plan is uncommitted.
2. After the user commits the plan, `/feature-flow csv-export` again → the skill checks a clean tree, a valid plan and the installed roles, runs `python3 scripts/flow.py csv-export start`, keeps the returned session token for every conductor call, says what will happen, and asks (skipped with `auto`).
3. `python3 scripts/flow.py csv-export next` → `BUILD plans/csv-export/tasks/01-types.md 01 <sha>` → `python3 scripts/flow.py csv-export prompt` prints the builder prompt → the session spawns a builder subagent with it → the subagent builds, proves and commits the ticket.
4. `next` → the script sees the ticket resolved and the tree clean, runs the gate and the floor guard, prints `REVIEW …` → `prompt` prints the reviewer prompt → reviewer subagent → the session saves the reply and runs `flow.py csv-export verdict <file>`.
5. `REVIEW: PASS` → `next` prints the next `BUILD`, until it prints `DONE`, or `HANDOFF /feature-flow csv-export` after four tickets.
6. The user opens a new session and types that line → step 2 again, resuming at the next ticket.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| The builder returns but the ticket is not resolved | stale claim reset, BUILD again, STOP after 2 attempts | 03 |
| The gate or the floor guard fails | findings written into the ticket and committed, BUILD again, STOP on the 4th failure | 03 |
| The tree is dirty after a resolved ticket | STOP | 03 |
| The reviewer says `REVIEW: FAIL` | findings with the source "independent review", BUILD again, same round counter | 04 |
| The reviewer's reply has no verdict | REVIEW again, STOP after 2 attempts | 04 |
| The reviewer dirtied the tree or committed a tracked change | STOP | 04 |
| The run limit is passed | STOP | 04 |
| `verdict` with no review pending | exit 2, nothing changes | 04 |
| `FLOW_TICKETS_PER_SESSION` tickets passed since `start` | `HANDOFF <line>`, exit 0 | 06 |
| A second session starts while one owns the feature | STOP with the owner token; it cannot reset or duplicate the phase | 06 |
| A session dies mid-build or mid-review | a new session explicitly takes over, then `next` judges the repo and continues; the attempt counts | 06 |
| Relay mode (`FLOW_RELAY=1`) | `HANDOFF` after every BUILD and every REVIEW, with the line for the next phase | 06 |
| The two roles are not installed (Claude) | the skill stops and says to run the installer | 07 |
| Codex cannot start subagents | the Codex skill runs in relay mode | 08 |
| An old install has the seven skills | the installer reports them as no longer installed and leaves them | 09 |

## Design

```
   you ─ /feature-flow f ─► [session: the one skill]
                              │   ▲
          start / next /      ▼   │  PLAN | BUILD | REVIEW | DONE | STOP | HANDOFF
          prompt / verdict  [scripts/flow.py]
                             reads plans/ + git, runs gate + floor guard,
                             state + session owner in .git/flow-<f>.state,
                             log in .git/flow-<f>.log
                              │
        BUILD  ─► builder subagent  (prompt = role + guides/build.md + ticket) ─► commits
        REVIEW ─► reviewer subagent (prompt = role + guides/review.md + ticket + sha)
                   ─► reply ─► verdict FILE
        HANDOFF ─► session stops; user types the printed line in a new session
```

Relay mode (no subagents): the same lines, but `flow.py` prints `HANDOFF` after each BUILD and REVIEW, and the new session does that one phase itself with the prompt from `prompt`.

### Decisions

- **Interactive only** — options: keep both modes, headless only, interactive only. Chosen: interactive only. Why: one state machine instead of two, no CLI adapters or flag preflight, and Claude cloud sessions already keep working with nobody watching. Cost: no terminal-driven overnight runs, and a runtime with neither subagents nor sessions cannot run the flow.
- **Language** — options: write the new conductor in bash and port it later, port everything first, or write new code in Python now and port the rest after. Chosen: new code in Python now (`feature_flow/` package, standard library only, Python 3.9+), existing bash ported by `plans/interactive-flow-python`. Why: nothing is written twice, `auto-flow.sh` is deleted rather than ported, and the package is ready for a later PyPI release. The black-box checks in `tests/run.sh` work for either language. Note: Python does not remove the need to pass `FLOW_SESSION` on every call; each agent command runs in a fresh shell whatever the language.
- **Who decides the order** — a conductor script the session has to ask (as in `plans/in-session-mode` Decision C). Why: it needs no harness feature and does not depend on the model's obedience.
- **One skill, guides as data** — options: seven skills per runtime with renderers, or one skill and guide files the script prints. Chosen: one skill. Why: the only runtime-specific text is how to spawn a subagent and how the skill is invoked, so two hand-written skills replace `skill.awk`, the renderers and the parity checker.
- **Handoff trigger** — options: context percentage, ticket count. Chosen: ticket count (`FLOW_TICKETS_PER_SESSION`, default 4), at a ticket boundary. Why: the script can count; neither runtime is known to tell a session its context usage. Ticket 02 checks; the skill may add an early handoff if it can.
- **State** — `.git/flow-<feature>.state` and `.git/flow-<feature>.log`. The state includes a session-owner token and the `HEAD` at which review began. Why: it survives a closed session, never dirties the tree, makes resume and relay possible, prevents two sessions from driving the same feature, and detects reviewer commits as well as dirty files.
- **Session ownership** — `start` creates an owner token. Every later command must present it. A second session stops unless the user explicitly authorizes takeover; `HANDOFF` releases the owner. Why: automatically treating every outstanding phase as a crashed session can start duplicate builders while the first session is still alive.
- **Review independence** — a fresh subagent, or a fresh session in relay mode, with no Edit or Write tools where the runtime allows it. The script STOPs if the tree is dirty or `HEAD` differs from the saved review-start SHA.

## Interfaces

`python3 scripts/flow.py <feature> <command>`; every command prints one line on stdout.

- `start` — marks a new session (resets the per-session ticket count), prints `OK <session-token>` or `PLAN` when the plan folder is missing. With an existing owner it prints `STOP`; `FLOW_TAKEOVER=1` explicitly replaces that owner after a crashed or closed session.
- `next` — `BUILD <ticket> <NN> <base-sha>`, `REVIEW <ticket> <NN> <base-sha>`, `DONE <summary>`, `HANDOFF <line to type>` (exit 0), or `STOP <reason>` (exit 1).
- `prompt` — the full prompt for the phase `next` last printed: role text, guide, ticket path, sha. Multi-line, plain text, runtime neutral.
- `verdict <file>` — records the reviewer's reply; `OK` or `RETRY no review verdict`; exit 2 when no review is pending.

Environment: `FLOW_DIR`, `FLOW_TICKETS`, `FLOW_MAX_RETRIES` (2), `FLOW_MAX_REVIEW_ROUNDS` (3), `FLOW_GATE`, `FLOW_SMOKE`, `FLOW_TICKETS_PER_SESSION` (4), `FLOW_RELAY` (0), `FLOW_INVOKE` (the line printed in `HANDOFF`, set by the skill: `/feature-flow` or `$feature-flow`), `FLOW_SESSION` (the token returned by `start`), and `FLOW_TAKEOVER` (0; set to 1 only after explicit user confirmation).

## Migration and compatibility

This plan replaces `plans/in-session-mode` and `plans/portable-runtime-skills`. Their useful parts move here: the subagent probe and the conductor from in-session-mode; nothing from the Codex hardening tickets, which only exist for the headless loop. Ticket 10 deletes both folders along with the rest of the headless flow.

`install.sh` keeps its options. It stops installing `plan-feature`, `next-phase`, `review-ticket`, `run-flow` and `show-flow` and installs `feature-flow`; existing copies in a user's repo are reported, never deleted. Nothing headless is kept: ticket 10 deletes `auto-flow.sh`, `/run-flow`, the old skills, the cost log, the headless settings and their tests, and checks the whole repo for leftovers. `scripts/auto-flow.sh` is removed only after both the Claude acceptance run and a successful Codex hand run pass.

## Risks

- A subagent cannot do what the protocol assumes — tickets 01 and 02 settle it before anything depends on it.
- Codex has no subagents and relay mode is tedious (two sessions per ticket) — acceptable as a fallback; the Codex check in ticket 13 measures it.
- A user opens the feature in two sessions — the session-owner token stops the second driver; takeover is explicit so crash recovery cannot silently duplicate live work.
- The review verdict is relayed by the session — a session could write `REVIEW: PASS` itself. The script verifies everything else from the repo; the README says so plainly.
- Users who relied on `/run-flow` lose it — the README says what replaced it and that a cloud session runs unattended.
- One skill triggers less precisely than seven — the skill is explicit-invocation only, so it runs when named.
