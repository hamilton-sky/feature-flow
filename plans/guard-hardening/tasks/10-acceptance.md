# Acceptance: run the bar end to end

Type: task
Status: resolved
Blocked by: 09
Test first: no

Run the map's bar: `python3 -m unittest discover -s tests/py && bash tests/run.sh`. Then run the three tamper tests from ticket 01 against 0.1.6: check out the `v0.1.6` tag into a temp folder, copy `tests/py/test_tamper.py` and `tests/py/helpers.py` there and run `python3 -m unittest discover -s tests/py -k tamper`; the three STOP tests must fail there and pass here. Put the two outputs in this ticket's Answer. Do not edit any file but this ticket's Status and Answer.

## Not in this ticket

- CI on the PR (the PR is checked by the thread); a real Codex or Windows agent run.

## Done when

- The Answer shows the suite passing on the branch and the three tamper tests failing on `v0.1.6`.

## Reference

- map.md (the bar), tests/py/test_tamper.py

## Answer

**Built**: no files; only this Answer and Status. Ran from HEAD 3f2e325 (two commits after the ticket's start 89afee0).

**Proof**:
- `python3 -m unittest discover -s tests/py`: `Ran 169 tests in 58.321s`, `OK`, exit 0.
- `bash tests/run.sh`: `441 passed, 0 failed`, exit 0.
- Branch, `python3 -m unittest discover -s tests/py -k tamper -v`: `Ran 5 tests in 4.454s`, `OK` (CommittedInstall, PrivateInstall, SourceCheckout STOP tests, EditBeforeStart and FlowEditAllowed all ok).
- v0.1.6: `git archive v0.1.6 | tar -x -C <tmp>/v016`, copied tests/py/test_tamper.py and tests/py/helpers.py over (the branch's helpers worked, no other helper files needed), same command run there: `Ran 5 tests in 4.234s`, `FAILED (failures=3)`:
  - `CommittedInstall ... FAIL`, `AssertionError: 0 != 1 : REVIEW plans/f/tasks/01-a.md 01 22e0a3c9...`
  - `PrivateInstall ... FAIL`, `AssertionError: 0 != 1 : REVIEW plans/f/tasks/01-a.md 01 8198f643...`
  - `SourceCheckout ... FAIL`, `AssertionError: 0 != 1 : REVIEW plans/f/tasks/01-a.md 01 457a1b24...`
  - `EditBeforeStart ... ok`, `FlowEditAllowed ... ok`
  So 0.1.6 lets a tampered install through to REVIEW (exit 0) where the branch stops it (exit 1).

**Decisions**: the v0.1.6 copy was in a temp folder outside the repo; /home/user/ff-0.1.6 and .feature-flow/state/ were not touched.

**Shortcuts taken**: none.

**For later tickets**: none; this is the last ticket.
