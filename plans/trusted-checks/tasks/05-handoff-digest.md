# Make the runner add the digest to HANDOFF

Type: task
Floor: allow flow-edit
Status: open
Blocked by: 03
Test first: yes

When the conductor's stdout line is `HANDOFF <invoke> <feature>`, `scripts/flow-trust.py` prints `HANDOFF <invoke> <feature> <digest>` instead, with the same digest as its `TRUST` line. The conductor itself does not change: its one-line output stays as it is. A new session passes that digest as `FLOW_TRUST` on its first call (`start`), so the comparison in the runner covers the gap between sessions with no new code path.

Tests in `tests/py/test_trust_runner.py`, with `FLOW_TICKETS_PER_SESSION=1`: after one ticket passes (resolve it, save a `REVIEW: PASS` reply for both review passes, as `tests/py/test_review_pass.py` does), the runner prints `HANDOFF /feature-flow f <digest>` equal to its `TRUST` digest; `start` with `FLOW_TRUST=<that digest>` then goes through; the same after editing `feature_flow/conductor.py` between the two calls STOPs naming it; and `start` with `FLOW_TRUST=new` (an old-style line with no digest) still works.

## Not in this ticket

- The skill reading the digest from the typed line and warning when there is none: ticket 06.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"` prints `OK` with the HANDOFF cases above.
- Run directly with `FLOW_TRUSTED=1`, `python3 scripts/flow.py f next` at the same point still prints exactly `HANDOFF /feature-flow f` (a test in `test_trust_runner.py`).
- `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_trust_runner.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Decisions (HANDOFF digest)
- `feature_flow/conductor.py` (`handoff`), `tests/py/test_review_pass.py`

## Answer
