# Document the new checks and the two reviews, and bump the version to 0.3.0

Type: task
Status: resolved
Blocked by: 03, 04, 05, 06, 07
Test first: no

Update `README.md`: the "How a ticket flows" diagram (Done when checks and test-first check after the floor guard; spec review then quality review; the debugging guide on a send-back); "What the script checks and what it trusts" (the conductor now runs the Done when `check` block and proves the red test commit itself; the verdicts are still relayed); the ticket format block (the `check` block under Done when); the settings table row for `FLOW_GATE` (`off` also skips the Done when and test-first checks); the line on the run limit; "What is tested". Set `__version__ = "0.3.0"` in `feature_flow/__init__.py`. If the installer-copy test from guard-hardening fails because a file it writes into `.claude/` or `.agents/` changed, refresh those copies with `python3 install.py . --agent all --force` and commit only `.claude/` and `.agents/`.

## Not in this ticket

- Tagging `v0.3.0`: the user pushes the tag.
- Guide wording: tickets 04, 05 and 06.

## Done when

- `python3 -c "import feature_flow; print(feature_flow.__version__)"` prints `0.3.0`.
- `grep -c '```check' README.md` and `grep -c "quality review" README.md` and `grep -c "debug" README.md` each print 1 or more.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Goal and the bar, § Design
- README.md (How a ticket flows, the ticket format, settings table, What is tested), feature_flow/__init__.py

## Answer


**Built**: `README.md` (flow diagram with Done when checks, test-first check, spec then quality review and the debugging guide on a send-back; "What the script checks and what it trusts"; the ticket format block with a `check` example, its fence widened to four backticks so the inner fence nests; the `FLOW_GATE` row; the run limit line; the Tests paragraph) and `feature_flow/__init__.py` (`__version__ = "0.3.0"`).

**Proof**:
- `python3 -c "import feature_flow; print(feature_flow.__version__)"` printed `0.3.0`.
- `grep -c '```check' README.md` printed 2; `grep -c "quality review" README.md` printed 3; `grep -c "debug" README.md` printed 2.
- `python3 -m unittest discover -s tests/py && bash tests/run.sh` exited 0, ending `457 passed, 0 failed`.

**Decisions**: the installer-copy test passed, so `.claude/` and `.agents/` were not refreshed. The README run limit line stays generic (no formula), saying both reviews count as phases.

**Shortcuts taken**: none.

**For later tickets**: ticket 09 can run the real demo; the version is already 0.3.0 and the tag `v0.3.0` is the user's to push.
