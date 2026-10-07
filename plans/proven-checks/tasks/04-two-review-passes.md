# Review every ticket twice: spec, then quality

Type: task
Status: open
Blocked by: —
Test first: yes

Split `guides/review.md`: it keeps everything up to and including "Verdict 1: does it meet the ticket?" (Done when re-run, scope, test first), the rules on what the reviewer may read and must not do, and an output with only the `SPEC` part and the `REVIEW: PASS|FAIL` last line; `PASS` when every Done when is MET, scope OK, test first not MISSING. A new `guides/review-quality.md` holds the same reading rules and "Verdict 2: is it good?" with an output of only the `QUALITY` part and the same last line rule; `PASS` when there is no blocker or major finding. Keep both heading texts as they are (tests grep for them).

In `feature_flow/prompts.py` add a `review-quality` entry to `ROLES` (`ticket-reviewer.md`) and `GUIDES` (`review-quality.md`) and let `build` treat it like `review` (same task text, plus `(quality pass)`/`(spec pass)` so the two prompts differ). In `feature_flow/codehash.py` include the `review-quality` files in the fingerprint. Name every new test method `test_review_pass_...` so `-k review_pass` selects them. In `feature_flow/conductor.py`: the run state gets `review_pass` (`spec` when absent); `pick_ticket` and `send_back` set it to `spec`; `prompt` uses `review-quality` when it is `quality`; in `judge_review` a spec PASS sets `quality`, resets `review_attempt` and calls `hand_out_review` (same `REVIEW` line); a quality PASS picks the next ticket as today; a FAIL calls `send_back("spec review" | "quality review", findings)`. `run_limit` uses 3 phases per round instead of 2. Update the existing tests in `tests/run.sh` and `tests/py` that expect the next `BUILD` straight after one PASS so they pass twice; do not delete any.

## Not in this ticket

- The skill (`skills/feature-flow/SKILL.md`): it already spawns a fresh reviewer for every `REVIEW` line and needs no change.
- README: ticket 08.

## Done when

- `python3 -m unittest discover -s tests/py -k review_pass` passes with new tests: after one `REVIEW: PASS` the next line is `REVIEW <ticket> <NN> <base>` again and `prompt` contains `Verdict 2: is it good?` and not `Verdict 1`; after the second PASS the next line is `BUILD` for the next ticket; a FAIL in the spec pass and a FAIL in the quality pass each lead to `BUILD` of the same ticket with findings headed `spec review` and `quality review`; a reviewer commit during the quality pass gives `STOP`.
- `python3 -m unittest discover -s tests/py -k review_pass` passes, including tests that: a quality-pass reply with no verdict makes `verdict` print `RETRY no review verdict` and the next line is the same `REVIEW` with the quality prompt; after `FLOW_MAX_RETRIES` such replies in the quality pass `next` prints `STOP ... no review verdict ...`; with `FLOW_MAX_RETRIES=2`, one no-verdict reply in the spec pass, then a spec PASS, then one no-verdict reply in the quality pass still gets a quality `REVIEW` (attempts are counted per pass, not summed).
- `grep -c "REVIEW: PASS" guides/review.md guides/review-quality.md` prints 1 or more for each file.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Design (Two review passes), § Decisions
- guides/review.md, agents/ticket-reviewer.md (unchanged), feature_flow/conductor.py (`hand_out_review`, `judge_review`, `prompt`, `run_limit`), feature_flow/prompts.py, feature_flow/codehash.py, tests/run.sh (section `flow.py, review verdict and finish`), tests/py/test_conductor.py

## Answer

