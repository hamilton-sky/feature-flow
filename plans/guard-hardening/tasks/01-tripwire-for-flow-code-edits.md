# Stop the conductor judging a build with code the builder changed

Type: task
Status: resolved
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


**Built**: `feature_flow/codehash.py` (new: `flow_code(scripts)` returns the overall sha256 and a `{repo-relative path: sha256}` map; `changed`, `dump`, `load`), `feature_flow/conductor.py` (`snapshot_code`, `check_code`, `flow_edit_allowed`; `pick_ticket` records `code_sha` and `code_files` next to `base`; `judge_build` and `judge_review` check first), `tests/py/test_tamper.py` (five tests: source checkout, committed install, `--private` install, `Floor: allow flow-edit`, edit before start).

**Proof**:
- `python3 -m unittest discover -s tests/py -k tamper`: Ran 5, OK. With `feature_flow/conductor.py` stashed: Ran 5, FAILED (failures=3), exactly SourceCheckout, CommittedInstall, PrivateInstall; the allow and before-start tests passed.
- `python3 -m unittest discover -s tests/py`: Ran 139, OK. `bash tests/run.sh`: 441 passed, 0 failed, exit 0.
- The tamper tests assert the line starts with `STOP flow code changed while building ` and contains `feature_flow/floorguard.py` and `scripts/flow.py` (with the `.feature-flow/` prefix for installs); they pass.

**Decisions**: file keys are paths relative to the repo top (absolute if outside it), so the STOP names repo-relative files. Per-file hashes live in the state key `code_files` as one JSON line. Role and guide files that cannot be found are skipped (the test fixtures have none; `prompt` already stops on that). The STOP text follows the spec: `... <files>. if intended, the ticket needs a line: Floor: allow flow-edit`. `judge_review` has no allowance.

**Shortcuts taken**: `flow_edit_allowed` runs `git show` on every `judge_build` even when nothing changed; cheap, but could be made lazy. A damaged `code_files` value gives an empty name list in the STOP. A state file from before this change has no `code_sha`, so the first `next` after upgrading mid-ticket stops with all files named; `reset` clears it.

**For later tickets**: tickets 02 to 10 edit `feature_flow/` and run under the pinned 0.1.6 conductor, which has no tripwire, so they are unaffected until it is replaced. Ticket 05 (floorguard and gate in plain Python) changes files the snapshot covers, so it needs `Floor: allow flow-edit` once this code is the conductor in use. Ticket 09 documents the check.
