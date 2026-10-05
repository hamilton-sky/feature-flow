# Render Codex installations from canonical skills

Type: task
Status: open
Blocked by: 01
Test first: yes

Refactor the Codex installation path to consume the canonical runtime metadata. The renderer emits a valid `SKILL.md`, `agents/openai.yaml` and any runtime fragment for every skill that supports Codex. It emits role files under `.agents/flow-roles/`, keeps resources unchanged, and explicitly reports every unsupported skill it skips.

Use the runtime-support declaration as the source of truth and remove the separate Claude-only skip list once tests prove the same behavior. Preserve dollar mentions, argument wording, `AGENTS.md`, `FLOW_AGENT=codex`, explicit-invocation policy and read-only manual review commands. Keep the legacy sentence converter available only as a transitional fallback until the canonical content is neutralized.

## Not in this ticket

- Removing every legacy prose replacement from the adapter; the canonical conversion does that after both renderers exist.
- Installing Claude skills or building the portable plugin.

## Done when

- `bash install.sh "$T" --agent codex` installs every Codex-supported skill with valid `SKILL.md` and `agents/openai.yaml`, reports `drive-flow` as unsupported, and writes no `.agents/skills/drive-flow` directory.
- `bash install.sh "$T" --agent all` installs `drive-flow` only for Claude and installs common skills for both environments.
- Strict YAML parsing accepts every rendered skill header and `agents/openai.yaml`; explicit-only policy matches the canonical metadata.
- Tests prove `--user`, `--dry-run`, second install, kept edits and `--force` retain their existing behavior.
- `bash tests/run.sh` exits 0, and no installed Codex skill contains Claude-only paths, slash invocations or frontmatter keys.

## Reference

- spec.md § Design, Migration and compatibility
- `install.sh` (`install_codex`, `generate`, `place`)
- `adapters/codex/skill.awk`
- runtime metadata produced by ticket 01
- `tests/run.sh` Codex adapter and installer sections

## Answer
