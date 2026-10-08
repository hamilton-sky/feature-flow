# Learnings: trusted-checks

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (plan) The holes were reproduced on main 69b993c with `tests/py/helpers.Repo` before planning: (a) `return` at the top of `Conductor.check_code` plus a committed build gives `REVIEW`, no STOP; (b) `phase=` written into `flow-f.state` after resolving 01 makes `next` print `BUILD ... 02-b.md`; (c) a `Test:` command whose script rewrites `feature_flow/conductor.py` runs inside `next`, which still prints `REVIEW`; a planted `scripts/secrets.py` makes `start` print `OK planted`. Goal 1(b) of the brief is therefore built, not dropped.
