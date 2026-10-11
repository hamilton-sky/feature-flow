# Measure a ticket's diff: files, changed lines and binary files

Type: task
Floor: allow flow-edit
Status: resolved
Blocked by: —
Test first: yes

Add `diff_size(base, head, exclude)` to `feature_flow/git.py`. It runs `git diff --numstat --no-renames <base> <head> -- . ":(exclude)<exclude>"` through the module's `_git` helper and returns a tuple `(files, lines, binary)`: the number of changed paths, the sum of added plus removed lines over the text files, and `True` when any line of the numstat output has `-` for its counts (a binary file). `exclude` is the plan folder (`plans/<feature>/`, or the `FLOW_DIR` root's feature folder), so the ticket's own Status and Answer and appended map lines never count. `--no-renames` makes the result the same whatever the user's `diff.renames` setting is. A git error raises `RuntimeError` like the module's other helpers.

Add the tests in a new `tests/py/test_diff_size.py`, using a throwaway repo like `tests/py/helpers.py`'s `Repo`: a two-file text change, a change inside the excluded folder only (0 files, 0 lines), a binary file, and a rename with `diff.renames=true` set in the repo config (counted as one delete plus one add).

## Not in this ticket

- Deciding what "small" means or reading `FLOW_SMALL_*`: ticket 04.
- The `Review:` ticket line: ticket 02.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_diff_size.py" -v` prints `OK` and lists a test with `binary` in its name.
- All existing tests still pass: `python3 -m unittest discover -s tests/py` prints `OK`.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_diff_size.py" -v
prints binary
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Interfaces, § Edge cases (binary, renames)
- `feature_flow/git.py` (`_git`, `changes`), `tests/py/helpers.py`

## Answer

Work started at commit `58255b6f8b966c6dd34a78a903e7be419ed0f867`; test-only commit `f318af3`.

**Built**
- `feature_flow/git.py`: new `diff_size(base, head, exclude)` returning `(files, lines, binary)`, via `_git("diff", "--numstat", "--no-renames", base, head, "--", ".", ":(exclude)<exclude>")`.
- `tests/py/test_diff_size.py`: new, 5 tests in a throwaway `helpers.Repo(local=False)`.

**Proof**
- `python3 -m unittest discover -s tests/py -p "test_diff_size.py" -v`: `Ran 5 tests ... OK`, lists `test_a_binary_file_is_flagged ... ok`, plus the two-file change (2, 4, False), the excluded-folder-only change (0, 0, False), the rename with `diff.renames=true` (2, 20, False) and a bad revision raising `RuntimeError`. Before the code it failed with `AttributeError: module 'feature_flow.git' has no attribute 'diff_size'` (5 errors).
- `python3 -m unittest discover -s tests/py`: `Ran 384 tests in 217.136s`, `OK`. Also `bash tests/run.sh`: `465 passed, 0 failed`.

**Decisions**
- A binary file counts as a changed path but adds no lines (its counts are `-`); `binary` is then `True`.
- `_git` runs in the current directory, so callers must be inside the repo (the conductor already is); the test chdirs into the throwaway repo like `test_floorguard.py`.
- Added a `RuntimeError` test for a bad revision, since the ticket names that behaviour.

**Shortcuts taken**
- none

**For later tickets**
- 04: pass `exclude` as the plan folder relative to the repo top with a trailing slash (e.g. `plans/<feature>/`); the pathspec `.` is relative to the cwd, so call it from the repo top level.
