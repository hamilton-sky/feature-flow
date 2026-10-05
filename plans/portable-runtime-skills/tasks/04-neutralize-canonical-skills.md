# Make canonical skill instructions provider-neutral

Type: task
Status: open
Blocked by: 02, 03
Test first: yes

Convert common canonical `SKILL.md` files to the portable core: frontmatter contains only `name` and `description`, and the body describes arguments, repository instructions and other skills without Claude- or Codex-specific invocation syntax. Put runtime-only commands and wording in explicit Claude or Codex fragments consumed by the renderers.

Keep genuinely runtime-specific instructions in skills whose metadata declares only that runtime. `drive-flow` remains Claude-specific rather than pretending to be portable. Move long checklists, rubrics and examples from `automation-design`, `architect-review` and other large skills into adjacent `references/` files when the main instructions can link to them without changing behavior. Update descriptions only when needed to keep activation precise.

Delete the Codex adapter's exact sentence-replacement rules after golden tests demonstrate that explicit fragments cover every difference. Templates and resources used as deliverables remain shared and unchanged unless their text is itself runtime-specific.

## Not in this ticket

- Changing what any workflow does, its ticket protocol, review policy or acceptance bar.
- Plugin packaging and model-backed activation evaluation.

## Done when

- A test parses every canonical `SKILL.md` and reports that common skills have only `name` and `description` frontmatter while runtime-specific exceptions match their metadata.
- Searches over common canonical instructions find no `$ARGUMENTS`, slash skill invocation, dollar skill invocation, `.claude/`, `.agents/`, `CLAUDE.md`, `AGENTS.md`, `claude -p` or `codex exec`; renderer fragments contain every required runtime-specific form.
- The generated Claude and Codex golden files retain the required invocation, project-instruction, role and sandbox wording for their environments.
- Main `SKILL.md` files link every extracted reference they require, and tests fail on a missing referenced file.
- `bash tests/run.sh` exits 0 and both installation trees remain behaviorally equivalent to their pre-conversion golden fixtures.

## Reference

- spec.md § Canonical content decision, Interfaces
- Claude renderer from ticket 02
- Codex renderer from ticket 03
- `skills/*/SKILL.md`, `skills/plan-feature/templates/`
- official skill layout guidance summarized in the repository plan discussion

## Answer
