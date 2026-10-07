# proven-checks — Spec

## Problem

feature-flow's edge over prompt-only workflows (Superpowers) is that code, not the model, checks the work. Two things still rest on the model's word. A ticket passes on the reviewer's `REVIEW: PASS`, which the session relays and the conductor cannot verify, so the ticket's own Done when commands are only ever run by models (builder and reviewer). And `Test first: yes` is only an instruction in the build guide: nothing proves the builder wrote a failing test before the code.

Two smaller gaps were approved into the same plan (brief, Decided 2026-10-07). A builder that is sent back gets the findings but no guidance on how to find the cause, so retries tend to patch symptoms. And one reviewer judges both "did it do what the ticket asked" and "is the code good" in one pass, so one concern crowds out the other.

## Goal and the bar

The conductor itself runs each ticket's machine-readable Done when checks and, for `Test first: yes`, proves a test-only commit failed the plan's Test command before the code made it pass; either failure is sent back to the builder like a gate failure, before any REVIEW. A builder sent back gets a short root-cause debugging guide in its prompt. Every ticket gets two fresh reviews, spec first and quality second, and moves on only when both say `REVIEW: PASS`. Old plans without check blocks keep working. Released as 0.3.0.

**The bar.** `python3 -m unittest discover -s tests/py && bash tests/run.sh` passes, with new tests showing (a) a ticket whose Done when check fails is sent back before REVIEW; (b) a `Test first: yes` ticket built without a failing test first is sent back; (c) a correct ticket passes both checks and reaches REVIEW; (d) a build prompt after a send-back carries the debugging guide and a first build prompt does not; (e) a ticket gets a spec REVIEW then a quality REVIEW, a FAIL in either sends it back, and the next ticket is handed out only after both PASS; plus the two-ticket demo (`tests/smoke-real.sh --prepare`) still drives through `flow.py next` to REVIEW with the new checks on. Ticket 09 runs it.

## Scope

In: the check block format and its parser; running it in `judge_build` after the gate and floor guard; the test-first check; two review passes; the debugging guide on retries; `guides/build.md`, `guides/plan.md`, `guides/templates/ticket.md`, `guides/review.md` (split) and a new `guides/review-quality.md` and `guides/debug.md`; README; the demo in `tests/smoke-real.sh`; version 0.3.0.

Not in scope: parallel tickets or worktrees; a new answer word (the one-line protocol BUILD/REVIEW/DONE/STOP/HANDOFF and `REVIEW: PASS|FAIL` stay); a Codex end-to-end run; any planner or plan-reviewer flow change beyond guide wording (so `flow-status.py --check` does not validate check blocks, see Decisions); mutation testing; running only the new tests at the red commit (the plan's whole Test command is run).

## Happy path

1. `next` after a resolved, committed build → gate passes → floor guard passes → the conductor reads the ticket's `check` block as it was at the base commit and runs each command → all match → log `DONEWHEN-PASS`.
2. The ticket says `Test first: yes` → the conductor finds the first commit after base that changes only test files, runs the Test command at that commit in place in the user's working copy, sees it fail, puts the working copy back as it was → log `TESTFIRST-PASS` (green at HEAD is the gate's own Test run).
3. `REVIEW <ticket> <NN> <base>` (spec pass) → `verdict` PASS → `next` prints `REVIEW <ticket> <NN> <base>` again (quality pass, state `review_pass=quality`) → PASS → next ticket.
4. Any failure in 1 to 3 → findings written into the ticket under `## Review findings (round N, <source>)`, ticket reopened → `BUILD`; its `prompt` now ends with the debugging guide.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| Ticket has no `check` block (every plan before 0.3.0) | Done when check skipped, log `DONEWHEN-SKIP`, the reviewer's prompt says the conductor ran no Done when checks | 02 |
| `check` block the parser cannot read (unknown line, unclosed fence, `exit x`) | `STOP` naming the ticket and the line: the plan is wrong, a builder may not edit it | 01, 02 |
| A check command times out (`FLOW_GATE_TIMEOUT`) | counts as a failed check, tree killed by `proc.run` | 02 |
| A check command leaves tracked or untracked changes | `STOP` naming the files: the plan's command is not read-only | 02 |
| `FLOW_GATE=off` | Done when and test-first checks are skipped too, with the skip logged | 02, 03 |
| `Test first: yes` but `commands.md` has no Test command | test-first skipped, `TESTFIRST-SKIP`, note to the reviewer | 03 |
| No commit between base and HEAD changes only test files | sent back: "commit the failing test alone first" | 03 |
| Test-only commit(s) exist but the Test command passes at each | sent back: "the test passes without the code" | 03 |
| Red run times out | does not count as red | 03 |
| Conductor killed during the red run | the next `next` undoes what the state's `restore` records before anything else: checks the recorded branch out again | 03 |
| The checkout of the test commit, or the way back, fails (e.g. a locked file on Windows) | `STOP` naming the git error and what to undo by hand | 03 |
| Rebuild after a send-back: the earlier test-only commit is still in base..HEAD | it still counts; a new red commit is not required | 03 |
| Reviewer edits or commits during either pass | `STOP` as today | 04 |
| No verdict in a pass | `RETRY`, then STOP after `FLOW_MAX_RETRIES`, counted per pass | 04 |
| A build attempt that ends unresolved (not a send-back) | no debugging guide: it is added only when `round` > 0 | 05 |

