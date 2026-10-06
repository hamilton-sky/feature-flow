# Map: interactive-flow

## Destination

A Claude Code or Codex user, locally or in the cloud, types `/feature-flow <feature>` (Codex: `$feature-flow <feature>`) and the feature gets planned or built in that session. `scripts/flow.py` owns the order of phases, the limits and the handoff, and prints the prompt for each phase from runtime-neutral guides. The session hands each build and each review to a fresh subagent, or, where a runtime has none, to a fresh session through the handoff. The installer installs one skill per runtime instead of seven, `adapters/codex/skill.awk` is gone, and the headless loop (`auto-flow.sh`, `/run-flow`) is removed only after the Claude and Codex acceptance runs pass. This plan replaces `plans/in-session-mode` and `plans/portable-runtime-skills`.

**The bar.** `RUN_REAL=1 FLOW_TICKETS_PER_SESSION=1 bash tests/smoke-real.sh --interactive` runs two `claude -p "/feature-flow hello auto"` sessions on the demo project: the first ends on `HANDOFF` after ticket 01, the second finishes ticket 02. Both tickets resolved, a clean tree, gate and floor guard run after each ticket, a reviewer subagent's `REVIEW: PASS` for each: a list of `ok` checks, no `FAIL`, exit 0. Ticket 12 runs it. The old headless path is not removed until ticket 13 also records a successful Codex run.

## How to work this

- See what is ready: `bash scripts/flow-status.sh interactive-flow`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `bash scripts/flow-status.sh interactive-flow --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Work this plan with `/next-phase`, not the unattended loop. Tickets 01, 02, 12 and 13 are probes or paid runs that need a person in an interactive session, and ticket 10 deletes the loop itself.

## Decisions so far

01 - subagents work in Claude Code: name the skill file in the prompt (`Follow .claude/skills/<skill>/SKILL.md for: <args>`), agents run in the background and the final reply arrives as a notification, the parent saves it with Bash to a path outside `.git` (unattended sessions are refused there), and three `review-ticket` defects (Answer leak, fenced template, moving range) are fixed in `skills/review-ticket/SKILL.md`.
02 - Codex mode is subagents: `spawn_agent` with `fork_turns="none"` gives a builder and a reviewer separate contexts and `wait_agent` returns their replies, but a child cannot be made read-only (no sandbox or tool-list argument), so the reviewer relies on its instructions plus the conductor's dirty-tree and HEAD checks, or a fresh `codex exec --sandbox read-only` session; both runtimes show context usage in their own UI.
03 - conductor is `feature_flow/` + `scripts/flow.py`; state in `.git/flow-<f>.state`; bash checks wrapped in `checks.py`; `next` does BUILD, gate, guard, REVIEW.
04 - `verdict <file>` records PASS/FAIL/none; `next` checks reviewer edits by tracked diff + HEAD vs review sha, then sends back, re-reviews or moves on; DONE on completion.
06 - `start` issues an owner token required as FLOW_SESSION; HANDOFF after FLOW_TICKETS_PER_SESSION passes (never on the last ticket) or after every phase with FLOW_RELAY=1; takeover only with FLOW_TAKEOVER=1.
05 - runtime-neutral `guides/` (build, review, plan, show, templates) copied from the skills; `flow.py <f> prompt` pastes role + guide + filled task, finding guides beside `scripts/` or in `.feature-flow/`.
07 - one Claude skill `skills/feature-flow/SKILL.md` (60 lines) drives `flow.py`: start/token, BUILD and REVIEW subagents from `prompt`, reply saved with Bash under `.git`, never checks or reviews itself.
08 - hand-written Codex skill in `adapters/codex/feature-flow/` (explicit only): same steps with `$feature-flow`, subagents via `spawn_agent` + `wait_agent`, optional hard read-only review through `codex exec --sandbox read-only`.
09 - installer installs feature-flow (+ architect-review, automation-design), roles, scripts and `.feature-flow/{guides,agents,feature_flow}`; old flow skills reported, never deleted; `skill.awk` gone.
14 - conductor state, log, findings and the saved review reply live in `.feature-flow/state/` (self-ignoring, `*`), not `.git`; a run kept under `.git` is copied over with its owner.

## Open questions

- Codex desktop in the environment used to write this revision exposes subagents with separate contexts and returns their replies to the parent. Ticket 02 still probes the exact installed/local and cloud surfaces, read-only review restrictions and prompt shape before choosing subagents or relay mode.
- Whether either runtime tells a session how full its context is (ticket 02). If so, the skill may hand off early, at a ticket boundary.
- Python: the conductor is written in Python here; `plans/interactive-flow-python` ports the remaining bash scripts after ticket 10 of this plan.
- Distribution after this plan: fetch a pinned feature-flow tag at run time, or a PyPI package (`uvx feature-flow@X`). A later plan, once `flow.py`'s commands are stable.
- Whether `architect-review` and `automation-design` become guides behind the one skill. Left as standalone skills here.
