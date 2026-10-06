# Prove the bar with a real Claude Code run, across a handoff

Type: task
Status: resolved
Blocked by: 09
Test first: no

Run the map's bar end to end. Add `--interactive` to `tests/smoke-real.sh`. With `RUN_REAL=1` it prepares the demo project as `--prepare` does (now installing the one skill), then runs `claude -p "/feature-flow hello auto"` until it prints a `DONE` line or a `STOP`, at most three sessions, with `--max-budget-usd` from `FLOW_MAX_BUDGET_USD` (default 6) per session. Find which `--allowedTools` the session needs for the Agent tool and for Bash, Read, Glob, Grep, Edit and Write. With `FLOW_TICKETS_PER_SESSION=1` the first session must end on `HANDOFF`. If a session ends without printing `HANDOFF`, `DONE` or `STOP` (it crashed or ran out of budget), the owner is still recorded and the skill never takes over in `auto` mode, so the script must not start another session: it prints `  FAIL session N ended without HANDOFF, DONE or STOP`, then the recovery command (`FLOW_TAKEOVER=1` with the same run, after checking no session is alive), and exits 1. It never sets `FLOW_TAKEOVER` itself. Checks after the run: the demo's bar holds, `flow-status.sh hello --next` exits 10, the tree is clean, each ticket landed as a commit, and `.git/flow-hello.log` has `BUILD`, `GATE-PASS`, `GUARD-PASS`, `REVIEW`, `VERDICT-PASS` for both tickets and one `HANDOFF` between them.

`--interactive` without `RUN_REAL=1` refuses with exit 2; the offline suite checks that and the option parsing.

This ticket spends real money. Run the paid command once, by hand, and paste its full output into the Answer between two lines of three backticks. The reviewer checks the pasted output and must not run it again.

## Not in this ticket

- A Codex run: ticket 13.
- Fixing what the run finds. If it fails, set the ticket open, write an Attempt note and open a new ticket for the fix.

## Done when

- `env RUN_REAL=0 bash tests/smoke-real.sh --interactive; echo $?` prints `2`, and `bash tests/run.sh` exits 0.
- The Answer contains the pasted output of one real run: `grep -c '^  ok ' plans/interactive-flow/tasks/12-acceptance-claude-run.md` prints at least `10` and `grep -c '^  FAIL' plans/interactive-flow/tasks/12-acceptance-claude-run.md` prints `0`.
- The pasted output shows two sessions, the first ending on `HANDOFF /feature-flow hello`.
- An offline check with a fake `claude` that exits without printing any of the three lines shows the `FAIL session 1 ended without HANDOFF, DONE or STOP` line, the recovery command and exit 1, and no second session started.

## Reference

- plans/interactive-flow/map.md § Destination (the bar)
- tests/smoke-real.sh (`--prepare` and the existing real-run branches)

## Answer

The bar holds in a real run. `RUN_REAL=1 bash tests/smoke-real.sh --interactive` was run once, by hand, from a fresh clone of `main` at `2ebe22a` (520 offline checks passing there). It ran two sessions: the first built and reviewed ticket 01 and ended on `HANDOFF`, the second built ticket 02 and ended on `DONE`. 16 checks `ok`, none `FAIL`, exit 0. The `EXIT=0` line at the end is added by the wrapper that captured the output.

