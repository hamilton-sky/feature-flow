# Map: small-tickets

## Destination

The planner folds changes too small to stand alone into the ticket they belong to, and the plan reviewer flags any it missed. A ticket whose built diff is small (3 files and 60 changed lines at most, plan folder left out) and whose `check` block ran and passed gets one combined reviewer instead of the spec and quality passes. The conductor measures the diff itself; `Review: full` in the ticket at base, `Type: convert`, `FLOW_GATE=off` or `FLOW_SMALL_LINES=0` keeps two passes. Every conductor check still runs on every ticket. Version 0.6.0.

**The bar.** `python3 -m unittest discover -s tests/py -p "test_small_drive.py"` prints `OK` (one `REVIEW` for a small checked ticket; two for `Review: full`, no check block, `Type: convert`, an over-limit diff, and for every ticket under `FLOW_SMALL_LINES=0`), and `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 07 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py small-tickets`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py small-tickets --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Build with the pinned 0.5.0 conductor: see spec.md § How this plan is built.

## Decisions so far

- (plan) `git diff --numstat` prints `-` for the added and removed counts of a binary file; `--no-renames` turns off rename detection even when `diff.renames` is set; a `:(exclude)<path>` pathspec leaves that path out. docs: https://git-scm.com/docs/git-diff (--numstat, --no-renames), https://git-scm.com/docs/gitglossary#Documentation/gitglossary.txt-exclude
- (plan) The conductor decides "small" from the measured diff, not a planner field or the builder's word. Why and the rejected options: spec.md § Decisions.
- 01 — `git.diff_size(base, head, exclude)` -> `(files, lines, binary)` from `git diff --numstat --no-renames`, plan folder excluded; binary files count as a path with 0 lines and set `binary`.
- 02 — `proof.review_mode(text)` -> `full`/`auto` from header lines; `Graph.hasreview`/`review`; `--check` error `NN: Review must be full or auto`.

## Open questions

- Are 3 files and 60 lines the right limits? Revisit after real runs, counting `REVIEW-SMALL` in the logs.
- Quick mode for a one-off fix outside a feature: offered to the user as a later step, not planned here.
- 03 — `guides/review-single.md` plus phase `review-single` in prompts/codehash/flow-trust (task line `(single pass)`); flow-trust hash re-pinned in the four skill copies.
- 04 — `judge_build` picks `review_pass` single/spec from the base ticket (Review, Type), the check block and `git.diff_size`; `FLOW_SMALL_FILES`/`FLOW_SMALL_LINES`; log `REVIEW-SMALL`; smoke-real demo ticket 01 is `Review: full`.
- 05 — planner guide rules 1a (fold tiny changes) and 8a (`Review: full`), plan-review check 7 folded, ticket template `Review: auto`.
06 — README documents the single review and its limits, skills say one or two reviews per ticket, version 0.6.0.
07 — tests/py/test_small_drive.py drives five tickets through the conductor: one REVIEW for the small checked one, two for the rest and for all under FLOW_SMALL_LINES=0.
