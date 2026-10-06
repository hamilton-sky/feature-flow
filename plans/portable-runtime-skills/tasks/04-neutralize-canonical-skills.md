# Make canonical skill instructions provider-neutral

Type: task
Status: open
Blocked by: 02, 03
Test first: yes

Convert common canonical `SKILL.md` files to the portable core: frontmatter contains only `name` and `description`, and the body describes arguments, repository instructions and other skills without Claude- or Codex-specific invocation syntax. Put runtime-only commands and wording in explicit Claude or Codex fragments consumed by the renderers.

Keep genuinely runtime-specific instructions in skills whose metadata declares only that runtime. `drive-flow` remains Claude-specific rather than pretending to be portable. Update descriptions only when needed to keep activation precise. Templates and resources used as deliverables remain shared and unchanged unless their text is itself runtime-specific.

First record the official skill layout guidance for both runtimes in `references.md` (its "Skill layout guidance" entry), with links and the date read, and follow it. The Codex adapter's sentence-replacement rules stay in place as a fallback; ticket 14 deletes them.

## Not in this ticket

- Changing what any workflow does, its ticket protocol, review policy or acceptance bar.
- Moving long checklists into `references/` files: ticket 13.
- Deleting the sentence-replacement rules from `adapters/codex/skill.awk`: ticket 14.
- Plugin packaging and model-backed activation evaluation.

## Done when

- The "Skill layout guidance" entry of `references.md` has no `<` placeholder line left and names at least one link.
- A test parses every canonical `SKILL.md` and reports that common skills have only `name` and `description` frontmatter while runtime-specific exceptions match their metadata.
- Searches over common canonical instructions find no `$ARGUMENTS`, slash skill invocation, dollar skill invocation, `.claude/`, `.agents/`, `CLAUDE.md`, `AGENTS.md`, `claude -p` or `codex exec`; renderer fragments contain every required runtime-specific form.
- The generated Claude and Codex golden files retain the required invocation, project-instruction, role and sandbox wording for their environments.
- `bash tests/run.sh` exits 0 and both installation trees remain behaviorally equivalent to their pre-conversion golden fixtures.

## Reference

- spec.md § Canonical content decision, Interfaces
- Claude renderer from ticket 02
- Codex renderer from ticket 03
- `skills/*/SKILL.md`, `skills/plan-feature/templates/`
- `references.md`, the "Skill layout guidance" entry, which this ticket fills in

## Answer
