# Learnings: proven-checks

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) `tests/run.sh` allows only listed stdlib modules in `feature_flow/` imports (no `collections`: use `dataclasses`); the unittest suite alone does not catch it.
