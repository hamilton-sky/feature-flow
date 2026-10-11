# Small tickets — Spec

## Problem

Every ticket pays the same fixed cost whatever its size: a smoke run, the gate, a builder session, and then two fresh reviewer sessions, a spec pass and a quality pass (`Conductor.judge_build` and `Conductor.judge_review` in `feature_flow/conductor.py`). Nothing in the flow looks at how big a ticket is.

On a small ticket the spec pass mostly repeats what the conductor already proved. `guides/review.md` tells the reviewer to re-run every Done when command, and for a ticket with a `check` block the conductor already ran those exact commands from the ticket as it was at base. What the spec pass adds is a scope check, the prose-only Done when bullets, and whether the test-first test really tests the change. The quality pass is the one that has caught real bugs: every review send-back recorded in the plans on main since the split came from it (trusted-checks tickets 02 and 03). The planner also sometimes makes tickets so small (a rename, a doc line) that the fixed cost dwarfs the work.

## Goal and the bar

Two changes. (1) The planner folds a change too small to stand alone into the ticket it belongs to, and the plan reviewer flags a ticket that should have been folded. (2) A ticket whose built diff is small gets **one** combined reviewer instead of two. The conductor decides "small" by measuring the diff from the repo, never from the builder's word, and the planner can force both reviewers with `Review: full`. Every conductor check (smoke, gate, floor guard, Done when, test-first) still runs on every ticket.

**The bar.** `python3 -m unittest discover -s tests/py -p "test_small_drive.py"` prints `OK`: in a fixture repo driven through the conductor, a small ticket with a passing `check` block gets exactly one `REVIEW` before the next `BUILD`, and its prompt says `(single pass)`; a small ticket with `Review: full`, a small ticket with no `check` block, a small `Type: convert` ticket and a ticket whose diff is over the line limit each get two (`spec` then `quality`); `FLOW_SMALL_LINES=0` gives every ticket two. And `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 07 runs it.

## Scope

In: a diff-size helper; the `Review:` ticket line (`full` or `auto`) and its `--check` validation; a combined review guide `guides/review-single.md` and its prompt phase; the conductor choosing the single pass; the planner and plan-reviewer guides and the ticket template; README, the Codex skill's reviewer task names, version 0.6.0.
Not in scope: a quick mode for a one-off fix outside a feature (offered to the user as a later step); skipping or weakening any conductor check for small tickets; a `Size:` field set by the planner (rejected, see Decisions); changing the Claude skill (it already spawns a fresh reviewer for every `REVIEW` line); a Codex end-to-end run (no Codex from the cloud).

## Happy path

1. Builder resolves and commits a ticket → gate, floor guard, Done when checks and (if `Test first: yes`) the test-first proof pass, exactly as today.
2. The conductor measures `git diff --numstat --no-renames <base>..HEAD`, leaving out the plan folder → 2 files, 30 lines. The ticket at base has a `check` block that ran and passed, no `Review: full`, and is not `Type: convert` → state `review_pass=single`, log `REVIEW-SMALL`.
3. `next` prints the usual `REVIEW <ticket> <NN> <base>`. `prompt` builds the reviewer prompt from `guides/review-single.md`, says `(single pass)`, and carries the note `the conductor judged this ticket small (2 files, 30 lines): one review covers the spec and quality passes`.
4. `verdict` PASS → `next` picks the next ticket. FAIL → findings written to the ticket as `## Review findings (round N, single review)`, ticket reopened → `BUILD`. The rebuilt ticket is measured again after its build.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| Ticket has no `check` block (Done when ran nothing) | two passes, as today | 04 |
| `FLOW_GATE=off` (Done when not run) | two passes | 04 |
| `Review: full` in the ticket at base | two passes | 02, 04 |
| `Review: full` added by the builder after base | ignored: the line is read at base | 04 |
| `Type: convert` | two passes | 04 |
| Diff has a binary file (`-` in numstat) | not small | 01 |
| Diff over `FLOW_SMALL_FILES` files (default 3) or `FLOW_SMALL_LINES` lines (default 60) | two passes | 01, 04 |
| `FLOW_SMALL_LINES=0` | the single pass is off: two passes always | 04 |
| `FLOW_SMALL_LINES=abc` | `STOP FLOW_SMALL_LINES must be a whole number`, as the other `FLOW_*` numbers | 04 |
| `Review: maybe` | `flow-status.py --check` error `Review must be full or auto` | 02 |
| Run state from 0.5.0 mid review (`review_pass` spec or quality) | carries on as before | 04 |
| A single review that returns no verdict | retried, then the existing `no review verdict` STOP | 04 |
| Codex skill names reviewer tasks by pass | `ticket_reviewer_<NN>_single_<k>` | 06 |

