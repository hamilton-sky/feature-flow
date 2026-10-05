# Prove the bar with a real drive run

Type: task
Status: open
Blocked by: 03, 04, 05, 06
Test first: no

Run the map's bar end to end. Add a `--drive` option to `tests/smoke-real.sh`. With `RUN_REAL=1` it prepares the demo project exactly as it does now, then runs one headless session, `claude -p "/drive-flow hello"`, instead of `scripts/auto-flow.sh`. Find which `--allowedTools` the headless session needs for the Agent tool and for Bash, Read, Glob, Grep, Edit and Write, and pass `--max-budget-usd` from `FLOW_MAX_BUDGET_USD` (default 6) because this is one session that spawns the others. After the run it checks: the demo's bar holds, both tickets are resolved (`flow-status.sh hello --next` exits 10), the tree is clean, each ticket landed as a commit, `.git/flow-step-hello.log` has a `BUILD`, a `REVIEW` and a `VERDICT-PASS` line for both tickets, the gate ran (the log of the run says so), and the floor guard never sent a ticket back.

`--drive` without `RUN_REAL=1` refuses with exit 2, like the other real runs. The offline suite gets checks for that and for the option parsing.

This ticket spends real money. Run the paid command once, by hand, and paste its full output into the Answer between two lines of three backticks. The reviewer checks the pasted output and must not run the paid command again. Then change the README row from "Not yet tested with a real run" to a sentence with the real numbers (tickets, subagent runs if known, minutes, cost or tokens), and say what the run did not cover.

## Not in this ticket

- A Codex drive run: a later round.
- Fixing problems the real run finds in the conductor or the skill. If it fails, set the ticket back to open, write an Attempt note and open a new ticket for the fix.

## Done when

- `grep -n -- '--drive' tests/smoke-real.sh` shows the option, and `env RUN_REAL=0 bash tests/smoke-real.sh --drive; echo $?` prints `2`.
- `bash tests/run.sh` exits 0 and its last line shows the new check count.
- The Answer contains the pasted output of one real `RUN_REAL=1 bash tests/smoke-real.sh --drive`: `grep -c '^  ok ' plans/in-session-mode/tasks/07-acceptance-real-drive-run.md` prints at least `12` and `grep -c '^  FAIL' plans/in-session-mode/tasks/07-acceptance-real-drive-run.md` prints `0`.
- `grep -c 'Not yet tested with a real run' README.md` prints `0`, and the "Claude Code, same-session" row of the "What is tested" table shows the real numbers.

## Reference

- plans/in-session-mode/map.md § Destination (the bar)
- tests/smoke-real.sh (the Codex and Claude run branches, `--prepare`)
- skills/drive-flow/SKILL.md from ticket 04
- README.md (the "What is tested" table)

## Answer

