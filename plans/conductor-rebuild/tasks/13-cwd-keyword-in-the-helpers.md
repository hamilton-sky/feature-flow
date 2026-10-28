# Give the helpers outside the package an optional cwd= keyword

Type: task
Status: open
Blocked by: 12
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/git.py, feature_flow/proc.py, feature_flow/checks.py, feature_flow/gate.py, feature_flow/floorguard.py, feature_flow/status.py, tests/py/test_cwd.py

Step 9 of the design, the part outside the package (spec.md § Decisions, cwd instead of chdir). The conductor runs these helpers in process, and each depends on the working folder today; give each an optional `cwd=None` keyword, where None means the process's working folder, so every existing caller (the conductor, `scripts/`, the tests) behaves exactly as now. Nothing in the package calls the keyword yet: ticket 15 does. Blocked by ticket 12 to keep the brief's order of steps (spec.md § Decisions, Order of the work), not because of a shared file.

- `git.py`: `_git` and `show_text` pass `cwd` to `subprocess.run`; the functions built on them (`toplevel`, `head`, `is_clean`, `changes`, `diff_names`, `diff_size`, and the rest) take `cwd=None` and pass it on. `tests/py/test_proof.py` patches `git._git` with `fail(*args, **kw)`, so the keyword must reach `_git` as a keyword.
- `proc.py`: `run(args, use_shell, log, minutes, cwd=None)` passes it to `Popen`.
- `gate.py`: `run(feature, out, err, timeout=None, quick=False, cwd=None)` reads `commands.md` (the `FLOW_DIR` or `plans` path) under `cwd` and runs the Test or Quick command there.
- `floorguard.py`: `run(argv, out, err, environ=None, cwd=None)`; its git calls (the `subprocess.run(["git", ...])` in its git helper) run in `cwd`, and the ticket folder (`FLOW_DIR` or `plans`) is read under it.
- `status.py`: `run(argv, out, err, cwd=None)` reads the plan folder under `cwd`.
- `checks.py`: `flow_status`, `gate`, `floor_guard` and `smoke` take `cwd=None` and pass it to the above.

Every line these print keeps the relative paths it prints now. `scripts/` is not edited (its callers do not pass the keyword).

Add `tests/py/test_cwd.py` (new): with two throwaway repos, a git helper, `checks.gate`, `checks.floor_guard`, `checks.flow_status` and `checks.smoke` called with `cwd=` the second repo act on it (its commits, its plan, its commands.md) and leave `os.getcwd()` unchanged; called without `cwd=` they act on the working folder, as before.

## Not in this ticket

- `proof.py` and the conductor using the keyword, and removing `os.chdir`: ticket 15.
- `feature_flow/lanes.py`'s helpers: they already take the folder as an argument (`git_in`).

## Done when

- `python3 -m unittest discover -s tests/py -p "test_cwd.py" -v` prints `OK`.
- The six helpers accept `cwd` (the check below prints `cwd ok`).
- `bash tests/run.sh` passes, including `tests/py/test_proof.py`, `tests/py/test_floorguard.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_cwd.py" -v
prints OK
$ python3 -c "import inspect,sys; from feature_flow import git, proc, gate, status, checks, floorguard; fs=[git._git, proc.run, gate.run, status.run, floorguard.run, checks.gate, checks.floor_guard, checks.flow_status, checks.smoke]; bad=[f.__module__ + '.' + f.__name__ for f in fs if 'cwd' not in inspect.signature(f).parameters]; print('cwd ok' if not bad else 'no cwd: %s' % bad); sys.exit(1 if bad else 0)"
prints cwd ok
```

## Reference

- spec.md § Decisions (cwd instead of chdir), § Edge cases (code that runs in a lane after the switch; a test that patches `git._git`)
- `feature_flow/git.py`, `feature_flow/proc.py`, `feature_flow/checks.py`, `feature_flow/gate.py` (`run`, the `commands.md` path), `feature_flow/floorguard.py` (`run`, its git helper, the ticket folder), `feature_flow/status.py` (`run`)

## Answer
