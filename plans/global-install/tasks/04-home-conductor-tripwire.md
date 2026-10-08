# Prove the home conductor runs from a repo and the code-hash tripwire covers it

Type: task
Status: open
Blocked by: 01
Test first: no

Add `tests/py/test_home_conductor.py`. It installs with `install.run(["--user", ...])` into a temp home (set `HOME`, `CLAUDE_HOME`, `AGENTS_HOME`, `FEATURE_FLOW_HOME` there), builds a git repo that has a plan (reuse the plan files `helpers.Repo` writes, but without its `scripts/` and `feature_flow/` copies; add an optional argument to `Repo` if that is the least code) and runs the home `scripts/flow.py` from the repo as a subprocess, as `Tamper.begin()` in `tests/py/test_tamper.py` does for a repo install.

The tripwire needs no code change: `codehash.flow_code` hashes the running package and the `scripts` folder, with absolute names for files outside the repo. This ticket only proves it. If a test fails because it does need one, fix `feature_flow/codehash.py` in this ticket and say so in the Answer.

## Not in this ticket

- The first-line comparison with a repo install on a fresh repo: ticket 07 (acceptance).
- Skill text: ticket 05.

## Done when

- `start` then `next` from the home conductor print `OK <token>` then `BUILD ...`, and the run state (`flow-f.state`) is under the repo's `.feature-flow/state/`, with nothing new written in the home folder except what the install wrote.
- Appending a line to `$FEATURE_FLOW_HOME/feature_flow/floorguard.py` (and, in a second test, to `$FEATURE_FLOW_HOME/scripts/flow.py`) during the build makes the next `next` print `STOP flow code changed while building`.
- With a repo-local install present as well, the repo's `scripts/flow.py` run is not affected by edits to the home copy (no STOP).
- `python3 -m unittest discover -s tests/py -p "test_home_conductor.py"` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_home_conductor.py"
prints OK
```

## Reference

- `tests/py/test_tamper.py`, `tests/py/helpers.py` (`Repo`)
- `feature_flow/codehash.py`: `flow_code`, `_files`, `_name`

## Answer

