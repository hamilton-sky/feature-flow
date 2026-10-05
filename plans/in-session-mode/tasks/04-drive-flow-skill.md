# Add the drive-flow skill

Type: task
Status: open
Blocked by: 01, 03
Test first: no

Add `skills/drive-flow/SKILL.md`, the skill a user types as `/drive-flow <feature>`. Give it the same frontmatter shape as `skills/run-flow/SKILL.md`: `name: drive-flow`, a `description`, `argument-hint: "[feature]"` and `disable-model-invocation: true`. Write it in the voice and structure of the other skills.

What it says, in order:

1. Take the feature from `$ARGUMENTS`. If none was given, list `plans/*/` and ask.
2. Before starting: `git status --porcelain` must be empty, `bash scripts/flow-status.sh <feature> --check` must print `OK`, and both `ticket-builder` and `ticket-reviewer` must be installed (`.claude/agents/` or `~/.claude/agents/`). If an agent is missing, stop and tell the user to run `bash install.sh`. Then tell the user what is about to happen: every ticket costs at least two subagent runs, this session's context grows with every ticket, and the limits are the same variables as the loop (`FLOW_MAX_RETRIES`, `FLOW_MAX_REVIEW_ROUNDS`). Ask for a yes.
3. The loop: run `bash scripts/flow-step.sh <feature> next` and act on the line it prints, and only on that line. `BUILD`: spawn a `ticket-builder` subagent with the builder prompt from ticket 01's Answer. `REVIEW`: spawn a `ticket-reviewer` subagent with the reviewer prompt from ticket 01's Answer, save the subagent's whole reply to `.git/flow-review-<feature>.txt`, run `bash scripts/flow-step.sh <feature> verdict .git/flow-review-<feature>.txt`, then `next` again. `DONE`: report how many tickets were resolved and suggest `/show-flow <feature>`. `STOP`: report the reason and show `bash scripts/flow-status.sh <feature>`.
4. The rules: never run the gate, the floor guard or a review yourself, never edit a ticket or commit, never choose the order or skip a line, and relay one short line per phase to the user instead of pasting the subagent's output. The script judges from the repo, so doing less than it asks only makes it ask again.

Copy the two prompts from ticket 01's Answer exactly, placeholders included (`<feature>`, `<NN>`, `<ticket>`, `<sha>`), so the skill and the answer cannot drift. If ticket 01 found that a subagent cannot read a skill file, follow what its Answer says to do instead.

## Not in this ticket

- The conductor script: tickets 02 and 03.
- Leaving the skill out of the Codex install: ticket 05.
- Documentation in the README: ticket 06.

## Done when

- `sed -n 1,6p skills/drive-flow/SKILL.md` shows `name: drive-flow`, an `argument-hint:` line and `disable-model-invocation: true`.
- `for a in BUILD REVIEW DONE STOP; do grep -c "$a" skills/drive-flow/SKILL.md; done` prints four numbers that are each at least 1, `grep -c 'scripts/flow-step.sh' skills/drive-flow/SKILL.md` is at least 1, and `grep -cE 'bash scripts/(gate|floor-guard)\.sh' skills/drive-flow/SKILL.md` prints `0`.
- `for k in builder reviewer; do p=$(sed -n "s/^Prompt that worked ($k): //p" plans/in-session-mode/tasks/01-probe-subagents.md); grep -cF -- "$p" skills/drive-flow/SKILL.md; done` prints `1` twice.
- `bash install.sh "$(mktemp -d)"` installs `.claude/skills/drive-flow/SKILL.md`, a second run adds nothing, and `bash tests/run.sh` exits 0 with checks for these four bullets.

## Reference

- spec.md § Happy path, Interfaces
- skills/run-flow/SKILL.md and skills/next-phase/SKILL.md (read only; the model for voice and structure)
- plans/in-session-mode/tasks/01-probe-subagents.md (the prompts to copy)
- tests/run.sh (the `install.sh` section)

## Answer

