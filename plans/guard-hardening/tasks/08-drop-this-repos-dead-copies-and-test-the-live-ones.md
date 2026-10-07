# Remove the dead installed copies and test that the used ones match the source

Type: task
Status: resolved
Blocked by: 06
Test first: yes
Floor: allow test-delete

Only build this after PR #34 is merged and this branch has merged main. In this repo `scripts/flow.py` and `prompts.find_file` look beside `scripts/` first, so `.feature-flow/feature_flow/`, `.feature-flow/guides/` and `.feature-flow/agents/` (tracked, 0.1.4) are never used: delete them with `git rm`. Then refresh `.claude/` and `.agents/` from the source by running `python3 install.py . --agent all --force` and committing only the files under `.claude/` and `.agents/` (not `.feature-flow/`: afterwards remove everything the installer wrote there, `guides/`, `agents/`, `feature_flow/`, `installed.txt`, `installed.sha256`, but never `.feature-flow/state/`, which holds the running conductor's state; `git status --porcelain` must be clean after the commit). Add `tests/py/test_own_install.py`: install into a temp dir with `--agent all` and require that every file the installer wrote under `.claude/` and `.agents/` exists in this repo with the same bytes, and that nothing tracked under `.feature-flow/` is a copy of `feature_flow/`, `guides/` or `agents/`.

## Not in this ticket

- Changing what the installer writes.
- A CI step beyond the unit test: the unit test already runs in CI.

## Done when

- `python3 -m unittest discover -s tests/py -k own_install` passes, and fails if `.claude/skills/feature-flow/SKILL.md` is edited by one byte.
- `git ls-files .feature-flow` prints nothing (or only files that are not copies of the source).
- `python3 scripts/flow.py x next` still runs in this repo (prints `STOP no plan folder` or similar, not an ImportError).
- All existing tests still pass.

## Reference

- spec.md § Design (Goal 5)
- feature_flow/install.py, feature_flow/prompts.py (`find_file`), scripts/flow.py, tests/py/test_install.py

## Answer


**Built**: `git rm` of the tracked `.feature-flow/feature_flow/`, `.feature-flow/guides/`, `.feature-flow/agents/` (0.1.4 copies, 0 tracked files left under `.feature-flow`); `.claude/skills/feature-flow/SKILL.md` and `.agents/skills/feature-flow/SKILL.md` refreshed by `python3 install.py . --agent all --force`; new `tests/py/test_own_install.py`. Everything the installer wrote under `.feature-flow/` was removed again (state/ untouched).

**Proof**:
- `python3 -m unittest discover -s tests/py -k own_install`: 2 tests OK. Before the work both failed (stale SKILL.md, tracked copies). After appending a line to `.claude/skills/feature-flow/SKILL.md` it failed (1 failure); after removing it, OK.
- `git ls-files .feature-flow | wc -l` printed 0.
- `python3 scripts/flow.py x next` printed `STOP no plan folder plans/x` (no ImportError).
- `python3 -m unittest discover -s tests/py`: 168 tests OK; `bash tests/run.sh`: 441 passed, 0 failed.

**Decisions**: the test shells out to `install.py` in a temp dir (a real install, as users run it) and checks the second part with `git ls-files`, failing on any tracked path under the three copy folders. Only the two SKILL.md files differed, so only they are in the diff.

**Shortcuts taken**: none. The second test needs git and a checkout with a `.git`; it errors in a source tarball.

**For later tickets**: after running `install.py .` here, delete `.feature-flow/{agents,guides,feature_flow,installed.txt,installed.sha256}` by hand (not `state/`) or the tree is dirty.
