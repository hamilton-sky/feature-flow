# Add sessions, the handoff and relay mode to the conductor

Type: task
Status: open
Blocked by: 04
Test first: yes

A session's context grows with every ticket, and a runtime without subagents needs a fresh session per phase. Both are the same mechanism: the script tells the session to stop at a clean point and prints the line that continues the work.

Add `python3 scripts/flow.py <feature> start`. It prints `PLAN` when the plan folder does not exist. Otherwise it creates an opaque session-owner token, records it in the state, resets the per-session ticket count and prints `OK <token>`. While an owner exists, every `next`, `prompt` and `verdict` call must receive that value as `FLOW_SESSION`; a missing or different token STOPs before changing state. With no owner recorded (no `start` yet, or after `HANDOFF` or `DONE` cleared it) those commands work without a token, so the `flow.py` tests written before this ticket keep passing unchanged. If another owner already exists, `start` STOPs and names it. Only `FLOW_TAKEOVER=1`, set after the user explicitly confirms that the earlier session is dead or closed, may replace it. A takeover does not touch the ticket, round or attempt state, so the next `next` judges the repo as usual (an unresolved ticket counts as a used attempt). Never `source` the state file or treat its values as shell code.

In `next`, after a PASS verdict, when the number of tickets passed since `start` reaches `FLOW_TICKETS_PER_SESSION` (default 4) and tickets remain, clear the owner, print `HANDOFF <FLOW_INVOKE> <feature>` instead of the next BUILD, exit 0, and log `HANDOFF`. `FLOW_INVOKE` defaults to `/feature-flow`. The next `start` creates a new owner and the following `next` prints the BUILD that was held back. `DONE` also clears the owner; `STOP` keeps it so the same session can inspect and report the failure.

With `FLOW_RELAY=1`, print `HANDOFF` after every BUILD and every REVIEW is handed out, so each phase runs in its own session: the session that receives BUILD or REVIEW does that phase itself (with `prompt`), then the script hands off. `FLOW_RELAY` is read at every call, so a skill sets it per runtime.

## Not in this ticket

- What the skill says and does on `HANDOFF`: the skill tickets.
- A handoff by context percentage.

## Done when

- `start` prints `PLAN` with no plan folder and `OK <token>` with one, and resets only the session count (the state file's ticket, round and attempt are unchanged). While an owner exists, calls without the matching `FLOW_SESSION` STOP without changing state; with no owner, `next` works without a token and the earlier `flow.py` tests pass unchanged.
- A second `start` STOPs while the first owner exists. `FLOW_TAKEOVER=1 start` returns a different token and preserves the outstanding phase and counters; a test proves the old token can no longer drive the flow.
- With `FLOW_TICKETS_PER_SESSION=1` on a two-ticket plan, after the first ticket passes `next` clears the owner, prints `HANDOFF /feature-flow f` and exits 0; after `start`, `next` with the new token prints `BUILD plans/f/tasks/02-b.md 02 <sha>`. With `FLOW_INVOKE='$feature-flow'` it prints `HANDOFF $feature-flow f`.
- After a takeover with a BUILD outstanding and the ticket still `claimed`, `next` resets it and prints BUILD again, counting the attempt.
- With `FLOW_RELAY=1`, every BUILD and REVIEW is followed by `HANDOFF` on the next `next`, and the log shows the sequence BUILD, HANDOFF, REVIEW, HANDOFF for one ticket.
- `bash tests/run.sh` exits 0 with checks for each bullet, including two simulated sessions attempting to drive the same feature.

## Reference

- spec.md § Interfaces, Edge cases, Decisions (handoff trigger)
- tests/run.sh (the `flow.py` section)

## Answer
