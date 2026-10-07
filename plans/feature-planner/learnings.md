# Learnings: feature-planner

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (NN) <what you found, and what to do about it>
- (01) This host has `python3` but no `python`; tests/py/test_fixture_drive.py invokes `python`, so prepend a temporary `python` alias to `python3` when running the suite here.
- (01) Correction: the fixture now uses its running interpreter, so run `bash tests/run.sh` exactly; no PATH alias is needed.
- (01) The conductor gate inherits `FLOW_INVOKE`; `tests/run.sh` must clear it so its default-invocation assertions stay hermetic.
- (02) Ticket 01's planner role now checks the draft with `FLOW_DIR=.feature-flow/state/draft` and ends with `PLAN: READY` or `PLAN: QUESTIONS`; without Edit, a findings round rewrites draft files with Write.
