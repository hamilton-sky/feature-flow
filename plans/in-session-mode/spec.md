# In-session mode — Spec

## Problem

Two ways to run a planned feature exist today. `/next-phase` runs one ticket in the session you are typing in: you start every ticket, that session is the builder, and the independent review is a separate headless process you have to ask for. `/run-flow` runs everything, but in separate headless `claude -p` processes started by `scripts/auto-flow.sh`, so you cannot watch the phases in the conversation you are in.

There is no way to say "do all the tickets" in one interactive Claude Code session and watch a builder subagent and a reviewer subagent do each phase in that same conversation, with the order of the phases guaranteed.

## Goal and the bar

`/drive-flow <feature>` completes a planned feature inside one Claude Code session. It hands each phase to a fresh subagent, in an order that a script enforces.

The bar: `RUN_REAL=1 bash tests/smoke-real.sh --drive` runs `claude -p "/drive-flow hello auto"` on the demo project. It ends with both tickets resolved, a clean tree, the gate and the floor guard run after each ticket, and a reviewer subagent's `REVIEW: PASS` for each. It prints the usual list of `ok` checks, no `FAIL`, and exits 0.

## Stories

### Drive a feature from one session

**As a** Claude Code user, **I want** to type `/drive-flow csv-export` and watch each ticket go builder, gate, floor guard, reviewer, **so that** I see the whole run in one conversation without starting separate processes.

- [ ] Each ticket goes through the phases in that order, every time, whatever the session does or forgets.
- [ ] A failing gate, floor guard or review writes its findings into the ticket as `## Review findings (round N, source)`, and a fresh builder subagent fixes them, up to `FLOW_MAX_REVIEW_ROUNDS` (3) rounds.
- [ ] With `auto` (`/drive-flow csv-export auto`) it asks nothing, like `/next-phase ... auto`, so it can run headless.
- [ ] It stops, and says why, when no ticket is ready, a ticket stays unresolved after `FLOW_MAX_RETRIES` (2) attempts, the review rounds run out, the tree is dirty after a ticket, or the run limit is reached.

### Trust the order

**As the** author of a feature, **I want** the order of phases to come from a script that reads the repo, **so that** a model that skips or forgets a step cannot get a ticket past the gate, the guard or the review.

- [ ] The session never decides the next step. It asks `scripts/flow-step.sh` and does what it is told.
- [ ] The script judges what happened from the ticket file and git, not from the session's account. The only thing the session reports is the reviewer's reply, and the script cannot prove that a reviewer wrote it (see Risks).

## Scope

In: the conductor script `scripts/flow-step.sh`; the `drive-flow` skill for Claude Code; the installer leaving it out for Codex; the README; one real acceptance run.

Not in scope:
- A Codex same-session mode. It needs its own probe of whether Codex lets a session spawn agents, so it is a later round.
- Refactoring `scripts/auto-flow.sh` to share code with the conductor. The working loop stays as it is.
- Per phase cost logging. The cost log only knows whole `claude -p` sessions.
- A plugin.

## Happy path

1. `/drive-flow csv-export` → the session checks a clean tree and a valid plan, says what it will do and what it costs, and asks → you say yes. With `auto` it says the same and does not ask.
2. The session runs `bash scripts/flow-step.sh csv-export next` → it prints `BUILD plans/csv-export/tasks/01-types.md 01 <sha>` → the session spawns a `ticket-builder` subagent with the prompt from the skill → the subagent builds, proves and commits the ticket.
3. The session runs `next` again → the script sees the ticket resolved and the tree clean, runs the gate and the floor guard itself, logs `GATE-PASS` and `GUARD-PASS`, and prints `REVIEW plans/csv-export/tasks/01-types.md 01 <sha>` → the session spawns a `ticket-reviewer` subagent, saves its reply to a file and runs `flow-step.sh csv-export verdict <file>`.
4. `REVIEW: PASS` → the next `next` prints the next `BUILD`, until it prints `DONE`.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| The builder returns but the ticket is not resolved | stale claim reset, BUILD again, STOP after 2 attempts | 02 |
| The gate or the floor guard fails | findings written into the ticket and committed, BUILD again, STOP after 3 rounds | 02 |
| The reviewer says `REVIEW: FAIL` | same, with the source "independent review" | 03 |
| The reviewer's reply has no verdict | ask again, STOP after 2 attempts | 03 |
| The reviewer changed a tracked file | STOP | 03 |
| The tree is dirty after a resolved ticket | STOP | 02 |
| The run limit is passed | STOP | 03 |
| `verdict` is called when no review is pending | exit 2, nothing changes | 03 |
| The two agents are not installed | the skill stops and says to run the installer | 04 |
| A headless run (`claude -p`), nobody to answer | `auto` skips the confirmation | 04 |
| A Codex user installs | the skill is not installed for Codex | 05 |