## Design

    judge_build: gate ─► floor guard ─► Done when ─► test first
         │ all pass
         ▼
    small? = gate on AND check block ran AND no `Review: full`
             AND not convert AND diff <= files/lines limits
         │ yes                         │ no
         ▼                             ▼
    review_pass=single            review_pass=spec
    REVIEW (review-single.md)     REVIEW (review.md) ─PASS─► REVIEW (review-quality.md)
         │ PASS                        │ PASS
         ▼                             ▼
    next ticket                   next ticket
         any FAIL ─► send_back (findings, reopen, BUILD), measured again next round

### Decisions

- **Who decides "small"** — options: the conductor measures the built diff; a `Size: small` field the planner sets; the builder says so. Chosen: the conductor measures. Why: the planner guesses before the code exists, and the builder's word is the model's word; the diff is checked from the repo like every other conductor decision. A builder can only "game" it by writing a smaller change. Rejected: `Size:` field, builder claim.
- **The planner's override** — `Review: full` (or `auto`, the default) read from the ticket at base, like `Floor:`, so a builder cannot add or remove it. Used for small but risky changes (trust boundaries, the conductor's own code). `Type: convert` always gets two passes in code, because the plan guide already treats conversions as high risk.
- **What the single pass covers** — options: drop the spec pass only; drop the quality pass only; one combined guide. Chosen: one combined guide, `guides/review-single.md`: scope, prose-only Done when bullets, the test-first question, and the quality list. It does not ask the reviewer to re-run commands the conductor's note says already passed. Why: the quality pass is the one that has found real bugs, and scope is the one thing only the spec pass checks.
- **Single pass requires a check block that ran** — without it the spec pass is the only place Done when is checked, so it stays.
- **Limits** — 3 files and 60 changed lines (added plus removed), plan folder left out, through `FLOW_SMALL_FILES` and `FLOW_SMALL_LINES`; `FLOW_SMALL_LINES=0` turns the single pass off. Why: one function plus its test usually fits; tune later from real runs.
- **Same protocol** — the conductor still prints `REVIEW <ticket> <NN> <base>`; the pass lives in state (`review_pass=single`) and the prompt names it, as spec and quality do today. No new answer word.
- **Fewer tiny tickets is guide text only** — the planner rule and plan-review check are wording; no code enforces a minimum ticket size. Why: "too small" is a judgement about where a change belongs, not a number.

## Interfaces

- `feature_flow/git.py`: `diff_size(base, head, exclude) -> (files, lines, binary)` from `git diff --numstat --no-renames`.
- `feature_flow/proof.py`: `review_mode(text) -> "full" | "auto"` from the ticket's header lines, like `wants_test_first`.
- `feature_flow/status.py` `--check`: error `NN: Review must be full or auto`.
- Run state: `review_pass` gains `single`. Log events: `REVIEW-SMALL` (the single pass was chosen, with the measured size in the conductor's note).
- `send_back` source: `single review`.
- `prompts.ROLES`/`GUIDES`: `review-single` (role `ticket-reviewer.md`, guide `review-single.md`); the task line says `(single pass)`.
- `codehash` and `scripts/flow-trust.py` `GUIDES` include `review-single.md`.
- Env: `FLOW_SMALL_FILES` (default 3), `FLOW_SMALL_LINES` (default 60, 0 = off).

## Migration and compatibility

Plans written before 0.3.0 have no `check` block, so they keep two passes. Plans with check blocks get the single pass on small tickets from 0.6.0; `FLOW_SMALL_LINES=0` restores the old behaviour. A run state saved by 0.5.0 has `review_pass` spec or quality and carries on unchanged. Tests in `tests/py` and `tests/run.sh` whose fixtures have no `check` block are unaffected; the demo in `tests/smoke-real.sh` has check blocks and small diffs, so ticket 04 keeps it covering both paths.

## Risks

- A small diff can still hold a boundary bug — the single pass keeps the quality list, and the planner marks risky tickets `Review: full`.
- One reviewer doing two jobs may skim scope — the guide puts scope first and the output shape has a scope line.
- Line limits are a guess — two env vars, and `REVIEW-SMALL` in the log so real runs can be counted.

## How this plan is built (read before running it)

Every ticket but 07 edits feature-flow's own code, guides or skills, so each carries `Floor: allow flow-edit`. Build it with a conductor from a pinned checkout of the 0.5.0 release (`git worktree add ../ff-0.5.0 32754ea`, then run the skill's runner from there), so this plan's tickets are judged by 0.5.0 rules, as trusted-checks was built on 0.4.0.
