# Find out what a Claude Code subagent can do for this flow

Type: settle
Status: open
Blocked by: —
Test first: no

Every later ticket assumes three things about Claude Code subagents that nobody has checked here. Decide them by trying them, in a normal interactive Claude Code session. Do not do this in the unattended loop: its builder agent has no Agent tool, so it cannot run the probe. The user and the worker decide together.

Prepare a throwaway project with `FLOW_AGENT=claude bash tests/smoke-real.sh --prepare DIR`. It installs the skills and the two agents into `DIR/.claude` and makes the demo plan. Open Claude Code in DIR and try these with the Agent tool:

1. **Builder.** Spawn the `ticket-builder` subagent with a prompt that tells it to read `.claude/skills/next-phase/SKILL.md` and follow it for `hello auto`. Does it resolve ticket 01 (Status, Answer, commit) and run the Done when commands itself?
2. **Reviewer.** Spawn `ticket-reviewer` with a prompt that tells it to read `.claude/skills/review-ticket/SKILL.md` and follow it for `hello 01` and the sha from before the builder's commit. Does its final reply, which the main session can save to a file, end with `REVIEW: PASS` or `REVIEW: FAIL`? Did it leave the tree untouched?
3. **Independence.** Tell the main session a made-up word, then spawn the reviewer and ask only whether it knows that word. It must not.

Record the exact wording, because later tickets copy it. Write each prompt with the placeholders `<feature>`, `<NN>`, `<ticket>` and `<sha>` wherever the conductor's output will supply a value. If a subagent cannot read a skill file or cannot return a verdict, say what works instead (for example, the main session pastes the skill text into the prompt).

Put these lines in the Answer exactly, one per line, each starting at the beginning of the line:

```
Read-the-skill works: yes|no
Verdict reaches the parent: yes|no
Reviewer is independent: yes|no
Prompt that worked (builder): <the prompt>
Prompt that worked (reviewer): <the prompt>
```

## Not in this ticket

- The conductor script (tickets 02 and 03) and the skill (ticket 04). This ticket only decides what they can rely on.
- Codex. Whether Codex can spawn agents from a session is a separate question for a later round.

## Done when

- `grep -cE '^(Read-the-skill works|Verdict reaches the parent|Reviewer is independent): (yes|no)$' plans/in-session-mode/tasks/01-probe-subagents.md` prints `3`.
- `grep -cE '^Prompt that worked \((builder|reviewer)\): .+' plans/in-session-mode/tasks/01-probe-subagents.md` prints `2`.
- If any of the three yes or no lines says `no`, the Answer's For later tickets names which ticket changes and how.

## Reference

- spec.md § Design, Decisions
- agents/ticket-builder.md and agents/ticket-reviewer.md (read only)
- skills/next-phase/SKILL.md and skills/review-ticket/SKILL.md (read only)
- tests/smoke-real.sh, the `--prepare` mode

## Answer

