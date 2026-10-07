# Map: proven-checks

## Destination

The conductor runs each ticket's `check` block from Done when and, for `Test first: yes`, proves a test-only commit failed the Test command, sending either failure back before any REVIEW. A builder sent back gets a root-cause debugging guide in its prompt. Each ticket gets a spec review then a quality review, both fresh `ticket-reviewer` subagents, and moves on only after two `REVIEW: PASS`. The guides and template teach planners and builders the new form. Version 0.3.0.

**The bar.** `python3 -m unittest discover -s tests/py && bash tests/run.sh` passes, with tests showing (a) a failing Done when check is sent back before REVIEW, (b) a `Test first: yes` ticket without a failing test first is sent back, (c) a correct ticket passes both checks, (d) a retry build prompt carries the debugging guide and a first one does not, (e) spec REVIEW then quality REVIEW, a FAIL in either sends back, both PASS moves on; and the `tests/smoke-real.sh --prepare` demo drives through `flow.py next` to REVIEW with the checks on. Ticket 09 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py proven-checks`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py proven-checks --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Build only after guard-hardening (PR #35) is merged, from a pinned 0.2.0 conductor: see `spec.md` § How this plan is built.

## Decisions so far

- (plan) Reuse the guard-hardening runner: `gate.shell`, `proc.run`, `gate.tail`, `FLOW_GATE_TIMEOUT`. Source: `git show origin/claude/project-thread-oj7ukv:feature_flow/proc.py` and `feature_flow/gate.py`.
- (plan) Test paths are what `floorguard.DELETED_TEST` matches. Source: `feature_flow/floorguard.py` on the guard-hardening branch.
- (plan) The installer copies all of `guides/` into `.feature-flow/guides/`, so new guide files ship without installer changes. Source: `feature_flow/install.py` (`copy_tree(here + "/guides", ...)`).
- (user, 2026-10-07 18:44Z) The test-first red run happens in place: check out the test-only commit in the working copy, run Test, check the branch out again; `restore` in run state lets the next `next` put a killed run back. No temporary worktree. See spec.md § Decisions.
- (plan) Git commands ticket 03 relies on, and what each is relied on for. git-scm.com was blocked by this sandbox's egress proxy, so the pages below were not read in this round; each behaviour was checked instead against the local git 2.43.0 (`git <cmd> -h` and a scratch repository). No minimum git version is added: these options all appear in the 2.43.0 usage text, and the repo states no minimum today.
  - `git rev-list --reverse --first-parent <base>..HEAD`: commits reachable from HEAD and not from base, oldest first, following only first parents. docs: https://git-scm.com/docs/git-rev-list
  - `git diff-tree --no-commit-id --name-only -r <sha>`: one commit against its parent, recursive, paths only, no sha header line (checked: prints `tests/t.py` for a test-only commit). docs: https://git-scm.com/docs/git-diff-tree
  - `git symbolic-ref -q --short HEAD`: prints the short branch name; with `-q` it prints nothing and exits 1 when HEAD is detached (checked: `exit=1`), so the code falls back to `git rev-parse HEAD`. docs: https://git-scm.com/docs/git-symbolic-ref , https://git-scm.com/docs/git-rev-parse
  - `git checkout -q --detach <sha>` and `git checkout -q <branch>`: detach HEAD at the commit, then return to the branch, quietly (checked in the scratch repo). docs: https://git-scm.com/docs/git-checkout
  - `git status --porcelain` (ticket 03's test that the working copy is back): stable, script-readable status, empty when clean. docs: https://git-scm.com/docs/git-status
  - `git worktree add` is used only by the person running this plan, to pin the 0.2.0 conductor (spec.md § How this plan is built), not by any ticket's code. docs: https://git-scm.com/docs/git-worktree
- (plan) Apart from the git pages above, no outside sources: every other decision here comes from the repository.
- 01 — `proof.checks_in(text)` parses ```check blocks in Done when into frozen `Check(command, exit, prints)` dataclasses (`exit` int or "nonzero", `prints` tuple); broken blocks raise `ParseError` quoting the line.
- 02 — `proof.run_checks` runs every check after the floor guard (gate on only); fail is sent back as `done when`, a broken block or a dirty tree is a STOP; `guard_warning` is now `review_notes` (tab separated, printed as `The conductor notes: ...`).
- 03 — `proof.test_first` finds test-only commits in `base..HEAD`, runs Test in place at each (state `restore` undone at the top of `next`), sent back as `test first` with a recovery recipe for a combined test+code commit; `TESTFIRST-PASS/FAIL/SKIP` logged.
- 04 — two review passes: `review_pass` (`spec`/`quality`) in run state; spec PASS hands out the same REVIEW line with `guides/review-quality.md`, quality PASS moves on; send-back sources are `spec review` / `quality review`; run limit is 3 phases per round.

## Open questions

- Running this plan from this checkout instead of a pinned 0.2.0 conductor would need `Floor: allow flow-edit` on tickets 01 to 08 (they edit `feature_flow/` or the guides the tripwire watches). The brief does not grant it, so the tickets carry no `Floor:` line; the user decides if that changes.
- Whether `flow-status.py --check` should later validate `check` blocks (left out: planner-flow change).
