# Make `uninstall --user` remove the home conductor too

Type: task
Status: resolved
Blocked by: 01
Test first: yes

In `feature_flow/uninstall.py`, `uninstall_user()` walks the `~/.claude` and `~/.agents` roots and their `feature-flow.sha256` records. Add the third root: `$FEATURE_FLOW_HOME` or `$HOME/.feature-flow` (share the lookup with the installer from ticket 01, one function, not a copy). Reuse `remove_install` unchanged for the removal rules (only files still holding their recorded or a released hash; edited files kept and named; `--force`; `--dry-run`).

Two gaps to close for the home root: `_prune` only drops `__pycache__` under folders starting with `.feature-flow/`, but here the folders are `feature_flow/` and `scripts/` relative to the root, so give `_prune` a way to treat the home root's folders as owned (python may have written bytecode there). And when nothing was kept, remove the now empty home folder itself, so the bar's "home folder without feature-flow files" holds. Update `USAGE` and the "no personal feature-flow install found in ..." message to name the third folder.

## Not in this ticket

- Repo uninstall (`feature-flow uninstall <repo>`) is unchanged.
- Writing the home install: ticket 01.

## Done when

- After `install --user --agent all` then `uninstall --user`, every file under the temp home is gone, including `~/.feature-flow` itself, and the output ends `removed N, kept 0`.
- A home file edited after the install is kept and named, the folder stays, and `--force` then removes it.
- `uninstall --user --dry-run` changes nothing and prints `would remove`.
- Bytecode python left in `~/.feature-flow/feature_flow/__pycache__` does not stop the removal.
- `python3 -m unittest discover -s tests/py -p "test_uninstall.py"` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_uninstall.py"
prints OK
```

## Reference

- `feature_flow/uninstall.py`: `uninstall_user`, `remove_install`, `_prune`
- `tests/py/test_uninstall.py`: `test_user_removes_the_home_install_and_leaves_the_repo`

## Answer


**Built**: `feature_flow/install.py` (new `flow_home()`, the one lookup of `$FEATURE_FLOW_HOME` or `$HOME/.feature-flow`, used by `Installer` and the uninstaller), `feature_flow/uninstall.py` (third root in `uninstall_user`; `owned` flag on `_prune` and `remove_install`; empty home folder removed when nothing was kept; `USAGE` and the "no personal install" message name the third folder), `tests/py/test_uninstall.py` (FEATURE_FLOW_HOME moved back under the temp home, plus tests for edited/force, dry run, bytecode, `removed N, kept 0`). Test-only commit 075f682.

**Proof**:
- `python3 -m unittest discover -s tests/py -p "test_uninstall.py"`: Ran 20 tests, OK (before the code: 3 failures). That covers: temp home empty, `.feature-flow` gone, last line `removed N, kept 0`; edited home file kept and named, then `--force` removes all; `--dry-run` prints `would remove` and changes nothing; bytecode in `~/.feature-flow/feature_flow/__pycache__` does not block removal.
- `python3 -m unittest discover -s tests/py`: Ran 254 tests, OK.
- `bash tests/run.sh`: 457 passed, 0 failed.

**Decisions**: the home root is passed `owned=True` so `_prune` drops `__pycache__` in every folder below it; also the root's own `__pycache__` is dropped before the root is removed. The root is removed with `os.rmdir`, so any user file left in it keeps the folder.

**Shortcuts taken**: none.

**For later tickets**: `remove_install` and `_prune` take an optional `owned` argument (default False, repo behaviour unchanged).
