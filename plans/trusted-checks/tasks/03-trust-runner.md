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
- `tests/py/test_trust_runner.py` (new): 41 tests (26 in the first build, 14 added for the round 1 review fixes; round 2 swapped the 3 real-link tests and the SIGKILL test for 5 in-process tests that run on every platform).
- `tests/run.sh`: `scripts/flow-trust.py` added to the installed-file loop.
- `tests/py/test_install.py`: `flow-trust.py` added to the exact list of installed `scripts/` files. The installer copies all of `scripts/`, so this test failed until the list included the new file. `install.py` and `pyproject.toml` (which bundles `scripts/*.py`) needed no change.

**Proof**

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"`: `Ran 41 tests ... OK`, exit 0 (round 3 rerun). No test in the file skips. Covered: a first call prints TRUST then OK. A later call with that digest gets `BUILD`. A missing or empty `FLOW_TRUST` is a STOP. Each of these trips the next call and is named: edited `feature_flow/conductor.py`, new `feature_flow/extra.py`, edited `.feature-flow/guides/build.md`, edited `.claude/agents/ticket-builder.md`, edited `.claude/skills/feature-flow/SKILL.md`, a line added to `flow-f.state`, an edited or missing root `guides/build.md`, an edit under `FEATURE_FLOW_HOME`. Hole (a), a committed `return` in `check_code`, gives a STOP that names `feature_flow/conductor.py`. Hole (b), `phase=` written into the state after resolving 01, gives a STOP that names the state file. None of these trip it: root `guides/notes.md`, root `agents/x.md`, `__pycache__/x.pyc`, `scripts/deploy.sh`, `flow-review-f.txt`, the log. The planted `.pyc` is real: it is loaded when `flow.py` is run directly, the control test shows `PW <token>`. Through the runner the source runs (`OK <token>`), both on a first call and between calls without a trip. The loader line from spec § Interfaces runs the runner as exec of its bytes. The runner's GUIDES and ROLES names match `prompts`.
- `python3 install.py <tmp repo>` writes `scripts/flow-trust.py`: `bash tests/run.sh` prints `ok    installed scripts/flow-trust.py`.
- `python3 -m unittest discover -s tests/py`: `Ran 322 tests ... OK`, exit 0 (round 3 rerun).
- `bash tests/run.sh`: `465 passed, 0 failed`, exit 0 (round 3 rerun, `ok    installed scripts/flow-trust.py`).
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

**Review fixes** (round 1, quality review)

1. CRLF in `PlantedBytecode.plant`: reproduced off Windows. With conductor.py rewritten to CRLF, `read_text` gives 25452 bytes and `st_size` gives 25998, the same numbers as the CI job. `plant()` now works on bytes (`read_bytes`, byte-string replace, `write_bytes`). New `PlantedBytecodeCrlf` reruns all three plant tests after converting the test repo's copy of conductor.py to CRLF before the layout commit. All three pass: the plant still loads when `flow.py` is run directly, and the runner still runs the source.
2. Linked folders: `tree()` is now a small recursive walk that follows linked folders, because Python imports through them. It also returns the linked folder itself, and `hash_files` hashes that entry as sha256 of `link <real path>`, so adding a link changes the digest even when it loops. A link that points back to a folder on its own path is listed but not entered again. Tests: adding a linked folder into `feature_flow/` trips and names `feature_flow/linked`. An edit inside a committed linked folder trips and names `feature_flow/linked/evil.py`. A looping link `feature_flow/loop -> feature_flow` finishes, trips, and names it. (Round 2 moved these checks in process, see below.)
3. `home()` now falls back to `os.environ.get("HOME", "") + "/" + name`, as install.py does. Tests: with HOME unset the default is `/.agents`, the installer's value. The runner previously gave `/root/.agents` here. With `AGENTS_HOME` unset, an edit under `$HOME/.agents/skills/feature-flow/` trips.
4. A negative return code (killed by a signal) now prints `STOP the conductor was killed by signal N` after the conductor's output and exits 1. TRUST is still printed first, because the call happened and the list was written. Before the fix, the test showed exit 247. (Round 2 moved this check in process, see below.)
5. Trip tests added for `.agents/skills/feature-flow/`, `.agents/flow-roles/`, `.feature-flow/agents/`, `$CLAUDE_HOME/skills/feature-flow/` and `$AGENTS_HOME/skills/feature-flow/`. Each STOPs and names its path.

