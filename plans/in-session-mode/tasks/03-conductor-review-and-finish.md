# Finish the conductor, the review verdict, the finish and the stops

Type: task
Status: open
Blocked by: 02
Test first: yes

Extend `scripts/flow-step.sh` with `bash scripts/flow-step.sh <feature> verdict <file>`. It takes the reviewer subagent's reply, which the session saves to a file (the path is the session's choice), and completes the review half of the policy, mirroring `review()` and `send_back` in `scripts/auto-flow.sh`.

`verdict` only works while a review is pending, meaning the last thing `next` printed was REVIEW. Otherwise it changes nothing and exits 2. It reads the last line of the file that matches `^REVIEW: (PASS|FAIL)[[:space:]]*$`, the pattern `auto-flow.sh` uses. It prints `OK` and exits 0, or `RETRY no review verdict` and exits 0 when there is no such line. It also appends a `VERDICT-PASS`, `VERDICT-FAIL` or `VERDICT-NONE` line to `.git/flow-step-<feature>.log`. Then `next` decides:

- PASS: the ticket is done. `next` prints the next `BUILD`, or a line starting with `DONE ` and exits 0 when `flow-status.sh --next` reports the feature complete (exit 10). If tickets remain but none is ready, `STOP stuck: ...` and exit 1, as `auto-flow.sh` does.
- FAIL: append the first 120 lines of the file under `## Review findings (round N, independent review)`, set the ticket open, commit it like the gate and guard send-back, and print BUILD. More than `FLOW_MAX_REVIEW_ROUNDS` rounds is `STOP ... still fails the independent review after 3 round(s)`.
- No verdict: print REVIEW again. After `FLOW_MAX_RETRIES` tries, `STOP no review verdict for 01-a after 2 attempt(s)`.
- Also STOP when a tracked file changed during the review (`the reviewer changed tracked files, which a reviewer must never do`), when the tree is dirty after a resolved ticket (`working tree is dirty after 01-a, it should have been committed`), and when the number of builder and reviewer runs passes the run limit computed as in `auto-flow.sh` (`total * 2 * MAX_RETRIES * (MAX_ROUNDS + 1) + 1`).

## Not in this ticket

- The skill and the subagent prompts: ticket 04.
- Changes to the build and check half written in ticket 02, except what the new stops need.

## Done when

- With a review pending, `verdict` on a file whose last line is `REVIEW: PASS` prints `OK`, and the next `next` prints `BUILD` for the next ready ticket. On the last ticket it prints a line starting with `DONE ` and exits 0. `.git/flow-step-f.log` has a `VERDICT-PASS` line.
- A file ending in `REVIEW: FAIL` appends `## Review findings (round 1, independent review)` containing the file's text to the ticket and commits it, and the next `next` prints BUILD for the same ticket. After 3 failed rounds `next` prints `STOP 01-a still fails the independent review after 3 round(s)` and exits 1.
- A file with no verdict line makes `verdict` print `RETRY no review verdict`, and after 2 such files `next` prints `STOP no review verdict for 01-a after 2 attempt(s)` and exits 1.
- `next` prints `STOP` and exits 1 when the reviewer left a tracked file modified, when the tree is dirty after a resolved ticket, and when the run limit is passed, each with the message above.
- `verdict` with no review pending exits 2 and leaves the state file and `git status` unchanged. `bash tests/run.sh` exits 0 with a check for every bullet in the `flow-step.sh` section.

## Reference

- spec.md § Interfaces, Edge cases
- scripts/auto-flow.sh (read only; `review`, `send_back`, `count_run`, the final loop)
- scripts/flow-step.sh from ticket 02
- tests/run.sh (the `flow-step.sh` section from ticket 02)

## Answer

