# Leave Claude Code only skills out of the Codex install

Type: task
Status: open
Blocked by: 04
Test first: yes

The `drive-flow` skill spawns Claude Code subagents, so a generated Codex copy would tell Codex to use a tool it does not have. Make `install.sh --agent codex` (and the Codex half of `--agent all`) skip skills listed in a new file `adapters/codex/claude-only.txt`, one skill name per line, and put `drive-flow` in it.

For a skipped skill the installer writes nothing under `.agents/`, prints one line `  skip    drive-flow (Claude Code only)`, and does not count it as added or kept. It must also leave the skipped name out of the skill names it hands to the transform, so no other skill's `/drive-flow` mention turns into a `$drive-flow` that does not exist. The Claude install is unchanged, and `--dry-run` reports the same lines without writing.

## Not in this ticket

- The skill itself: ticket 04.
- A Codex same-session mode. It is a later round and needs its own probe.

## Done when

- `bash install.sh "$T" --agent codex` (with `T=$(mktemp -d)`) exits 0, prints a line containing `drive-flow` and `Claude Code only`, leaves `$T/.agents/skills/drive-flow` absent, and still installs the other seven skills with an `agents/openai.yaml` each.
- `bash install.sh "$T" --agent all` installs `$T/.claude/skills/drive-flow/SKILL.md` and leaves `$T/.agents/skills/drive-flow` absent.
- The default install is unchanged: `cmp skills/drive-flow/SKILL.md "$T/.claude/skills/drive-flow/SKILL.md"` prints nothing.
- `bash install.sh "$(mktemp -d)" --agent codex --dry-run` writes nothing and its `would add` count equals the real install's `added` count.
- `bash tests/run.sh` exits 0 with a check for each bullet, and the existing Codex install checks still pass.

## Reference

- install.sh (the `install_codex` function and the skill name list)
- adapters/codex/skill.awk (read only)
- tests/run.sh (the `install.sh, codex` section)

## Answer

