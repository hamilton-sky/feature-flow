# Learnings: conductor-rebuild

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) A golden mismatch prints the scenario, the first differing line, its section (calls, log events, state keys) and a diff; run one scenario with `python3 -m unittest test_golden.Golden.test_lanes` from tests/py (about 4 s each, all 14 in about 35 s).
- (03) The system python3 has no `build` module: `python3 -m venv <scratch>/venv && <scratch>/venv/bin/pip install build`, then run `<scratch>/venv/bin/python tests/package_smoke.py` (prints `all passed`).
