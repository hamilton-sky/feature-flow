# Learnings: proven-checks

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) `tests/run.sh` allows only listed stdlib modules in `feature_flow/` imports (no `collections`: use `dataclasses`); the unittest suite alone does not catch it.
- (02) `tests/py` Repo tests that call `prompt` need `agents/` and `guides/` copied in and committed first, or `next` STOPs on a dirty tree. Running the full suite plus `tests/run.sh` takes about 2 minutes: run it in the background.
