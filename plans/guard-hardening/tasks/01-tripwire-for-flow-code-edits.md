# Stop the conductor judging a build with code the builder changed

Type: task
Status: open
Blocked by: —
Test first: yes
Floor: allow flow-edit, skip, suppress

First write `tests/py/test_tamper.py`, which builds a throwaway repo, drives the conductor with `flow.py` (`start`, `next`), plays the builder by editing the code the conductor loads, resolves the ticket and commits, and calls `next` again. Three layouts, each its own test: a source checkout (`feature_flow/` beside `scripts/`, like `helpers.Repo`), a committed install (`install.py` run into the repo and committed) and a `--private` install (same, excluded from git, so the edit is untracked). In each, edit `feature_flow/floorguard.py` (or `.feature-flow/feature_flow/floorguard.py`) and also `scripts/flow.py`. Expected: `next` prints `STOP flow code changed while building <ticket>` naming the changed files. A fourth test: the same edit with `Floor: allow flow-edit` on the ticket (committed before the base) reaches `REVIEW`. Fifth: an edit made before `start` never stops. Run them first against the current code: the three STOP tests must fail.

Then build it in `feature_flow/conductor.py` (and a small helper, `feature_flow/codehash.py` or inside `git.py`). `pick_ticket` records `code_sha` in the run state next to `base`: one sha256 over the sorted relative path and bytes of every `*.py` in the directory of the imported `feature_flow` package (skip `__pycache__`), every `*.py` in `self.scripts`, and the files `prompts.find_file` returns for the `build` and `review` role and guide. A function `flow_code()` returns the hash and the list of file hashes so a STOP can name the changed files (store the per-file hashes in the state as one line or recompute names by comparing against a second state key). At the top of `judge_build` and in `judge_review` compare; on a difference raise `Stop` with the message above. In `judge_build` read the ticket's `Floor:` line as it was at `base` (`git show <base>:<ticket>`, reusing `floorguard.allow_line`) and when `flow-edit` is allowed, refresh the snapshot and go on. `judge_review` has no allowance.

## Not in this ticket

- A `flow-edit` category inside `floorguard.py`: the snapshot covers it (spec.md § Decisions).
- README, `guides/build.md`: ticket 09 documents the check, `Floor: allow flow-edit` and that it is a tripwire.
- Sandboxing: a builder that edits the conductor can edit the check too.

## Done when

- `python3 -m unittest discover -s tests/py -k tamper` passes; with the conductor change stashed, the three STOP tests fail and the allow and before-start tests pass.
- `next` on an untouched repo behaves exactly as before: all existing tests still pass.
- The STOP names each changed file relative to the repo, and the line still starts with `STOP `.

## Reference

- spec.md § Design (Goal 1), § Decisions
- feature_flow/conductor.py (`pick_ticket`, `judge_build`, `judge_review`), feature_flow/prompts.py (`find_file`), feature_flow/install.py (`--private`), tests/py/helpers.py, tests/py/test_install.py

## Answer

