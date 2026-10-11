# Learnings: quick-gate

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

(01) Test helpers: tests/py/test_gate.py shows the throwaway plans folder pattern (chdir to a temp dir, clear FLOW_DIR); bash only.
(01) Gate test commands: use '"<sys.executable>" script.py Name' (double quotes only) so they run under bash and cmd.exe; never skip tests on Windows.
(02) Conductor tests: put logger script, log and verdict files outside the Repo dir (a stray file dirties the tree); the flow consumes the verdict file.
