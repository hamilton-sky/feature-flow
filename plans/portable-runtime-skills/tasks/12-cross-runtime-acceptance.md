# Prove cross-runtime installation, safety and packaging

Type: task
Status: open
Blocked by: 08, 09, 11
Test first: no

Run the map's bar from a clean checkout and add only the acceptance wiring needed to exercise the complete offline workflow. Build fresh Claude and Codex installations, validate the portable plugin, run a fake Codex feature through preflight, build, safe commit, isolated writable review and structured verdict normalization, and confirm the completed interactive conductor's text review fixtures still pass.

The acceptance must prove runtime boundaries: common skills render for both agents, `drive-flow` renders only for Claude, the plugin contains only Codex-supported skills, and shared resources come from the same canonical files. It must also prove failure safety by running one missing-capability case, one malformed structured review, one reviewer tracked edit and one suspicious untracked file, with no unintended commit and no leftover worktree.

Keep real-agent activation evaluation optional. If credentials and the explicit enable switch are present, document how to run it separately; the acceptance bar remains deterministic and offline.

## Not in this ticket

- Fixing failures by weakening checks, changing approved commands or excluding supported platforms.
- Publishing the plugin or running paid model sessions as part of the required bar.

## Done when

- `bash tests/run.sh` exits 0, its final summary reports no failed checks, and it includes cross-runtime acceptance checks for installation, runtime exclusion, preflight, commit safety, review isolation and verdict normalization.
- `bash scripts/package-plugin.sh --check` exits 0, reports every supported skill and the Claude-only omission, and leaves `git status --porcelain` empty.
- Acceptance fixtures leave no extra `git worktree list --porcelain` entry, no staged file and no commit after each forced failure.
- A fresh default Claude install, Codex install and `--agent all` install each succeed twice idempotently and preserve an edited destination unless `--force` is given.
- `bash scripts/flow-status.sh portable-runtime-skills --check` prints `OK`, and the Answer records the commands and their fresh output without invoking a real model.

## Reference

- map.md § Destination, The bar
- all resolved ticket Answers and `learnings.md`
- `tests/run.sh`, `tests/smoke-real.sh`
- `scripts/package-plugin.sh`
- completed `scripts/flow-step.sh` and `scripts/auto-flow.sh`

## Answer
