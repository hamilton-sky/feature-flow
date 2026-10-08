# Add scripts/flow-trust.py: hash the flow's files, compare with the session's digest, run the conductor

Type: task
Floor: allow flow-edit
Status: resolved
Blocked by: —
Test first: yes

Add `scripts/flow-trust.py`, standard library only, Python 3.9+, importing nothing from the repo (it must work when run as `exec` of its bytes by the skill's loader: `sys.argv[0]` is `-c`, `sys.argv[1]` is the path of this file, `sys.argv[2]` the pinned hash, the rest its own arguments; `__file__` is not set). Also make it runnable directly as `python3 -I scripts/flow-trust.py <feature> <command> ...` for tests, by detecting which form it was started in.

Usage: `[--after-build <ticket> <sha>] <feature> <command> [args...]`. Accept and ignore `--after-build` here (ticket 04 gives it meaning). Steps:

1. Read `FLOW_TRUST`. Missing or empty: print `STOP pass FLOW_TRUST: the last TRUST digest, or new on this session's first call` and exit 1. `new`: no comparison.
2. Hash the flow's files exactly as spec.md § Design "What is hashed" says, with `S` the folder this file is in; the repo is `git rev-parse --show-toplevel` from the working directory (run with `--no-replace-objects` is not needed here). Skip `__pycache__/` and `*.pyc`. The digest is `<code>.<state>` as spec.md § Design says. Otherwise compare the whole digest with `FLOW_TRUST`: on a difference print `STOP flow files changed since the last step: <paths>` and exit 1 without calling the conductor. Name the paths by comparing with the per-file list in `.feature-flow/state/flow-<feature>.trust` (untrusted, naming only); if it is missing or unreadable, say `(no earlier list to name them)`.
3. Run `[sys.executable, "-I", "-X", "pycache_prefix=" + <a fresh empty temp folder, removed afterwards>, str(S / "flow.py"), feature, command, *args]` with the current environment plus `FLOW_TRUSTED=1`, capturing stdout and stderr. Pass stdin through.
4. Hash again, write the per-file list to `.feature-flow/state/flow-<feature>.trust` (JSON, sorted), print `TRUST <digest>` as the first line, then the conductor's stdout unchanged; write the conductor's stderr to stderr without its final `flow-state` line. Exit with the conductor's exit code.

The `.trust` file must not itself be hashed. Keep the file readable: short functions, a docstring that says it is the trusted check and why it imports nothing from the repo.

Check that the installer ships it: `install.py` copies every file in `scripts/` and the wheel bundle maps `scripts/`, so it should need no change; if it does, change it here. Add `scripts/flow-trust.py` to the installed-file list in `tests/run.sh` (the loop that checks installed files).

Add `tests/py/test_trust_runner.py` (on `helpers.Repo`, running the runner directly with `-I`): a first call with `FLOW_TRUST=new` prints `TRUST <16 hex>` then `OK <token>`; a later call with that digest goes through; each of these between calls makes the next call print `STOP flow files changed since the last step:` naming the path: an edited `feature_flow/conductor.py`, a new `feature_flow/extra.py`, an edited guide, an edited role file under `.claude/agents/`, an edited file under `.claude/skills/feature-flow/`, a line added to `flow-f.state`, and a user's own `guides/notes.md` or `agents/x.md` in the repo root does NOT trip it while a missing or edited `guides/build.md` there does; a planted `feature_flow/__pycache__/conductor.cpython-<ver>.pyc` compiled from an edited `conductor.py` (with the source's mtime and size kept, as `py_compile` with `invalidation_mode=TIMESTAMP` and `os.utime` allow) is not run: the call behaves as the source says; and none of these trips it: a new `__pycache__/x.pyc`, a new `scripts/deploy.sh`, writing the review-reply file `.feature-flow/state/flow-review-f.txt`, the log. Hole (a) from learnings.md (a committed `return` at the top of `check_code`) and hole (b) (`phase=` written into the state after resolving 01) each end in that STOP. Point `CLAUDE_HOME`, `AGENTS_HOME` and `FEATURE_FLOW_HOME` at temp folders in every test, and add one test that an edit under `FEATURE_FLOW_HOME` trips it.

## Not in this ticket

- Changes made during a conductor call, the state-sha check and `--after-build`: ticket 04.
- `HANDOFF` gaining the digest: ticket 05.
- The loader line and the skills: ticket 06.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"` prints `OK` (the cases above, holes a and b included).
- A fresh `python3 install.py <tmp repo>` writes `scripts/flow-trust.py` (checked in `tests/run.sh`).
- `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_trust_runner.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
$ bash tests/run.sh
exit 0
```

## Reference

- spec.md § Design, § Interfaces, § Edge cases
- `feature_flow/codehash.py` (the in-process tripwire, kept), `feature_flow/prompts.py` (`ROLES`), `tests/py/test_tamper.py`

