# Catch focused and skipped tests the guard misses

Type: task
Status: resolved
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


**Built**: `feature_flow/floorguard.py` (SKIP extended with `self.skipTest(`, `pytest.importorskip`, `@unittest.expectedFailure`, `t.Skipf(`, `t.SkipNow(`, `#[ignore = `, appended after the old alternatives; new `FOCUSED` regex; `diff_findings` reports `skip` for a FOCUSED hit only when the file path matches `DELETED_TEST`). `tests/py/test_floorguard.py` (new `MoreSkipTests`: caught and look-alike tests per pattern).

**Proof**:
- `python3 -m unittest discover -s tests/py -k floorguard`: Ran 26 tests, OK (the 4 new tests loop over every new pattern with subTests, caught and clean). Before the code change the new tests failed (12 subtest failures).
- `diff_findings` run directly: `self.skipTest("x")` gives `skip: a.py: ...`; `it.only(` in `a.test.js` gives `skip:`; `fit('x')` in `a.spec.js` gives `skip:`; `model.fit(x)` in `train.py` gives `b''`.
- Full `python3 -m unittest discover -s tests/py`: 143 tests OK. `bash tests/run.sh`: 441 passed, 0 failed.

**Decisions**: `fit(`/`fdescribe(` use lookbehinds `(?<!def )(?<![A-Za-z0-9_.])`; `.only(` covers it/describe/test.only. A line matching both SKIP and FOCUSED is reported once. `pytest.importorskip` is a prefix match as the ticket wrote it (no paren).

**Shortcuts taken**: none.

**For later tickets**: the first run.sh after the change showed 440 passed, 1 failed, and a rerun after fixing my own look-alike test showed 441/0; I did not identify which check failed the first time. Ticket 05 (mawk removal) can ignore the mawk comparison for the new patterns: mawk does not support lookbehind, so the bash version never had them.
