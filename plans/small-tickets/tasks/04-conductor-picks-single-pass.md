# Give a small, checked ticket one combined review

Type: task
Floor: allow flow-edit
Status: open
Blocked by: 01, 02, 03
Test first: yes

In `feature_flow/conductor.py`:

1. `Conductor.__init__` reads `FLOW_SMALL_FILES` (default 3) and `FLOW_SMALL_LINES` (default 60) with `_env_int`, so a bad value is the usual `STOP ... must be a whole number`.
2. At the end of `judge_build`, after every check has passed and just before `hand_out_review`, decide the pass. The ticket is small when all of these hold: the gate is on; `run_done_when` ran a check block and it passed (not `DONEWHEN-SKIP`); `proof.review_mode` of the ticket at base (`ticket_at_base`) is `auto`; the ticket at base is not `Type: convert`; `FLOW_SMALL_LINES` is above 0; and `git.diff_size(base, HEAD, <plan folder>)` gives no binary file, at most `FLOW_SMALL_FILES` files and at most `FLOW_SMALL_LINES` lines. Small → set `review_pass` to `single`, log `REVIEW-SMALL`, and add the note `the conductor judged this ticket small (<files> files, <lines> lines): one review covers the spec and quality passes`. Otherwise → `review_pass` `spec`, as today.
3. `hand_out_review` keeps the pass that `judge_build` set (it must not reset `single` to `spec`).
4. `judge_review`: a PASS on `single` picks the next ticket, like a quality PASS. A FAIL on `single` sends back with the source `single review`. `send_back` still resets the pass; the next build is measured again.
5. `prompt` uses the `review-single` phase when `review_pass` is `single`.

A run state saved by 0.5.0 (`review_pass` spec or quality, or missing) must carry on as before.

`tests/smoke-real.sh` drives a demo whose tickets have check blocks and small diffs, so they would now get one review each. Keep the demo covering both paths: give one of its tickets a `Review: full` line, and make its log checks expect `REVIEW-SMALL` for the others. `tests/run.sh` must stay green.

Tests in a new `tests/py/test_small_review.py`, using `helpers.Repo` with tickets that carry a check block: small and checked → `REVIEW`, state `review_pass=single`, prompt has `(single pass)`, PASS → `BUILD` of the next ticket; FAIL → findings headed `single review`, ticket reopened; `Review: full` at base → spec then quality; `Review: full` added by the builder after base → still single; no check block → spec; `Type: convert` → spec; diff over the line limit → spec; `FLOW_SMALL_LINES=0` → spec; `FLOW_SMALL_LINES=abc` → STOP; a 0.5.0 state mid quality pass → its PASS picks the next ticket.

## Not in this ticket

- The planner guide, the ticket template: ticket 05.
- README, Codex skill, version: ticket 06.
- The end-to-end drive that is the bar: ticket 07.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_small_review.py"` prints `OK`.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_small_review.py"
prints OK
```

## Reference

- spec.md § Happy path, § Edge cases, § Design
- `feature_flow/conductor.py` (`judge_build`, `run_done_when`, `hand_out_review`, `judge_review`, `send_back`, `prompt`), `tests/py/test_review_pass.py`, `tests/smoke-real.sh`

## Answer
