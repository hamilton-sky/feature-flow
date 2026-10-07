# Remove the dead installed copies and test that the used ones match the source

Type: task
Status: open
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

