# Give the helpers outside the package an optional cwd= keyword

Type: task
Status: resolved
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

- **Built**:
  - `feature_flow/git.py`: `_git(*args, check=True, cwd=None)` and `show_text(revision_path, cwd=None)` pass `cwd` to `subprocess.run`. `git_dir`, `toplevel`, `head`, `diff_size`, `diff_names`, `changes`, `is_clean`, `tracked_clean`, `undo_tracked`, `commit_paths` and `commit_file` all take `cwd=None` and pass it to `_git` as a keyword, so test_proof's `fail(*args, **kw)` still forwards it. `undo_tracked` also runs its own `git diff --binary` in `cwd` and writes a relative `patch` under it.
  - `feature_flow/proc.py`: `run(args, use_shell, log, minutes, cwd=None)` passes it to `Popen`.
  - `feature_flow/gate.py`: `run(..., quick=False, cwd=None)` reads `<cwd>/<FLOW_DIR or plans>/<feature>/commands.md` and runs each command through `proc.run(..., cwd=cwd)`.
  - `feature_flow/floorguard.py`: `run(argv, out, err, environ=None, cwd=None)`. A new module helper `_under(cwd, path)` joins a path to cwd; `_find_ticket(dir_, num, cwd=None)` lists the folder under cwd and still returns the relative path; the `os.path.exists` and `open` of the ticket and the commands.md handed to `_content_config` go through `_under`; `_Guard(err, cwd)` runs every git call in cwd. Git paths (`base:./plans/...`, the `:(exclude)` root) stay relative, which git resolves from its cwd.
  - `feature_flow/status.py`: `run(argv, out, err, cwd=None)`. It uses its own `_under` for the folder check, `suggest.features`, `ticket_files`, learnings.md, and (through `_report(..., cwd)` and `lint(g, plan_dir, cwd=None)`) the ticket reads, the `os.path.exists` of the named paths and commands.md. When cwd is given, `g.path` is mapped back to `<folder>/<name>`, so `--next`, `--ready` and `--json` print the same relative paths as before.
  - `feature_flow/checks.py`: `flow_status(..., root=None, cwd=None)`, `gate(..., quick=False, cwd=None)`, `floor_guard(..., base, cwd=None)` and `smoke(command, timeout=None, cwd=None)` pass it on as a keyword.
  - New `tests/py/test_cwd.py` (5 tests). It uses two `helpers.Repo`s, chdirs into the first and points `cwd=` at the second, which has 3 tickets, its own commit and its own commands.md. Git helpers: head, toplevel, show_text, changes/is_clean, diff_names. `checks.gate` writes ran.txt in the right repo. `checks.floor_guard` finds a `unittest.skip` in the second repo, and without cwd says `no ticket 03 in plans/f/tasks`. `checks.flow_status` covers --counts, a relative --next path and --check. `checks.smoke` covers the working folder of the child. Every test checks that `os.getcwd()` is unchanged and that a call without cwd acts on the working folder.
  - Test-only commit 9a9fbf4: the discover command failed with `TypeError: ... got an unexpected keyword argument 'cwd'` in all 5 tests. After that I fixed one wrong expectation in the test itself: the third ticket's text holds `# C`, not `02-b`.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_cwd.py" -v`: `Ran 5 tests`, `OK`.
  - The signature check prints `cwd ok` (exit 0). The Smoke parse check exits 0.
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0, after the last edit. Also `test_proof test_floorguard test_gate test_timeout test_status test_lint test_diff_size test_buildchecks test_quick_gate_mode test_cwd`: `Ran 158 tests`, `OK`. `test_golden`: `Ran 14 tests`, `OK`. No existing test changed.
- **Decisions**:
  - A relative `FLOW_DIR` (or `root` in `checks.flow_status`) is taken under cwd, the same way `plans` is. An absolute one wins, because `os.path.join` drops cwd for an absolute path.
  - status.run builds its Graph from joined paths and then puts the relative paths back on `g.path`, because `tickets.py` and `suggest.py` are outside Touches. `tickets.Graph` and `ticket_files` are unchanged.
  - `checks.flow_status` keeps its FLOW_DIR environment swap for `root`. That is existing behaviour and not this ticket's.
- **Shortcuts taken**: none.
- **For later tickets**:
  - Ticket 15: pass `cwd=ws.folder` (None in the main worktree) to `git.*`, `checks.*` and `proc.run`. Every git function in git.py takes `cwd=` as a keyword. `undo_tracked(patch, cwd=)` writes a relative patch under cwd, so pass an absolute patch path if you mean the main top.
