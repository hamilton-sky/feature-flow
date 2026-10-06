# Leave Claude Code only skills out of the Codex install

Type: task
Status: open
Blocked by: —
Test first: yes

The `drive-flow` skill (ticket 04, which comes after this one) spawns Claude Code subagents, so a generated Codex copy would tell Codex to use a tool it does not have. This ticket lands first because a new skill marked `disable-model-invocation: true` would otherwise change two existing Codex install checks (the list of explicit only skills and the `--dry-run` count) and ticket 04 could not pass `bash tests/run.sh`. Make `install.sh --agent codex` (and the Codex half of `--agent all`) skip skills listed in a new file `adapters/codex/claude-only.txt`, one skill name per line, and put `drive-flow` in it.

For a skipped skill the installer writes nothing under `.agents/`, prints one line `  skip    drive-flow (Claude Code only)`, and does not count it as added or kept. It must also leave the skipped name out of the skill names it hands to the transform, so no other skill's `/drive-flow` mention turns into a `$drive-flow` that does not exist. The Claude install is unchanged, and `--dry-run` reports the same lines without writing. A name in the list with no skill directory is ignored silently. The skill does not exist yet, so the tests copy the repository into a temp directory, add a stub `skills/drive-flow/SKILL.md` there, and run that copy's `install.sh`.

## Not in this ticket

- The skill itself: ticket 04, which is blocked by this one.
- A Codex same-session mode. It is a later round and needs its own probe.

## Done when

- `grep -x drive-flow adapters/codex/claude-only.txt` prints `drive-flow`.
- In a copy of the repo with a stub `skills/drive-flow/SKILL.md`, `install.sh "$T" --agent codex` (with `T=$(mktemp -d)`) exits 0, prints a line containing `drive-flow` and `Claude Code only`, leaves `$T/.agents/skills/drive-flow` absent, and still installs the other seven skills with an `agents/openai.yaml` each. No installed Codex skill contains `$drive-flow`.
- In the same copy, `--agent all` installs `$T/.claude/skills/drive-flow/SKILL.md` byte for byte (`cmp` prints nothing) and leaves `$T/.agents/skills/drive-flow` absent.
- In the same copy, `--agent codex --dry-run` writes nothing and its `would add` count equals the real install's `added` count.
- In the real repo, which has no `drive-flow` yet, every existing install check passes unchanged.
- `bash tests/run.sh` exits 0 with a check for each bullet, and the existing Codex install checks still pass.

## Reference

- install.sh (the `install_codex` function and the skill name list)
- adapters/codex/skill.awk (read only)
- tests/run.sh (the `install.sh, codex` section)

## Answer