## Design

```
 judge_build
   gate ──fail──► send_back("gate")
    │pass
   floor guard ──fail──► send_back("floor guard")
    │pass
   Done when checks (proof.run_checks) ──fail──► send_back("done when")
    │pass / skip(note)
   test-first (proof.test_first) ──fail──► send_back("test first")
    │pass / skip(note)
   REVIEW (review_pass=spec) ──FAIL──► send_back("spec review")
    │PASS
   REVIEW (review_pass=quality) ──FAIL──► send_back("quality review")
    │PASS
   pick next ticket

 send_back ──► round+1 ──► BUILD; prompt = build guide + debug.md
```

New module `feature_flow/proof.py` holds the parser, the check runner and the test-first check, so `conductor.py` only sequences them. Commands run through the guard-hardening runner: `gate.shell(cmd)` for the shell (bash -c on POSIX, cmd.exe on Windows), `proc.run(args, use_shell, log, minutes)` for the timeout and process-tree kill, `gate.tail` for the last 40 lines. No second runner.

**Check block.** Inside `## Done when` (up to the next `## ` heading), any number of fenced blocks opened by a line that is exactly ```` ```check ```` and closed by ```` ``` ````. Inside: blank lines and lines starting with `#` are ignored; `$ <command>` starts a check; after it, `exit <N>` (whole number, default 0) or `exit nonzero`, and any number of `prints <text>` lines (the combined stdout and stderr, with `\r\n` read as `\n`, must contain `<text>`). Any other line is a parse error. Prose bullets stay for people and the reviewer. Example:

````
## Done when

- `python3 hello.py Ada` prints exactly `Hello, Ada!`.

```check
$ python3 hello.py Ada
prints Hello, Ada!
$ python3 -m unittest test_hello
```
````

The block is read from the ticket at the base commit (`git show <base>:<ticket>`, the same way `flow_edit_allowed` reads `Floor:`), so a builder cannot change what is checked. Each command runs from the repo's top folder with `FLOW_GATE_TIMEOUT`. All checks run (not stop-at-first) so one round reports every failure.

**Test first.** Read `Test first:` from the ticket at base. Candidates: commits in `git rev-list --reverse --first-parent <base>..HEAD` whose changed paths, ignoring the plan folder, are non-empty and all match `floorguard.DELETED_TEST` (the guard's test-path pattern). For each candidate in order: record in the run state's `restore` what must be undone, put the candidate's files where the Test command can run, run the Test command from `commands.md`, undo, clear `restore`. This happens **in place** (the user's decision, see Decisions): `restore` is the branch name (`git symbolic-ref -q --short HEAD`), or the sha when HEAD is detached; `git checkout -q --detach <sha>`, run Test, then `git checkout -q <restore>`. The first candidate whose Test exits non-zero (not a timeout) proves red. Green at HEAD is the gate's Test run, which already passed. Runs only when the gate is on.

**Two review passes.** `guides/review.md` keeps "Verdict 1: does it meet the ticket?" (Done when re-run, scope, test first) and ends with `REVIEW: PASS|FAIL`; the new `guides/review-quality.md` holds "Verdict 2: is it good?" and the same output contract. The run state gains `review_pass` (`spec` or `quality`). `hand_out_review` prints the same `REVIEW <ticket> <NN> <base>` line for both; `prompt` picks the guide by `review_pass`; a spec PASS hands out the quality pass (fresh `review_attempt`, same `review_sha`), a quality PASS picks the next ticket. The skill needs no change: it already spawns a fresh `ticket-reviewer` for every REVIEW line. The run limit grows from 2 to 3 phases per round.

**Debugging guide.** `guides/debug.md`: reproduce the failure from the findings, isolate the cause (smallest failing case, one hypothesis at a time), fix the cause not the symptom, prove it with the command that failed. `prompts.build` appends it to a build prompt when the conductor's `round` is above 0.

### Decisions

