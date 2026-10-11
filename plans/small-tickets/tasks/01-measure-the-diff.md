# Measure a ticket's diff: files, changed lines and binary files

Type: task
Floor: allow flow-edit
Status: open
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
