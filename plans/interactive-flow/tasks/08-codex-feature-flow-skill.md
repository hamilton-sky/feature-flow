# Add the feature-flow skill for Codex

Type: task
Status: open
Blocked by: 02, 05, 06
Test first: no

Add `adapters/codex/feature-flow/SKILL.md` and `adapters/codex/feature-flow/agents/openai.yaml` (with `allow_implicit_invocation: false`), written by hand, not generated. The Codex user types `$feature-flow <feature> [show] [auto]`. Frontmatter: only `name` and a quoted `description`. It follows the Claude skill step for step, with three differences:

- It calls the script with `FLOW_INVOKE='$feature-flow'`, and says `<arguments>` (what the user typed after the skill name) where Claude says `$ARGUMENTS`.
- It preserves the Claude skill's plan-commit boundary, session token on every conductor call and explicit-only takeover rule.
- If ticket 02 found `Codex mode: subagents`, BUILD and REVIEW spawn subagents with the wording it recorded, putting the role text from `prompt` first. If it found `relay`, the skill sets `FLOW_RELAY=1`: on BUILD the session does the build itself from `prompt`; on REVIEW it does the review itself, without editing anything, saves its reply and runs `verdict`; on `HANDOFF` it tells the user to start a new session with the printed line, and for a review to start it read-only with the command ticket 02 recorded.
- It reads `AGENTS.md` where the Claude skill reads `CLAUDE.md`.

## Not in this ticket

- The installer placing it, and deleting `adapters/codex/skill.awk`: the next ticket.

## Done when

- `sed -n 1,4p adapters/codex/feature-flow/SKILL.md` shows `name: feature-flow` and a quoted `description:`, and no `disable-model-invocation` or `argument-hint` line.
- `grep -c 'allow_implicit_invocation: false' adapters/codex/feature-flow/agents/openai.yaml` prints `1`.
- `grep -c "FLOW_INVOKE='\$feature-flow'" adapters/codex/feature-flow/SKILL.md` is at least 1, and `grep -cE '(^|[^$])/feature-flow|\$ARGUMENTS' adapters/codex/feature-flow/SKILL.md` prints `0`.
- The mode in the skill matches ticket 02's `Codex mode:` line (relay mode: `grep -c 'FLOW_RELAY=1'` is at least 1; subagents: it is `0`), and `bash tests/run.sh` exits 0.

## Reference

- plans/interactive-flow/tasks/02-probe-codex-sessions.md (the mode and wording)
- skills/feature-flow/SKILL.md (the Claude version)
- adapters/codex/skill.awk (read only; what the Codex rendering used to change)

## Answer