**Review fixes** (round 2, floor guard)

1. and 2. The two skips are gone: `self.skipTest` in the link helper and `@unittest.skipUnless(hasattr(signal, "SIGKILL"))`. A real folder link or SIGKILL cannot be made on every platform without a skip, so I removed those four end-to-end tests (three link tests, one SIGKILL test). In their place are in-process tests that run the same way everywhere and have no platform branch. A new `load_runner()` loads `scripts/flow-trust.py` with importlib under the name `flow_trust`, so its `__main__` guard does not run `main()`. Loading it outside `-I` deletes `sys.path[0]`, so `load_runner()` saves `sys.path` and puts it back. The two existing in-process loads now use it too.
   - `KilledInProcess` runs `main()` with `started`, `toplevel` and `run_conductor` patched. `run_conductor` returns a fake result with returncode -9. The test checks exit 1, TRUST first, the conductor's stdout, `STOP the conductor was killed by signal 9` last, and stderr without the `flow-state` line. A second test checks that returncode 3 is passed through.
   - `LinkedFolders` runs `tree()` and `hash_files()` on a fake file system. `os.listdir`, `os.path.realpath` and `Path.is_symlink/is_dir/is_file/read_bytes` are patched, so no real link is needed. The tests check four things. A linked folder is listed and followed (`feature_flow/linked`, `feature_flow/linked/evil.py`). The link hashes as sha256 of `link <real path>`. Adding a link changes the code part. A looping link `feature_flow/loop -> feature_flow` is listed but not entered again. `__pycache__` is skipped in both cases.
   - The runner did not change. To prove the tests can fail, I broke it for one run (no negative-code branch, no link listing, no loop check): three of the five new tests failed. Then I restored it with `git checkout` and confirmed it was unchanged.

## Review findings (round 1, quality review)

QUALITY
1. blocker tests/py/test_trust_runner.py (found by CI, "windows with python" job on 7ab6752): `PlantedBytecode.plant` reads conductor.py with read_text and writes it back with write_text. On a Windows checkout the file has CRLF line endings: read_text turns them into LF, so `len(edited.encode("utf-8"))` is 25452 while `stat.st_size` is 25998, and all three PlantedBytecode tests fail with `AssertionError: 25452 != 25998`. write_text would also write CRLF back. Fix: work on bytes (read_bytes, replace the byte strings, write_bytes) so the size and the bytes stay exactly as on disk on every platform.
2. minor scripts/flow-trust.py: `tree()` uses `os.walk` without following links, so a symlinked subfolder inside `feature_flow/` or a skill folder is never hashed, but Python still imports through it. Either follow links (followlinks=True, with loop protection) or record a linked folder as a hashed entry so adding one trips the check.
3. minor scripts/flow-trust.py: `home()` falls back to `Path.home()`, which can raise RuntimeError when HOME is unset; install.py uses `os.environ.get("HOME", "")`. Use the same fallback or print a STOP.
4. minor scripts/flow-trust.py: a conductor killed by a signal gives a negative returncode and an odd exit code. Map a negative code to 1 with a STOP line.
5. minor tests/py/test_trust_runner.py: no trip case for `.agents/skills/feature-flow/`, `.agents/flow-roles/`, `$CLAUDE_HOME`/`$AGENTS_HOME` skill edits, or `.feature-flow/agents/`. Add one each.
REVIEW: FAIL

## Review findings (round 2, floor guard)

floor guard: the diff weakens the bar instead of meeting it
skip: tests/py/test_trust_runner.py: self.skipTest("cannot make a folder link here: %s" % error)
skip: tests/py/test_trust_runner.py: @unittest.skipUnless(hasattr(signal, "SIGKILL"), "no SIGKILL on this platform")
if a finding is intended, the ticket needs a line like: Floor: allow <category>
