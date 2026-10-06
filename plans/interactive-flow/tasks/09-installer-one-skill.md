# Make the installer install the one skill

Type: task
Status: open
Blocked by: 07, 08
Test first: yes
Floor: allow test-delete

Change `install.sh` so both agents get one flow skill instead of five. Claude: `skills/feature-flow/` to `.claude/skills/feature-flow/`, the two agents to `.claude/agents/` as today. Codex: `adapters/codex/feature-flow/` to `.agents/skills/feature-flow/`, the roles to `.agents/flow-roles/` as today. Both: the scripts to `scripts/` as today, and `guides/` to `.feature-flow/guides/` and the role files to `.feature-flow/agents/` so `flow.sh prompt` finds them. `architect-review` and `automation-design` are still installed as they are.

Stop installing `plan-feature`, `next-phase`, `review-ticket`, `run-flow` and `show-flow`. If a target already has any of them, print one line naming them as no longer part of feature-flow and leave them alone. Delete `adapters/codex/skill.awk` and the code in `install_codex` that runs it; architect-review and automation-design are copied for Codex with only the `name`/`description` header reduction they need, done without phrase rewriting. Remove the tests that covered the awk rules and add tests for the new layout; the options `--agent`, `--user`, `--force`, `--dry-run` keep working.

## Not in this ticket

- Deleting `skills/next-phase` and the other old skill folders from this repo, and the headless loop: ticket 10.
- The README: ticket 11.

## Done when

- `bash install.sh "$(mktemp -d)"` installs `.claude/skills/feature-flow/SKILL.md`, the two agents, `scripts/flow.sh` and `.feature-flow/guides/build.md`, and no `.claude/skills/next-phase`; a second run adds nothing.
- `bash install.sh "$(mktemp -d)" --agent codex` installs `.agents/skills/feature-flow/SKILL.md` and its `agents/openai.yaml`, identical to the files in `adapters/codex/feature-flow/`.
- A target with an existing `.claude/skills/next-phase/` keeps it, and the output names it as no longer part of feature-flow.
- `test ! -e adapters/codex/skill.awk` succeeds, and `bash tests/run.sh` exits 0 with checks for these bullets.

## Reference

- install.sh (`place`, `copy_tree`, `install_codex`)
- tests/run.sh (the `install.sh` and `install.sh, codex` sections)

## Answer
