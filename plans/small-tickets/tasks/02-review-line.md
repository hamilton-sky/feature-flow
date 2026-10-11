# Read the ticket's `Review:` line and check its value

Type: task
Floor: allow flow-edit
Status: open
Blocked by: —
Test first: yes

A ticket may carry `Review: full` or `Review: auto` among its header lines (before the first `## ` heading). `auto` is the default when the line is missing.

1. Add `review_mode(text)` to `feature_flow/proof.py`, beside `wants_test_first` and written the same way: it reads the header lines only, is case insensitive on the value, and returns `"full"` or `"auto"`. Any other value returns `"auto"` here; the plan check below is what rejects it.
2. In `feature_flow/tickets.py`'s `Graph._read`, read `Review:` from the first 20 lines the way `Test first:` is read (a `hasreview` set and a `review` dict). In `feature_flow/status.py`'s `_check`, add the error `NN: Review must be full or auto` when the line is there with another value.

Tests: `review_mode` on a ticket with `Review: full`, `Review: FULL`, `Review: auto`, no line, and a `Review: full` that appears only below `## Done when` (ignored); and `flow-status.py --check` failing on `Review: maybe` with that message and passing on `full` and `auto`. Put them all in a new `tests/py/test_review_line.py`.

## Not in this ticket

- Acting on the value in the conductor: ticket 04.
- The ticket template and the planner guide: ticket 05.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_review_line.py" -v` prints `OK`, and lists a test with `review_mode` in its name and one with `maybe` in its name (the plan with `Review: maybe`, whose `--check` output contains `Review must be full or auto`).
- All existing tests still pass: `python3 -m unittest discover -s tests/py` prints `OK`.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_review_line.py" -v
prints review_mode
prints maybe
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Interfaces
- `feature_flow/proof.py` (`wants_test_first`), `feature_flow/tickets.py` (`Graph._read`), `feature_flow/status.py` (`_check`)

## Answer
