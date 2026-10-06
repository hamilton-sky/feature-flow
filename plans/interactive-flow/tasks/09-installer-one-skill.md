# Make the installer install the one skill

Type: task
Status: resolved
Blocked by: 07, 08
Test first: yes
Floor: allow test-delete

Change `install.sh` so both agents get one flow skill instead of five. Claude: `skills/feature-flow/` to `.claude/skills/feature-flow/`, the two agents to `.claude/agents/` as today. Codex: `adapters/codex/feature-flow/` to `.agents/skills/feature-flow/`, the roles to `.agents/flow-roles/` as today. Both: the scripts to `scripts/` as today, and `guides/` to `.feature-flow/guides/` and the role files to `.feature-flow/agents/` so `flow.py prompt` finds them. `architect-review` and `automation-design` are still installed as they are.

Both also get the Python package: `feature_flow/` to `.feature-flow/feature_flow/` (no `__pycache__`), next to the guides, so the `scripts/flow.py` shim finds it.

Stop installing `plan-feature`, `next-phase`, `review-ticket`, `run-flow` and `show-flow`. If a target already has any of them, print one line naming them as no longer part of feature-flow and leave them alone. Delete `adapters/codex/skill.awk` and the code in `install_codex` that runs it; architect-review and automation-design are copied for Codex with only the `name`/`description` header reduction they need, done without phrase rewriting. Remove the tests that covered the awk rules and add tests for the new layout; the options `--agent`, `--user`, `--force`, `--dry-run` keep working.

## Not in this ticket

- Deleting `skills/next-phase` and the other old skill folders from this repo, and the headless loop: ticket 10.
- The README: ticket 11.

## Done when

- `bash install.sh "$(mktemp -d)"` installs `.claude/skills/feature-flow/SKILL.md`, the two agents, `scripts/flow.py`, `.feature-flow/feature_flow/cli.py` and `.feature-flow/guides/build.md`, `python3 scripts/flow.py f start` runs from the installed repo, and no `.claude/skills/next-phase`; a second run adds nothing.
- `bash install.sh "$(mktemp -d)" --agent codex` installs `.agents/skills/feature-flow/SKILL.md` and its `agents/openai.yaml`, identical to the files in `adapters/codex/feature-flow/`.
- A target with an existing `.claude/skills/next-phase/` keeps it, and the output names it as no longer part of feature-flow.
- `test ! -e adapters/codex/skill.awk` succeeds, and `bash tests/run.sh` exits 0 with checks for these bullets.

## Reference

- install.sh (`place`, `copy_tree`, `install_codex`)
- tests/run.sh (the `install.sh` and `install.sh, codex` sections)

## Answer

Built: `install.sh` installs `feature-flow`, `architect-review` and `automation-design` (the `SKILLS` list) instead of every folder under `skills/`.
- Claude gets `skills/feature-flow/`.
- Codex gets `adapters/codex/feature-flow/` copied as it is. The other two skills get a Codex header (`codex_header`: name plus a quoted, escaped description, other keys dropped, body untouched). The roles go to `.agents/flow-roles/` without frontmatter (`role_body`).
- Both agents get `scripts/`, plus `.feature-flow/guides/`, `.feature-flow/agents/` and `.feature-flow/feature_flow/`. `copy_tree` now skips `__pycache__` and `*.pyc`.
- When the old flow skills are present, a target gets one line: `note: no longer part of feature-flow, left in place: <names>`. Nothing is deleted.
- `adapters/codex/skill.awk` is gone.
- The "next:" lines point at `/feature-flow` and `$feature-flow`. The missing-jq note is now a missing-python3 note.
- `tests/smoke-real.sh --prepare` tells the user to type `/feature-flow hello` or `$feature-flow hello`.

Proven: `bash tests/run.sh` 504 passed, 0 failed. The count dropped from 539 because the awk rule tests and the old Codex wording checks were removed, which `Floor: allow test-delete` covers. The new `install.sh` and `install.sh, codex` sections check each Done when:
- A default install has `.claude/skills/feature-flow/SKILL.md`, both agents, `scripts/flow.py`, `.feature-flow/feature_flow/cli.py` and `.feature-flow/guides/build.md`, and no old skill.
- `python3 scripts/flow.py f start` in the installed repo prints `PLAN`, then `OK <token>` once a plan folder exists.
- A second run adds nothing.
- The Codex skill and its `openai.yaml` are byte-identical to `adapters/codex/feature-flow/`.
- An existing `.claude/skills/next-phase/` is kept and named.
- `test ! -e adapters/codex/skill.awk` passes.
- `--user`, `--force`, `--dry-run` and `--agent all|codex|=codex` still work.
- PyYAML parsed every installed header and `openai.yaml`.

Decisions: `architect-review` and `automation-design` get no `openai.yaml`. They were never explicit-only, and Codex reads a skill without one. Their bodies still mention `$ARGUMENTS` and `/plan-feature`, because the ticket asked for no phrase rewriting.

Shortcuts taken: `scripts/` is still copied whole, so `auto-flow.sh` is still installed until ticket 10 deletes it. It now has no `next-phase` skill to start in an installed repo.

For later tickets: ticket 12's `--interactive` gets the new layout from `--prepare`. Ticket 10 deletes the old skill folders, `run-flow`, `auto-flow.sh` and the auto-flow test sections.
