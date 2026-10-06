# Validate changed files before automatic commits

Type: task
Status: open
Blocked by: —
Test first: yes

Harden the Codex loop's `commit_for_agent` path without restricting legitimate ticket scope. It needs nothing from the rest of this plan or from the in-session plan. Before staging, capture the exact tracked paths and the untracked paths that are not ignored (`git ls-files --others --exclude-standard`; a correctly ignored `.env` is never flagged, because `git add -A` skips it anyway), and reject untracked high-risk filenames such as private keys, credential files and real `.env` files while allowing documented examples. Print the status summary before staging. After staging, run `git diff --cached --check`, which also covers new files (a `git diff --check` before staging sees only tracked files), and print the cached name/status summary before committing.

Define the suspicious-name rules in one testable helper shared by the commit path. Provide a narrow, explicit environment override that lists exact repository-relative paths; reject absolute paths, parent traversal, directories and globs in that override. The override changes only the filename check, never the floor guard, gate, clean-tree requirement or ticket resolution requirement.

After staging, verify the index is nonempty and contains the same path set that was approved. On any mismatch or validation failure, leave the files unstaged when safely possible, make no commit and print recovery instructions. Preserve the existing behavior when the agent already committed its work. This covers only the Codex loop: Claude builders commit for themselves inside `next-phase`, and ticket 11 says so in the README.

## Not in this ticket

- A per-ticket file allowlist; tickets may legitimately change arbitrary project files.
- Secret-content scanning or removal of committed secrets; use dedicated security tooling for that.

## Done when

- A normal resolved ticket prints pre-stage and cached summaries and commits exactly the changed path set it approved.
- Untracked `.env`, private-key and credential fixtures are refused before commit and named; `.env.example`, ordinary source files and a `.env` listed in `.gitignore` are allowed.
- Exact-path overrides allow only the named repository-relative file, while absolute paths, `..`, directories and glob characters exit nonzero before staging.
- A whitespace error in a new untracked file fails `git diff --cached --check` and leaves nothing staged, an index path-set mismatch makes no commit, and an agent-created commit still causes the loop to add none.
- `bash tests/run.sh` exits 0 with the tree clean after every commit-safety fixture.

## Reference

- spec.md § Stories, Risks
- `scripts/auto-flow.sh` (`commit_for_agent`, clean-tree checks)
- `scripts/floor-guard.sh` (read only; complementary policy)
- `tests/run.sh` Codex commit fixtures

## Answer
