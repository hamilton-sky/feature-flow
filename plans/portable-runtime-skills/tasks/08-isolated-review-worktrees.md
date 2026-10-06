# Run headless reviews in disposable writable worktrees

Type: task
Status: open
Blocked by: 07
Test first: yes

Change the unattended reviewer path to create a temporary detached Git worktree at the committed state under review, run the reviewer there with `workspace-write`, and remove the worktree afterward. Pass Codex the worktree as its working root and make Claude reviewer commands run from the same directory. This deliberately covers Claude as well as Codex: Claude's reviewer has no sandbox, so today it can write the main tree. The main checkout remains the source of the loop state and review output.

A worktree holds only tracked files. The plan folder may be git ignored (`next-phase` supports that), and the installed skills (`.claude/skills/`, `.agents/skills/`) and roles (`.claude/agents/`, `.agents/flow-roles/`) often are. Copy whichever of them are ignored or untracked into the worktree before the review, so the reviewer finds the ticket, the skill and its role. Resolve the role file before changing directory, because `pick_agent` uses relative paths. The copies are inputs: they are not part of the tracked-diff check.

Use `mktemp -d`, validate the returned path before cleanup, and install a trap that attempts `git worktree remove --force` followed by `git worktree prune`. Never recursively delete an unresolved or broad path. If creation, review setup or cleanup fails, stop and print the exact worktree path plus a manual recovery command. A reviewer may create caches or generated files inside the worktree, but a tracked diff after the review is a failure even when the verdict says PASS.

Do not change the interactive `drive-flow` subagent contract. Its reviewer remains governed by `flow-step.sh`; parity tests only ensure both paths enforce an unchanged builder checkout and the same final verdict meaning.

## Not in this ticket

- Parallel reviews, reuse of worktrees between tickets or worktree support for builders.
- Automatic deletion of arbitrary temporary directories after an unresolved Git error.

## Done when

- A fake reviewer writes an untracked cache file and passes inside the temporary worktree; the main checkout stays clean and `git worktree list --porcelain` has no leftover entry.
- A fake reviewer changes a tracked file and returns PASS; the loop stops, names the changed file and does not accept the verdict.
- Creation and cleanup failure fixtures each stop with the validated path and a `git worktree` recovery command, without running a recursive delete on an unvalidated value.
- With `plans/` listed in `.gitignore` and the installed skills untracked, a fake reviewer in the worktree still reads the ticket and the skill, and passes.
- The fake `codex` in `tests/run.sh` honours `-C` (today it drops it), and a test shows from its log that the reviewer ran in the worktree, not the main checkout.
- Codex reviewers use `workspace-write` with the worktree root, builders keep their current sandbox, and the interactive `flow-step.sh` tests remain unchanged.
- `bash tests/run.sh` exits 0 on Linux and macOS-compatible Git commands.

## Reference

- spec.md § Writable review isolation decision, Risks
- structured review normalization from ticket 07
- `scripts/auto-flow.sh` (`run_agent`, `run_codex`, `review`)
- `scripts/flow-step.sh` and `skills/drive-flow/SKILL.md` (read only)
- `tests/run.sh` review-mutation fixtures

## Answer
