# Make the runner add the digest to HANDOFF

Type: task
Floor: allow flow-edit
Status: resolved
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

Work started at c021db0aa1b6eb76ab4c23a465e949a4fd58b768. Test-only commit: b98b9c3 (`test(trusted-checks): 05 failing test`). At that commit the new `Handoff` tests failed 4 of 6, each because the runner printed `HANDOFF /feature-flow f` with no digest. The direct-conductor test and the after-call STOP guard passed already, because they check that nothing changes there.

**Built**

- `scripts/flow-trust.py`: new `with_digest(out, feature, trusted)` rewrites each stdout line `HANDOFF <invoke> <feature>` to `HANDOFF <invoke> <feature> <digest>`. It works on bytes and keeps each line's own ending, so CRLF is fine. `main()` calls it only on the TRUST path, with the same digest as the TRUST line. The conductor is not changed.
- `tests/py/test_trust_runner.py`: new `Handoff` class (6 tests), all run with `FLOW_TICKETS_PER_SESSION=1`. Each test runs start, BUILD, resolve, then REVIEW plus a `REVIEW: PASS` verdict for the spec pass and again for the quality pass, all through the runner. Then:
  - the runner's `next` prints exactly `HANDOFF /feature-flow f <digest>`, where `<digest>` is that call's TRUST digest;
  - a new session's `start` with `FLOW_TRUST=<that digest>` prints TRUST then `OK <token>`;
  - if `feature_flow/conductor.py` is edited between the two calls, that `start` STOPs (`flow files changed since the last step`), names the file and prints no `OK`;
  - `start` with `FLOW_TRUST=new` (an old-style line with no digest) prints TRUST then `OK`;
  - `python3 scripts/flow.py f next`, run directly with `FLOW_TRUSTED=1` at the same point, prints exactly the one line `HANDOFF /feature-flow f` (checked on decoded bytes);
  - in process, with a fake killed conductor whose stdout is `HANDOFF /feature-flow f`, the STOP line comes first and the HANDOFF line follows with no digest.

**Proof**

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"`: `Ran 60 tests in 74.314s` / `OK`. The 6 `Handoff` tests cover the cases above.
- The direct `FLOW_TRUSTED=1 python3 scripts/flow.py f next` case is `test_the_conductor_run_directly_prints_handoff_unchanged` in that run. It passes, and its stdout lines are exactly `["HANDOFF /feature-flow f"]`.
- `python3 -m unittest discover -s tests/py`: `Ran 341 tests in 185.738s` / `OK`.
- `bash tests/run.sh` (the gate's Test command): `465 passed, 0 failed`, exit 0. Smoke command: exit 0.
- No added test skips, and none uses `.only(` or expectedFailure.

**Decisions**

- A line is matched when it starts with `HANDOFF ` and ends with ` <feature>`. That way an `FLOW_INVOKE` with spaces still matches, and other output is never touched.
- No digest is added after an after-call STOP. The runner does not trust that state, so it has no digest to hand on, and the line stays exactly as the conductor printed it. On the next session the skill then gets the old-style line, and ticket 06 makes it warn.

**Shortcuts taken**

- none

**For later tickets**

- 06: the line the user types is `HANDOFF <invoke> <feature> <digest>`. The digest is the fourth field, or the last field if the invoke has spaces. Pass it as `FLOW_TRUST` on `start`. If there is no digest, use `new` and warn. `start` after HANDOFF needs no `FLOW_TAKEOVER`, because HANDOFF releases the owner.
