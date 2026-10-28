# Add the size ratchet and prove the bar end to end

Type: task
Status: open
Blocked by: 13, 16
Test first: no
Level: 3
Touches: tests/py/test_conductor_package.py

Step 10 of the design, and the acceptance ticket. Add the ratchet to `tests/py/test_conductor_package.py` (new in ticket 03): a test method named `test_ratchet` checks that `feature_flow/conductor/facade.py` (new in ticket 03 too) is under 300 lines and every other `.py` file under `feature_flow/conductor/` is under 400, each failure naming the file and its count. `Test first: no`: ticket 16 already brought the sizes down, so the test cannot fail before it is written.

Then run the bar of map.md and the acceptance tests (spec.md § Acceptance tests, A1 to A4, which the tester wrote before ticket 01; A3 proves a run paused at a `HANDOFF` on the old code resumes on the new; A4 that a run paused mid-ticket meets today's `check_code` STOP), and record in the Answer: each check's last line, and `git log --oneline -- tests/py/golden`, which must list only ticket 01's commits. If anything fails, do not fix it here: reopen the ticket it belongs to with the finding, and say so in the Answer.

## Not in this ticket

- Any code change under `feature_flow/`: the tickets before this one.
- `tests/py/golden/` and `plans/conductor-rebuild/acceptance/`: never changed by a builder.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v` lists `test_ratchet` and prints `OK`.
- `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` prints the three classes, and `feature_flow/conductor.py` does not exist.
- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v` prints `OK`, with A3 (a run paused at a `HANDOFF` on the old code resumes on the new) and A4 (a run paused mid-ticket meets today's `check_code` STOP) among the tests it ran.
- `bash tests/run.sh` prints `0 failed` and exits 0.
- The Answer shows `git log --oneline -- tests/py/golden` listing only ticket 01's commits.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v
prints test_ratchet
prints OK
$ python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"
prints NoPhase
$ python3 -c "import os,sys; gone = not os.path.exists('feature_flow/conductor.py'); print('conductor.py gone:', gone); sys.exit(0 if gone else 1)"
prints conductor.py gone: True
$ python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v
prints OK
$ bash tests/run.sh
prints , 0 failed
```

## Reference

- map.md § Destination (the bar), spec.md § Goal and the bar, § Acceptance tests, § Edge cases (a run paused on the old code)
- `tests/py/test_conductor_package.py` and `tests/py/test_golden.py` (new in tickets 03 and 01)

## Answer
