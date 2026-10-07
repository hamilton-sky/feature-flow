# Acceptance: run the bar end to end

Type: task
Status: resolved
Blocked by: 02, 03, 04, 05, 07, 08
Test first: no

Run the map's bar: `python3 -m unittest discover -s tests/py && bash tests/run.sh`. In the output, find and copy into the Answer the passing test for each of (a) a failing Done when check sent back before REVIEW, (b) a `Test first: yes` ticket without a failing test first sent back, (c) a correct ticket passing both checks, (d) the debugging guide only on a retry build prompt, (e) spec then quality review with a FAIL in either sending back, and the `tests/run.sh` lines for the demo driven to REVIEW with `DONEWHEN-PASS` and `TESTFIRST-PASS`. Do not edit any file but this ticket's Status and Answer.

## Not in this ticket

- CI on the pull request (checked by the thread); a paid `--interactive` run; a Codex run.

## Done when

- `python3 -m unittest discover -s tests/py && bash tests/run.sh` exits 0.
- The Answer names the test for each of (a) to (e) and quotes the demo's `ok` lines.

## Reference

- map.md (the bar), tests/py/test_proof.py, tests/run.sh

## Answer


**Built**: nothing. Only this ticket's Status and Answer changed; no code, no other file.

**Proof**: `python3 -m unittest discover -s tests/py` printed `Ran 220 tests in 87.535s` / `OK` (exit 0), then `bash tests/run.sh` printed `457 passed, 0 failed` (exit 0). Both run fresh with `-v`, one after the other, which is the bar's `&&` form. The passing tests, from the `-v` output:

- (a) failing Done when check sent back before REVIEW: `test_a_failing_check_is_sent_back_before_review (test_proof.Conducted...) ... ok` (asserts BUILD again, a `done when` finding, `DONEWHEN-FAIL`, no REVIEW in the log).
- (b) `Test first: yes` without a failing test first sent back: `test_no_test_only_commit_is_sent_back`, `test_test_and_code_in_one_commit_is_sent_back` and `test_a_test_only_commit_that_passes_is_sent_back` (all `test_proof.TestFirst ... ok`).
- (c) a correct ticket passing both checks: `test_a_passing_check_reaches_review (test_proof.Conducted ...) ... ok` for the Done when check, and `test_a_failing_test_commit_then_code_reaches_review (test_proof.TestFirst ...) ... ok` for test first. Also the demo lines below, where one ticket gets both `DONEWHEN-PASS` and `TESTFIRST-PASS`.
- (d) debugging guide only on a retry: `test_debug_build_prompt_after_a_failing_gate_carries_the_guide (test_debug.DebugGuide ...) ... ok` and `test_debug_first_build_prompt_has_no_debugging_guide (test_debug.DebugGuide ...) ... ok`.
- (e) spec then quality review, a FAIL in either sends back: `test_review_pass_a_fail_in_the_spec_pass_builds_the_same_ticket_again`, `test_review_pass_a_fail_in_the_quality_pass_builds_the_same_ticket_again`, `test_review_pass_one_pass_hands_out_the_quality_review_of_the_same_ticket`, `test_review_pass_second_pass_picks_the_next_ticket` (all `test_review_pass.ReviewPasses ... ok`).

Demo lines from `tests/run.sh` (section "smoke-real.sh, the prepared demo driven through the checks"):

```
  ok    the demo drive: next hands out BUILD for 01
  ok    the demo reaches REVIEW with the checks on
  ok    and the log has GATE-PASS
  ok    and GUARD-PASS
  ok    and DONEWHEN-PASS
  ok    and TESTFIRST-PASS
  ok    after one PASS the demo gets its second REVIEW
  ok    after the second PASS it gets BUILD for 02
  ok    the demo with test and code in one commit is built again
  ok    with a test first finding
  ok    and TESTFIRST-FAIL in the log
```

**Decisions**: where the bar names one behaviour and several tests cover it, I listed all that apply instead of picking one.

**Shortcuts taken**: none.

**For later tickets**: none. This is the last ticket.
