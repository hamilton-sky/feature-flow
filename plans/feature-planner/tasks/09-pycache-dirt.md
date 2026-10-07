# Keep Python's __pycache__ from stopping the build

Type: task
Status: open
Blocked by: —
Test first: yes

The acceptance run showed that the planner and the plan reviewer (and later the gate's Test and Smoke runs) leave untracked `__pycache__/` folders in a Python repo that has no `.gitignore` for them. `next` counts every untracked file as a change (`git.changes()`, `git status --porcelain -uall`), so the build stops on "working tree is not clean" for files the flow itself made.

Two ways, pick one and say why in the Answer: (a) `git.changes()` skips untracked `__pycache__/` folders and `*.pyc` files, as it already skips the install; or (b) the guides tell every agent to run Python with `PYTHONDONTWRITEBYTECODE=1`. (a) also covers the gate's own runs; (b) does not.

## Not in this ticket

- Adding a `.gitignore` to the user's repo: the flow never edits it on its own.

## Done when

- `python3 -m unittest discover -s tests/py` runs a new test: with an untracked `pkg/__pycache__/m.cpython-312.pyc` and nothing else changed, `next` does not STOP on a dirty tree.
- Any other untracked file still makes `next` STOP with "working tree is not clean".
- All existing tests still pass.

## Reference

- feature_flow/git.py (`changes`), feature_flow/conductor.py (`next`)

## Answer
