# Add canonical runtime metadata for every skill

Type: task
Status: open
Blocked by: —
Test first: yes

Before changing anything, check the prerequisite: `grep -l '^Status: resolved' plans/in-session-mode/tasks/0[45]-*.md | wc -l` must print `2`, meaning the in-session plan's `drive-flow` skill and its Codex exclusion are resolved. Otherwise leave this ticket open and stop, because the Claude-only `drive-flow` skill and its exclusion do not exist yet. The rest of the in-session plan (its README and its paid run) is not needed.

Add one non-executable metadata file beside every canonical `SKILL.md`. Define a minimal, AWK-readable key/value contract for the argument hint, implicit invocation and supported runtimes. Parse it as data; never `source` it. Shared skills declare both `claude` and `codex`. `drive-flow` declares only `claude`. Validate names against their directory and `SKILL.md` frontmatter, reject unknown keys, duplicate keys, empty runtime lists and unknown runtimes, and print the skill and field in every error.

Add reusable installer helpers that read the metadata without changing either current installation path yet. Keep the Codex exclusion introduced by the prerequisite plan working until the Codex renderer consumes the new runtime field.

## Not in this ticket

- Rendering Claude or Codex skill files; the adapter tickets switch those paths.
- Rewriting skill instructions or moving detailed guidance into references.

## Done when

- `grep -l '^Status: resolved' plans/in-session-mode/tasks/0[45]-*.md | wc -l` prints `2`.
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
