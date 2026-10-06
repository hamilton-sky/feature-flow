# Run the demo by hand in Codex and record what happened

Type: settle
Status: open
Blocked by: 08, 09
Test first: no

Prepare the demo with `FLOW_AGENT=codex bash tests/smoke-real.sh --prepare DIR` and run `$feature-flow hello` in an interactive Codex session, in the mode ticket 02 chose, following every `HANDOFF` by starting a new session with the printed line. This is by hand because relay mode needs a person to start sessions. The user decides whether it costs too much to repeat.

Record in the Answer: how many sessions it took, whether both tickets resolved with `REVIEW: PASS`, the last 20 lines of `.git/flow-hello.log`, anything the skill said that confused the user, and the cost or tokens if Codex shows them. Put these lines in the Answer exactly:

```
Codex run finished: yes
Sessions used: <number>
```

## Not in this ticket

- Fixing what the run finds: a new ticket per problem. If the run does not finish, leave this ticket open, add an Attempt note and make each required fix a blocker of this ticket; do not record a resolved `no` result.

## Done when

- `grep -c '^Codex run finished: yes$' plans/interactive-flow/tasks/13-codex-hand-run.md` prints `1` and `grep -cE '^Sessions used: [0-9]+$' plans/interactive-flow/tasks/13-codex-hand-run.md` prints `1`.
- The Answer contains the log lines between two lines of three backticks.

## Reference

- adapters/codex/feature-flow/SKILL.md
- plans/interactive-flow/tasks/02-probe-codex-sessions.md

## Answer