## Design

```
   you ─ /drive-flow f ─► [session]
                            │   ▲
                   next     ▼   │  BUILD | REVIEW | DONE | STOP
                      [scripts/flow-step.sh]
                       reads ticket + git, runs gate + guard,
                       state in .git/flow-step-f.state
                            │
        BUILD  ─► [ticket-builder subagent]  ─► commits the ticket
        REVIEW ─► [ticket-reviewer subagent] ─► reply ─► verdict FILE
```

### Decisions

- **Who decides the order** — options: A, instructions in the skill only; B, hooks that block out of order tool calls; C, a conductor script the session has to ask. Chosen: C. Why: it is the trick that makes the loop reliable (a script owns the order), it needs no harness feature, and it carries over to Codex later. A depends on the model's obedience and B on hook behaviour nobody has checked here.
- **Where the state lives** — options: the conversation, a tracked file, an untracked file under `.git`. Chosen: `.git/flow-step-<feature>.state`. Why: it survives a closed session and never dirties the tree, like the cost log and the graph page.
- **How a subagent gets the protocol** — the two agents have no Skill tool, so the prompt tells them to read the skill file and follow it. To be confirmed by the first ticket.
- **Duplicate policy** — the conductor repeats the loop's retry, round and run limit rules instead of sharing code with `auto-flow.sh`. Why: refactoring the working loop is out of scope and risky. Cost: the two can drift, so ticket 03 adds a parity test that runs both on the same scenarios and compares their STOP lines.
- **Round counting** — one round counter per ticket, shared by the gate, the floor guard and the review, exactly as in `auto-flow.sh`: it goes up on every failure, and the STOP comes on the failure that takes it past `FLOW_MAX_REVIEW_ROUNDS` (the 4th failure with the default 3). The STOP names the source of that last failure.
- **Ticket order** — the Codex exclusion (ticket 05) lands before the skill (ticket 04). A new skill marked `disable-model-invocation: true` changes two existing Codex install checks, so the skill cannot pass `bash tests/run.sh` until the exclusion exists.

## Interfaces

`bash scripts/flow-step.sh <feature> next` prints one line and exits 0 (`BUILD <ticket> <NN> <base-sha>`, `REVIEW <ticket> <NN> <base-sha>` or `DONE ...`), or prints `STOP <reason>` and exits 1.

`bash scripts/flow-step.sh <feature> verdict <file>` records the reviewer's reply and exits 2 when no review is pending. `<file>` may be `-` to read the reply from stdin, so the session never has to write a file under `.git`.

Every printed line, and every gate and floor guard result, is appended to `.git/flow-step-<feature>.log` as `HH:MM:SS,<NN>,<EVENT>`. Events: `BUILD`, `REVIEW`, `DONE`, `STOP`, `GATE-PASS`, `GATE-FAIL`, `GATE-OFF`, `GUARD-PASS`, `GUARD-FAIL`, `VERDICT-PASS`, `VERDICT-FAIL`, `VERDICT-NONE`. The acceptance run reads this log, because a drive run has no `auto-flow.sh` output to grep.

The details may change after the first ticket, which settles what a subagent can do.

## Risks

- A subagent cannot do what the protocol assumes — the first ticket settles it before anything is built.
- The conductor and `auto-flow.sh` drift apart — they share the scripts they call, and the map keeps a parity test as an open question.
- The session ignores the script — it can skip work, but the script judges the build, the gate and the floor guard from the repo, so a ticket that was not built or does not pass them never advances.
- The session fakes the review — the verdict is relayed by the session, so a session that writes `REVIEW: PASS` itself would advance the ticket, and the script cannot detect it. The skill forbids it and the README says so plainly: this mode trusts the session for the review; the headless loop does not.
- The session's own context grows with every ticket's summary — the acceptance run measures it once.
