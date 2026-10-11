# Acceptance: drive small and large tickets through the conductor

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06
Test first: no

Add `tests/py/test_small_drive.py`, the bar. In a fixture repo built with `tests/py/helpers.py`'s `Repo` (the real `agents/` and `guides/` copied in, as `tests/py/test_review_pass.py` does), with `commands.md` giving a passing `Test:` command, write a plan whose tickets each carry a check block, and drive it with `start`, `next`, `prompt` and `verdict` the way the skill does, committing a builder's change for each `BUILD` and replying `REVIEW: PASS` for each `REVIEW`:

- a small ticket (one file, a few lines) → exactly one `REVIEW` before the next `BUILD`, its prompt says `(single pass)`, the log has `REVIEW-SMALL`;
- the same small change in a ticket with `Review: full` → two `REVIEW`s, `(spec pass)` then `(quality pass)`;
- a small ticket with no check block → two;
- a small `Type: convert` ticket → two;
- a ticket whose change is over 60 lines → two;
- the whole plan again with `FLOW_SMALL_LINES=0` → two for every ticket;
- the drive ends in `DONE`.

Then run the full suites.

## Not in this ticket

- A real agent run in Claude Code or Codex: not from the cloud; the user can run one on their machine.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_small_drive.py"` prints `OK`.
- `python3 -m unittest discover -s tests/py` prints `OK`, and `bash tests/run.sh` exits 0.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_small_drive.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
$ bash tests/run.sh
exit 0
```

## Reference

- map.md § The bar
- `tests/py/test_review_pass.py`, `tests/py/test_fixture_drive.py`, `tests/py/helpers.py`

## Answer