```
project: /var/folders/n7/9mk8c93j3r53vyswkv_mh0vm0000gn/T/tmp.Omrw4kBlc5 (kept)
session 1: claude -p "/feature-flow hello auto"
Ticket 01 of `hello` is built and reviewed, and the review passed. The conductor then asked for a handoff to a new session, so I've stopped there.

- **Built:** `hello.py` now has `greet(name)`, which returns `Hello, <name>!`. `test_hello.py` has one unittest for it. The commit is `a91fcb8`.
- **Review:** the reviewer re-ran both Done when commands and both exited 0. Scope was clean, the test was written first, and it found no quality issues.
- **Not done yet:** ticket 02 is still to do. `hello.py` has no command-line entry point, so `python3 hello.py Ada` prints nothing until then.

To continue, open a new session and type exactly:

`/feature-flow hello`
session 1 ended on HANDOFF
session 2: claude -p "/feature-flow hello auto"
The `hello` feature is complete: both tickets are resolved. Ticket 01 was already built. This run built ticket 02, the command-line entry point in `hello.py`, as commit `632765b`.

The reviewer ran both Done when commands and passed it. `python3 hello.py Ada` prints `Hello, Ada!`, and `python3 -m unittest test_hello` runs one test and exits 0. The reviewer's one minor note: running `hello.py` with no name raises an `IndexError`, and the ticket doesn't ask for a usage message.

To see the graph, run `/feature-flow hello show`.
session 2 ended on DONE
checks
  ok    the run ended on DONE
  ok    the bar holds
  ok    both tickets are resolved
  ok    the tree is clean
  ok    each ticket landed as a commit
  ok    ticket 01: the log has BUILD
  ok    ticket 01: the log has GATE-PASS
  ok    ticket 01: the log has GUARD-PASS
  ok    ticket 01: the log has REVIEW
  ok    ticket 01: the log has VERDICT-PASS
  ok    ticket 02: the log has BUILD
  ok    ticket 02: the log has GATE-PASS
  ok    ticket 02: the log has GUARD-PASS
  ok    ticket 02: the log has REVIEW
  ok    ticket 02: the log has VERDICT-PASS
  ok    the first session handed off once, between the tickets

15:23:08,-,START
15:23:10,01,BUILD
15:23:50,01,GATE-PASS
15:23:51,01,GUARD-PASS
15:23:51,01,REVIEW
15:24:19,01,VERDICT-PASS
15:24:20,01,HANDOFF
15:24:32,01,START
15:24:34,02,BUILD
15:24:57,02,GATE-PASS
15:24:57,02,GUARD-PASS
15:24:57,02,REVIEW
15:25:19,02,VERDICT-PASS
15:25:20,02,DONE
632765b feat(hello): 02 Add the command line entry point
a91fcb8 feat(hello): 01 Add the greet function
7694997 init
EXIT=0
```

Proven offline, with no model called: `env RUN_REAL=0 bash tests/smoke-real.sh --interactive` prints the refusal and exits `2`. With a fake `claude` first on `PATH` that exits without printing anything, the harness printed `  FAIL  session 1 ended without HANDOFF, DONE or STOP`, then the recovery command, exited `1`, and the fake was started exactly once, so no second session began. The script never sets `FLOW_TAKEOVER` itself; it appears only inside the printed recovery command.

Checked by hand in the kept demo project afterwards: `python3 hello.py Ada` prints `Hello, Ada!`, the unit test passes, `git status --porcelain` is empty, there are three commits, both tickets say `Status: resolved`, and no review reply is left under `.git`.

An earlier attempt of the same command, on `bce036c`, did not pass. Session 1 built and reviewed ticket 01 (`REVIEW: PASS`) but could not save the reviewer's reply: an unattended `claude -p` session is refused when it writes under `.git` ("a sensitive file"), so `verdict` never ran and the harness stopped after one session with its recovery message. That is the failure path this ticket specifies, and it was fixed in `#9` (reply saved outside `.git`) and ticket 14 (state and reply moved to `.feature-flow/state/`), not in this ticket. The run above is the one that counts.

For later tickets:
- The tools a session needs, found by this run: `--allowedTools "Agent,Task,Bash,Read,Glob,Grep,Edit,Write"` is enough for the whole flow, including the builder and reviewer subagents, with `--max-budget-usd 6` per session.
- Cost: the harness prints no dollar figure. Both sessions ran on `claude-sonnet-5-5` and used about 23k output tokens and 1.98M cached input tokens between them, well inside the $6 cap each. Two sessions is the normal case; three is the worst case.
- The reviewer's one minor note was that `python3 hello.py` with no name raises `IndexError`. The ticket does not ask for a usage message, so it is not a finding.
- Ticket 13 (the Codex hand run) was skipped, so the Codex runtime is still unverified by hand. Ticket 10 waits on this ticket only.
