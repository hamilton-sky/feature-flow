# Learnings: trusted-checks

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (plan) The holes were reproduced on main 69b993c with `tests/py/helpers.Repo` before planning: (a) `return` at the top of `Conductor.check_code` plus a committed build gives `REVIEW`, no STOP; (b) `phase=` written into `flow-f.state` after resolving 01 makes `next` print `BUILD ... 02-b.md`; (c) a `Test:` command whose script rewrites `feature_flow/conductor.py` runs inside `next`, which still prints `REVIEW`; a planted `scripts/secrets.py` makes `start` print `OK planted`. Goal 1(b) of the brief is therefore built, not dropped.
- (01) In Python 3.13 `from pathlib import Path` imports `glob` -> `re`, so a script must drop `sys.path[0]` before importing pathlib; `-I`/`-P` never add the script folder, so check `sys.flags.isolated`/`safe_path` before deleting.
- (02) Tests that drive `next`, `prompt` or `verdict` need `FLOW_TRUSTED=1` (helpers.Repo.flow and tests/run.sh set it); a test helper that strips `FLOW_*` from the env must add it back. `bash tests/run.sh` takes over 2 minutes: run it in the background.
- (02) `state.read_bytes/read_text/write_text/remove/load/save` record for the flow-state report only when given `kind="state"` or `"findings"`; a new caller touching the conductor's files must pass it.
- (03) In `helpers.Repo` there are no guides or roles, so `prompt` through the runner ends in the conductor's 'cannot find agents/...' STOP. Use `next` (BUILD) or check only the TRUST line. `start` again on an owned run needs `FLOW_TAKEOVER=1`. `tests/py/test_install.py` pins the exact list of installed `scripts/` files, so a new script must be added there.
