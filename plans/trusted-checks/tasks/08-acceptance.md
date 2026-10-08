# Acceptance: drive the flow the way the skill does and show every tamper ends in STOP

Type: task
Status: open
Blocked by: 01, 02, 04, 05, 06, 07
Test first: no

Add `tests/py/test_trust_drive.py`. It extracts the loader line and pinned sha from `skills/feature-flow/SKILL.md` (as the skill test does), builds a two-ticket fixture repo (`helpers.Repo`, with a `commands.md` whose commands use the interpreter running the test, as `tests/py/test_fixture_drive.py` does), and drives it only through the loader, passing each `TRUST` digest on to the next call and `--after-build` after each BUILD, exactly as the skill says. Point `CLAUDE_HOME`, `AGENTS_HOME` and `FEATURE_FLOW_HOME` at temp folders.

Cases, each from a fresh repo:

- Untampered: resolve each ticket, save `REVIEW: PASS` replies for both passes, and reach `DONE`.
- (a) a builder commit that makes `check_code` return early → `STOP` naming `feature_flow/conductor.py`.
- (b) the builder resolves 01 and writes `phase=` into `flow-f.state` → `STOP` naming the state file, and no `BUILD` for 02 is ever printed.
- (c) the builder's committed test script, run by the plan's `Test:` command, edits `feature_flow/conductor.py` during `next` → `STOP flow code changed during next`.
- A new `.py` file in `feature_flow/`, and an edited guide, role, skill and state file → each a `STOP` naming it.
- A planted `.pyc` for an edited `conductor.py` (source unchanged) is not run.
- No STOP for a new `__pycache__` file or the review-reply file.

Then run the full suites. This ticket proves the map's bar; if a case fails, fix the code in the ticket that owns it and say so in the Answer.

## Not in this ticket

- A real Claude Code, Codex or Windows agent run: out of scope (no Codex from the cloud; Windows runs the unit tests in CI).

## Done when

- `python3 -m unittest discover -s tests/py -p "test_trust_drive.py"` prints `OK`.
- `python3 -m unittest discover -s tests/py -p "test_fixture_drive.py"` prints `OK`.
- `python3 -m unittest discover -s tests/py` prints `OK` and `bash tests/run.sh` exits 0.

```check
$ python3 -m unittest discover -s tests/py -p "test_trust_drive.py"
prints OK
$ python3 -m unittest discover -s tests/py -p "test_fixture_drive.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
$ bash tests/run.sh
exit 0
```

## Reference

- map.md § Destination (the bar)
- `tests/py/test_fixture_drive.py`, `tests/py/test_review_pass.py`, `tests/py/helpers.py`
- learnings.md (the repros)

## Answer
