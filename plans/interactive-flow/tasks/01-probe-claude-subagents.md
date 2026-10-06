# Find out what a Claude Code subagent can do for this flow

Type: settle
Status: open
Blocked by: —
Test first: no

Every later ticket assumes three things about Claude Code subagents that nobody has checked here. Decide them by trying them in a normal interactive Claude Code session. The unattended loop cannot do this (its builder has no Agent tool), so the user and the worker do it together.

Prepare a throwaway project with `FLOW_AGENT=claude bash tests/smoke-real.sh --prepare DIR`. It installs the skills and the two agents into `DIR/.claude` and makes the demo plan. Open Claude Code in DIR and use the Agent tool:

1. **Builder.** Spawn the `ticket-builder` subagent with a prompt that pastes the text of `.claude/skills/next-phase/SKILL.md` and tells it to follow it for `hello auto` on ticket 01. Does it resolve ticket 01 (Status, Answer, commit) and run the Done-when commands itself? Try once more where the prompt only names the file to read; record which works.
2. **Reviewer.** Spawn `ticket-reviewer` the same way with `.claude/skills/review-ticket/SKILL.md`, for `hello 01` and the sha from before the builder's commit. Does its final reply, which the main session can save to a file with the Write tool, end with `REVIEW: PASS` or `REVIEW: FAIL`? Did it leave the tree untouched?
3. **Independence.** Tell the main session a made-up word, then spawn the reviewer and ask only whether it knows that word. It must not.
4. **Writing under `.git`.** Can the main session write the reviewer's reply to `.git/flow-review-hello.txt` without a permission refusal? If not, does piping it through Bash work?

Put these lines in the Answer exactly, one per line, each starting at the beginning of the line:

```
Pasted prompt works: yes|no
File-path prompt works: yes|no
Verdict reaches the parent: yes|no
Reviewer is independent: yes|no
Writing under .git works: yes|no
```

Then, under For later tickets, the exact prompts that worked, with the placeholders `<ticket>`, `<NN>`, `<sha>` and `<feature>` wherever the conductor will supply a value.

## Not in this ticket

- Codex: ticket 02 probes it separately.
- The conductor and the guides that build these prompts: later tickets copy what this one finds.

## Done when

- `grep -cE '^(Pasted prompt works|File-path prompt works|Verdict reaches the parent|Reviewer is independent|Writing under \.git works): (yes|no)$' plans/interactive-flow/tasks/01-probe-claude-subagents.md` prints `5`.
- The Answer's For later tickets contains a builder prompt and a reviewer prompt that worked, each with the placeholders above.
- If any line says `no`, For later tickets says what works instead.

## Reference

- spec.md § Design, Decisions
- agents/ticket-builder.md and agents/ticket-reviewer.md (read only)
- skills/next-phase/SKILL.md and skills/review-ticket/SKILL.md (read only)
- tests/smoke-real.sh, the `--prepare` mode
- plans/in-session-mode/tasks/01-probe-subagents.md (the earlier version of this probe)

## Answer
