# Learnings: trusted-checks

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (plan) The holes were reproduced on main 69b993c with `tests/py/helpers.Repo` before planning: (a) `return` at the top of `Conductor.check_code` plus a committed build gives `REVIEW`, no STOP; (b) `phase=` written into `flow-f.state` after resolving 01 makes `next` print `BUILD ... 02-b.md`; (c) a `Test:` command whose script rewrites `feature_flow/conductor.py` runs inside `next`, which still prints `REVIEW`; a planted `scripts/secrets.py` makes `start` print `OK planted`. Goal 1(b) of the brief is therefore built, not dropped.
- (01) In Python 3.13 `from pathlib import Path` imports `glob` -> `re`, so a script must drop `sys.path[0]` before importing pathlib; `-I`/`-P` never add the script folder, so check `sys.flags.isolated`/`safe_path` before deleting.
- (02) Tests that drive `next`, `prompt` or `verdict` need `FLOW_TRUSTED=1` (helpers.Repo.flow and tests/run.sh set it); a test helper that strips `FLOW_*` from the env must add it back. `bash tests/run.sh` takes over 2 minutes: run it in the background.
