# Render Claude installations from canonical skills

Type: task
Status: open
Blocked by: 01
Test first: yes

Add a Claude adapter that combines each canonical skill with its runtime metadata and emits the Claude installation shape. Switch the default and `--agent claude` installer paths to the adapter while preserving byte-for-byte behavior where the canonical source already has the correct Claude form. The adapter owns Claude-only frontmatter such as the argument hint and model-invocation switch, slash-command examples, `$ARGUMENTS` wording and named-agent review commands.

At this stage the canonical files may still contain legacy Claude metadata and wording. The renderer must tolerate that transition without duplicating fields or text. It must skip skills whose supported runtimes do not include Claude, use the existing `place` behavior, and preserve templates, references and other resources unchanged.

## Not in this ticket

- Removing legacy Claude metadata or wording from canonical files; that happens after both renderers exist.
- Changing Codex output or plugin packaging.

## Done when

- `bash install.sh "$T" --agent claude` in a temporary directory installs every Claude-supported skill, its resources and the two named agents, and exits 0.
- Golden tests prove the rendered `next-phase`, `review-ticket` and `drive-flow` frontmatter, invocation syntax and manual-review command match the current Claude contract without duplicate keys.
- A fixture marked `runtimes=codex` is skipped for Claude with an explicit message and is not counted as added or kept.
- A second install adds nothing, `--dry-run` writes nothing, and an edited destination is kept unless `--force` is supplied.
- `bash tests/run.sh` exits 0 and the existing default-install checks still pass.

## Reference

- spec.md § Design, Migration and compatibility
- `install.sh` (`copy_tree`, `place`, current Claude branch)
- `skills/next-phase/SKILL.md`, `skills/review-ticket/SKILL.md`, `skills/drive-flow/SKILL.md`
- `agents/ticket-builder.md`, `agents/ticket-reviewer.md`
- runtime metadata produced by ticket 01

## Answer
