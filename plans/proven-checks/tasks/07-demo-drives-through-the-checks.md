# Give the demo check blocks and drive it through the new checks

Type: task
Status: open
Blocked by: 03, 04
Test first: no

In `tests/smoke-real.sh`, add a `check` block to both demo tickets' Done when (ticket one: `$ python3 -m unittest test_hello` and `$ python3 -c "from hello import greet; assert greet('Ada') == 'Hello, Ada!'"`; ticket two: `$ python3 hello.py Ada` with `prints Hello, Ada!`, and the unittest line). In the `--interactive` checks list, also require `DONEWHEN-PASS` per ticket and `TESTFIRST-PASS` for ticket 01.

In `tests/run.sh`, section `smoke-real.sh, prepare only`, add a drive of a prepared demo with no model: `start`; `next` gives `BUILD` for 01; play the builder by committing `test_hello.py` alone (it fails: no `hello` module), then `hello.py` with the ticket set to resolved; `next` must print `REVIEW plans/hello/tasks/01-greet-function.md 01 <base>` and the log must have `GATE-PASS`, `GUARD-PASS`, `DONEWHEN-PASS` and `TESTFIRST-PASS`; then a `REVIEW: PASS` verdict gives a second `REVIEW`, and a second PASS gives `BUILD` for 02. A second drive commits test and code together and must get `BUILD` of 01 again with a `test first` finding. Use the installed `scripts/flow.py` in the prepared folder.

## Not in this ticket

- The paid `--interactive` run itself (`RUN_REAL=1`); it is not part of the bar.
- Unit tests of each check: tickets 02 and 03 own them.

## Done when

- `bash tests/run.sh` passes, and its output has an `ok` line for the demo reaching `REVIEW` with `DONEWHEN-PASS` and `TESTFIRST-PASS` in the log, for the second `REVIEW` after one PASS, and for the test-and-code-together build being sent back.
- `bash tests/smoke-real.sh --prepare "$(mktemp -d)/p"` exits 0 and the prepared `plans/hello/tasks/01-greet-function.md` contains a line that is exactly ```` ```check ````.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Happy path
- tests/smoke-real.sh, tests/run.sh (section `smoke-real.sh, prepare only`, helpers `expect_has`, `expect_rc`)

## Answer

