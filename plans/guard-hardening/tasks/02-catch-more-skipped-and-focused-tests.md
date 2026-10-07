# Catch focused and skipped tests the guard misses

Type: task
Status: open
Blocked by: 01
Test first: yes
Floor: allow skip, suppress, threshold

In `feature_flow/floorguard.py` extend the `skip` category. Add `self.skipTest(`, `pytest.importorskip`, `@unittest.expectedFailure`, Go `t.Skipf(` and `t.SkipNow(`, and Rust `#[ignore = `. Add focused tests: `.only(` (`it.only`, `describe.only`, `test.only`), and `fit(`, `fdescribe(`. The focused patterns must not hit look-alikes: `fit(` and `fdescribe(` count only when not preceded by a word character, `.` or `def ` (so `model.fit(x)`, `def fit(self)` and `outfit(` are clean), and all three (`.only(`, `fit(`, `fdescribe(`) are findings only on a path that looks like a test (reuse the path idea of `DELETED_TEST`; `qs.only("a")` in `app/models.py` is clean). Keep the existing patterns and their order. Tests go in `tests/py/test_floorguard.py` using its `diff()` helper: for each new pattern one line that is caught and one look-alike that is not.

## Not in this ticket

- Config files and the assertion count: tickets 03 and 04.
- Removing the mawk code: ticket 05.

## Done when

- `python3 -m unittest discover -s tests/py -k floorguard` passes and includes, per new pattern, a caught and a not-caught test.
- `diff_findings` reports `skip:` for `self.skipTest("x")`, `it.only(` in `a.test.js`, `fit(` at the start of a JS line in `a.spec.js`, and nothing for `model.fit(x)` in `train.py`.
- All existing tests still pass.

## Reference

- spec.md § Design (Goal 2)
- feature_flow/floorguard.py (`SKIP`, `diff_findings`), tests/py/test_floorguard.py

## Answer

