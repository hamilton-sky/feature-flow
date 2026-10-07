# Acceptance: run the bar end to end

Type: task
Status: open
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

