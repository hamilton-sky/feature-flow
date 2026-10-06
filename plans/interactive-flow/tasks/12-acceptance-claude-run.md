# Prove the bar with a real Claude Code run, across a handoff

Type: task
Status: open
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