- **Machine form for Done when** — options: a fenced `check` block with `$`/`exit`/`prints` lines; or parsing the existing prose bullets for backticked commands. Chosen: the fenced block. Why: prose bullets hold commands that are not meant to run as written ("with the change stashed, the three tests fail") and results in free words, so a parse would guess; a fence is explicit and renders as code. Rejected: parsing bullets.
- **Where the red run happens — decided by the user (2026-10-07 18:44Z): in place.** Options were (A) check out the test-only commit in the user's working copy, run Test, and check the branch out again, with the branch recorded as `restore` in the run state so a killed run is put back by the next `next`; or (B) a temporary `git worktree`, as the brief first assumed. The user chose A. It works in any project because ignored dependencies (`node_modules`, a venv, build output) are already in the working copy; a fresh worktree would lack them and could be red for the wrong reason. Rejected: B. The cost of A (the working copy is detached while Test runs; a locked file on Windows can STOP) is under Risks.
- **Identifying the test commit** — options: by convention, a commit whose changes are only test paths; or a commit message prefix the builder must use. Chosen: by content, reusing `floorguard.DELETED_TEST`. Why: a message is the model's word; content is checked. The build guide still asks for `test(<feature>): NN failing test` as the message, for people.
- **Red only, not "red because of the commit"** — options: also run Test at the red commit's parent and require it to pass; or not. Chosen: not. Why: base already passed the gate at the end of the previous ticket, so one run is enough; listed under Risks.
- **Switch** — options: a new `FLOW_CHECKS` variable; or reuse `FLOW_GATE=off`. Chosen: reuse. Why: both checks run project commands just like the gate, and test-first relies on the gate's green run. No new variable.
- **A failing check is a finding, a broken check block is a STOP** — the builder can fix code, not the plan.
- **Two passes sequenced by state, not a new answer word** — options: `REVIEW` twice with `review_pass` in state; or a new `QUALITY` line. Chosen: `REVIEW` twice. Why: the brief keeps the protocol; the skill already handles any number of REVIEW lines. Spec pass first: it is the one that re-runs Done when and fails most often, so a broken ticket costs one reviewer, not two.
- **Two guide files, not two sections** — options: `review.md` and `review-quality.md`; or one guide with both sections and the conductor cutting it. Chosen: two files. Why: `prompts.find_file` and the installer already work by file; cutting markdown is fragile. Both are added to the code fingerprint (`codehash`).
- **Debugging guide trigger** — options: on `round > 0` (sent back); or also on a repeated unresolved attempt. Chosen: `round > 0`, as the brief says ("when a ticket is sent back").
- **No `--check` validation of check blocks** — would catch typos at plan time but is a planner-flow change the brief rules out. A broken block STOPs at the first build instead. The user can overrule this.

## Interfaces

- `feature_flow/proof.py` (new): `class ParseError(ValueError)`; `checks_in(text) -> [Check]` with `Check(command, exit, prints)` where `exit` is an int or `"nonzero"`; `run_checks(checks, timeout) -> (ok, report)`; `test_first(base, test_command, plan_dir, timeout, remember) -> (status, report)` with status `pass`, `fail` or `skip`.
- Run state keys: `review_pass` (`spec`/`quality`), `review_notes` (replaces `guard_warning`; one note per line), `restore` (the branch, or sha, to check out again after the red run).
- Log events: `DONEWHEN-PASS|FAIL|SKIP`, `TESTFIRST-PASS|FAIL|SKIP`; existing `REVIEW` and `VERDICT-*` are logged once per pass.
- `send_back` sources: `done when`, `test first`, `spec review`, `quality review` (was `independent review`).
- `prompts.ROLES`/`GUIDES` gain `review-quality` (role `ticket-reviewer.md`, guide `review-quality.md`); `prompts.build(..., retry=False)` appends `guides/debug.md` when `retry`.

## Migration and compatibility

Plans without a `check` block are not broken: the check is skipped with a note. Tickets with `Test first: yes` in existing plans whose builders did not commit tests first will be sent back once on their next build; `reset` and `Test first: no` are the ways out. Existing run states have no `review_pass`; an absent value means `spec`. Existing tests that expect the next BUILD straight after one PASS change to two PASSes.

## Risks

- A test-only commit that breaks the whole suite (syntax error) counts as red — the spec reviewer still checks "would the test fail without the production change".
- If base itself was red (first ticket, gate off earlier), a test-only commit is red for the wrong reason — the smoke command and the gate at the previous ticket make this rare.
- The red run detaches the user's working copy at an older commit while Test runs; after a crash it stays detached until the next `next` puts it back from `restore`. On Windows a locked file can make the checkout fail — the check reports it as a STOP naming the git error and the branch to go back to.
- Two reviews cost one more subagent per ticket — the spec pass goes first so most failing tickets stop there.

## How this plan is built (read before running it)

Every ticket edits `feature_flow/` or the guides, which in this repo are the conductor's own code, and the guard-hardening tripwire would STOP on them. Build this plan only after guard-hardening (PR #35) is merged, then run its conductor from a pinned checkout of that release: `git worktree add ../ff-0.2.0 <the 0.2.0 tag or merge commit>`, then `python3 ../ff-0.2.0/scripts/flow.py proven-checks <command>` from this repo. That conductor has none of the new checks, so this plan's tickets are judged by 0.2.0 rules.
