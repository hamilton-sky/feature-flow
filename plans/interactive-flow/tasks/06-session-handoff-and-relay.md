# Add sessions, the handoff and relay mode to the conductor

Type: task
Status: open
Blocked by: 04
Test first: yes

A session's context grows with every ticket, and a runtime without subagents needs a fresh session per phase. Both are the same mechanism: the script tells the session to stop at a clean point and prints the line that continues the work.

Add `bash scripts/flow.sh <feature> start`. It prints `PLAN` when the plan folder does not exist, otherwise records a new session in the state (resets the per-session ticket count) and prints `OK`. It does not touch the ticket, round or attempt state, so a session that died mid-phase is picked up by the next `next`, which judges the repo as usual (an unresolved ticket counts as a used attempt).

In `next`, after a PASS verdict, when the number of tickets passed since `start` reaches `FLOW_TICKETS_PER_SESSION` (default 4) and tickets remain, print `HANDOFF <FLOW_INVOKE> <feature>` instead of the next BUILD, exit 0, and log `HANDOFF`. `FLOW_INVOKE` defaults to `/feature-flow`. The next `start` resets the count and the following `next` prints the BUILD that was held back.

With `FLOW_RELAY=1`, print `HANDOFF` after every BUILD and every REVIEW is handed out, so each phase runs in its own session: the session that receives BUILD or REVIEW does that phase itself (with `prompt`), then the script hands off. `FLOW_RELAY` is read at every call, so a skill sets it per runtime.

## Not in this ticket

- What the skill says and does on `HANDOFF`: the skill tickets.
- A handoff by context percentage.

## Done when

- `start` prints `PLAN` with no plan folder and `OK` with one, and resets only the session count (the state file's ticket, round and attempt are unchanged).
- With `FLOW_TICKETS_PER_SESSION=1` on a two-ticket plan, after the first ticket passes `next` prints `HANDOFF /feature-flow f` and exits 0; after `start`, `next` prints `BUILD plans/f/tasks/02-b.md 02 <sha>`. With `FLOW_INVOKE='$feature-flow'` it prints `HANDOFF $feature-flow f`.
- After a `start` with a BUILD outstanding and the ticket still `claimed`, `next` resets it and prints BUILD again, counting the attempt.
- With `FLOW_RELAY=1`, every BUILD and REVIEW is followed by `HANDOFF` on the next `next`, and the log shows the sequence BUILD, HANDOFF, REVIEW, HANDOFF for one ticket.
- `bash tests/run.sh` exits 0 with checks for each bullet.

## Reference

- spec.md § Interfaces, Edge cases, Decisions (handoff trigger)
- tests/run.sh (the `flow.sh` section)

## Answer
