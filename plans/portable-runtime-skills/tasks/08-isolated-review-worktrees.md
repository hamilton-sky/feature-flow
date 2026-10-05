# Run headless reviews in disposable writable worktrees

Type: task
Status: open
Blocked by: 07
Test first: yes

Change the unattended reviewer path to create a temporary detached Git worktree at the committed state under review, run the reviewer there with `workspace-write`, and remove the worktree afterward. Pass Codex the worktree as its working root and make Claude reviewer commands run from the same directory. The main checkout remains the source of the loop state and review output.

Use `mktemp -d`, validate the returned path before cleanup, and install a trap that attempts `git worktree remove --force` followed by `git worktree prune`. Never recursively delete an unresolved or broad path. If creation, review setup or cleanup fails, stop and print the exact worktree path plus a manual recovery command. A reviewer may create caches or generated files inside the worktree, but a tracked diff after the review is a failure even when the verdict says PASS.

Do not change the interactive `drive-flow` subagent contract. Its reviewer remains governed by `flow-step.sh`; parity tests only ensure both paths enforce an unchanged builder checkout and the same final verdict meaning.

## Not in this ticket

- Parallel reviews, reuse of worktrees between tickets or worktree support for builders.
- Automatic deletion of arbitrary temporary directories after an unresolved Git error.

## Done when

- A fake reviewer writes an untracked cache file and passes inside the temporary worktree; the main checkout stays clean and `git worktree list --porcelain` has no leftover entry.
- A fake reviewer changes a tracked file and returns PASS; the loop stops, names the changed file and does not accept the verdict.
- Creation and cleanup failure fixtures each stop with the validated path and a `git worktree` recovery command, without running a recursive delete on an unvalidated value.
- Codex reviewers use `workspace-write` with the worktree root, builders keep their current sandbox, and the interactive `flow-step.sh` tests remain unchanged.
- `bash tests/run.sh` exits 0 on Linux and macOS-compatible Git commands.

## Reference

- spec.md § Writable review isolation decision, Risks
- structured review normalization from ticket 07
- `scripts/auto-flow.sh` (`run_agent`, `run_codex`, `review`)
- `scripts/flow-step.sh` and `skills/drive-flow/SKILL.md` (read only)
- `tests/run.sh` review-mutation fixtures

## Answer
