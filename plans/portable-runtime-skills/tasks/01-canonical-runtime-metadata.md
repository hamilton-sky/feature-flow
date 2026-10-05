# Add canonical runtime metadata for every skill

Type: task
Status: open
Blocked by: —
Test first: yes

Before changing anything, run `bash scripts/flow-status.sh in-session-mode --next`. It must exit 10; otherwise leave this ticket open and stop, because the final set of skills and the Claude-only `drive-flow` behavior do not exist yet.

Add one non-executable metadata file beside every canonical `SKILL.md`. Define a minimal, AWK-readable key/value contract for the argument hint, implicit invocation and supported runtimes. Parse it as data; never `source` it. Shared skills declare both `claude` and `codex`. `drive-flow` declares only `claude`. Validate names against their directory and `SKILL.md` frontmatter, reject unknown keys, duplicate keys, empty runtime lists and unknown runtimes, and print the skill and field in every error.

Add reusable installer helpers that read the metadata without changing either current installation path yet. Keep the Codex exclusion introduced by the prerequisite plan working until the Codex renderer consumes the new runtime field.

## Not in this ticket

- Rendering Claude or Codex skill files; the adapter tickets switch those paths.
- Rewriting skill instructions or moving detailed guidance into references.

## Done when

- `bash scripts/flow-status.sh in-session-mode --next >/dev/null; test $? -eq 10` succeeds before the ticket's implementation begins.
- A test loops over every `skills/*/SKILL.md`, finds exactly one adjacent runtime metadata file, and reports no missing or duplicate skill entry.
- Tests prove that common skills include `claude` and `codex`, `drive-flow` includes `claude` but not `codex`, and no unknown runtime is accepted.
- Tests feed malformed, duplicate-key and mismatched-name fixtures to the parser; each exits nonzero and names the bad skill and field.
- `bash tests/run.sh` exits 0 and all existing installer checks still pass.

## Reference

- spec.md § Interfaces, Migration and compatibility
- `install.sh` (`install_codex`, `copy_tree`, `generate`; read before editing)
- `skills/*/SKILL.md`
- `adapters/codex/claude-only.txt` from the completed prerequisite plan
- `tests/run.sh` installer sections

## Answer