## Answer

**Built**

- `scripts/flow-trust.py` (new): the runner. Stdlib only, imports nothing from the repo. It works out how it was started (`__file__` set: run directly; otherwise `exec` by the loader, with `sys.argv[1]` as its path and `sys.argv[3:]` as its arguments). It accepts and ignores `--after-build <ticket> <sha>`. A missing or empty `FLOW_TRUST` is a STOP. It hashes the files that spec § Design "What is hashed" lists into a `<code>.<state>` digest and compares it with `FLOW_TRUST` (`new` skips the comparison). On a difference it prints the STOP and names the paths from the `.trust` list. Otherwise it runs `flow.py` with `-I -X pycache_prefix=<fresh temp>` and `FLOW_TRUSTED=1`, hashes again, writes `.feature-flow/state/flow-<feature>.trust` (sorted JSON), and prints `TRUST <digest>` followed by the conductor's stdout as is. It passes stderr on without the final `flow-state` line and exits with the conductor's exit code.
- `tests/py/test_trust_runner.py` (new): 26 tests.
- `tests/run.sh`: `scripts/flow-trust.py` added to the installed-file loop.
- `tests/py/test_install.py`: `flow-trust.py` added to the exact list of installed `scripts/` files. The installer copies all of `scripts/`, so this test failed until the list included the new file. `install.py` and `pyproject.toml` (which bundles `scripts/*.py`) needed no change.

**Proof**

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"`: `Ran 26 tests ... OK`, exit 0. Covered: a first call prints TRUST then OK. A later call with that digest gets `BUILD`. A missing or empty `FLOW_TRUST` is a STOP. Each of these trips the next call and is named: edited `feature_flow/conductor.py`, new `feature_flow/extra.py`, edited `.feature-flow/guides/build.md`, edited `.claude/agents/ticket-builder.md`, edited `.claude/skills/feature-flow/SKILL.md`, a line added to `flow-f.state`, an edited or missing root `guides/build.md`, an edit under `FEATURE_FLOW_HOME`. Hole (a), a committed `return` in `check_code`, gives a STOP that names `feature_flow/conductor.py`. Hole (b), `phase=` written into the state after resolving 01, gives a STOP that names the state file. None of these trip it: root `guides/notes.md`, root `agents/x.md`, `__pycache__/x.pyc`, `scripts/deploy.sh`, `flow-review-f.txt`, the log. The planted `.pyc` is real: it is loaded when `flow.py` is run directly, the control test shows `PW <token>`. Through the runner the source runs (`OK <token>`), both on a first call and between calls without a trip. The loader line from spec § Interfaces runs the runner as exec of its bytes. The runner's GUIDES and ROLES names match `prompts`.
- `python3 install.py <tmp repo>` writes `scripts/flow-trust.py`: `bash tests/run.sh` prints `ok    installed scripts/flow-trust.py`.
- `python3 -m unittest discover -s tests/py`: `Ran 307 tests ... OK`, exit 0.
- `bash tests/run.sh`: `465 passed, 0 failed`, exit 0.
- Smoke command: exit 0.

**Decisions**

- STOP lines go to stdout, like the conductor's. Usage errors go to stderr with exit 2.
- If the `.trust` list is readable but names no difference (for example it was rewritten), the STOP says `(the earlier list names none of them)`. If the list is missing, unreadable or not a JSON object, it says `(no earlier list to name them)`.
- Anything under the repo's `.feature-flow/state/` is left out of the code set, even if a home folder overlaps it. So the `.trust` file, the log and the review reply are never hashed. Only `flow-<f>.state` and `.findings` are, as the state part.
- Paths are named under the resolved git top level (or cwd outside git). The home folders are resolved first, so their names are absolute POSIX.
- When `FLOW_TRUST=new` there is no "before" snapshot. Ticket 04 needs one for the during-call check.
- An unreadable file hashes as the marker `unreadable`, so the change still shows.

**Shortcuts taken**

- The pycache temp folder is removed with `shutil.rmtree(..., ignore_errors=True)`. A folder that cannot be removed (Windows file locks) is left in the system temp folder rather than failing a call whose conductor work is already done.
- The GUIDES and ROLES names are copied from `prompts.py`, because the runner may not import it. A test fails if they drift.

**For later tickets**

- 04: `split_report()` already returns the `flow-state` line as its second value (currently `_report`). `snapshot()` returns `(code, state)` maps. Take the "before" snapshot for `new` calls too when the during-call check is added.
- 05: `HANDOFF` lines come through the stdout bytes unchanged. Rewrite them in `main()` before writing stdout.
- 06/07: the runner's direct form is `FLOW_TRUST=new python3 -I scripts/flow-trust.py <feature> <command>`.
