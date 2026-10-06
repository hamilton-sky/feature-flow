# Find out what a Claude Code subagent can do for this flow

Type: settle
Status: resolved
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

Pasted prompt works: yes
File-path prompt works: yes
Verdict reaches the parent: yes
Reviewer is independent: yes
Writing under .git works: yes

Probed by hand in an interactive Claude Code session in a prepared demo project. Both builder prompts worked and behaved the same. The pasted form (about 9.8k characters, the whole `next-phase` skill) resolved ticket 01 and committed it. The file-path form (57 characters) resolved ticket 02, because 01 was already resolved by then, so "next ready" moved on. Both builders ran every Done-when command themselves (each reply shows the run), wrote Status, Answer, a map line and learnings, committed, and said they had not reviewed their own work. Naming the file is as reliable as pasting it and far cheaper, so the conductor should name the file.

Reviewers: all four first-round runs (one per prompt form, on each of tickets 01 and 02) ended with `REVIEW: PASS`, and the final reply reached the parent. Two ticket-02 reviewers wrapped the report in a ``` fence, so their last line was the closing fence, not the verdict (the skill's own template sat inside a fence and the reviewers copied it). `feature_flow/conductor.py` matches `^REVIEW: (PASS|FAIL)$` on any line and keeps the last match, so a trailing fence is harmless there. A verdict that is indented or decorated is not matched, and then no verdict is recorded.

Independence: the made-up word was held only in the parent. Two running reviewers were asked whether they knew it, by `SendMessage` while they worked (a variant of "spawn and ask only that"), and both said no and grepped the repo to check. That passes. The probe also found a leak the word test cannot see: every first-round reviewer reported, unprompted, that the author's `## Answer` reached it, by reading the ticket at HEAD (where the Answer is already written) and through the ticket's own hunk in `<base>..HEAD`. A reviewer sees the author's account unless the skill says how to avoid it.

Writing under `.git`: the parent wrote `.git/flow-review-hello.txt` with Bash (`cat > .git/flow-review-hello.txt <<'EOF'`, later `cat >>`), with no permission refusal. The Write tool was never tried on that path, so whether it is refused is unknown. Use Bash.

Three defects in `skills/review-ticket/SKILL.md`. They were fixed in the probe copy first (commits `5d49529`, `4551f89`, `831cea0` in the throwaway project `~/ff-probe-claude`, each checked by a live reviewer), then ported to `skills/review-ticket/SKILL.md` in a separate commit on the same branch as this Answer, so this ticket's own diff leaves the skill alone:

1. **Answer leak.** Read the ticket at `<base>` (the `## Answer` heading is an empty stub there) and exclude `plans/<feature>/tasks/` from the reviewed diff. Resolve the filename first with `TICKET=$(git ls-files 'plans/<feature>/tasks/NN-*.md')` and run `git show "<base>:$TICKET"`. A `*` inside `<rev>:<path>` does not glob and does not fail: git reads it as a pathspec, prints the HEAD commit and serves the Answer hunk, exit 0. A reviewer then reported `LEAK CHECK: No`.
2. **Fence.** Replace the fenced output template with an indented one, so reviewers have no fence to copy and the verdict is the last line, flush left. Both prompt forms then emitted it flush left.
3. **Moving range.** Reviewing `<base>..HEAD` absorbs every commit that lands after the ticket, so the same finished ticket passed or failed depending on when it was reviewed (one ticket-02 reviewer failed it over a file its author never touched). End the range at the ticket's own commit, found from the ticket file. The re-run passed.

### For later tickets

Builder prompt that worked, file form (the pasted form works too, but costs 9.8k characters for nothing):

```
Follow .claude/skills/next-phase/SKILL.md for: <feature> auto
```

The skill also accepts a ticket number (`<feature> auto <NN>`). The probe did not pass one, so use `<NN>` only after trying it once. Without it the builder takes the next ready ticket.

Reviewer prompt that worked, file form:

```
Follow .claude/skills/review-ticket/SKILL.md for: <feature> <NN> <sha>
```

`<sha>` is `HEAD` as it was before the builder's commit. The pasted form that worked started with `Follow these instructions exactly. They are the contents of the review-ticket skill.`, then `$ARGUMENTS: <feature> <NN> <sha>`, `---` and the whole `SKILL.md`.

- **Agents run in the background.** The `Agent` call returns a stub ("launched"); the real final reply arrives later as a notification, and that reply is what `verdict` should be given. The conductor's prompt must tell the session to wait for it before running `verdict`, and to save it with Bash as above.
- **Parent saves the reply with Bash,** not Write, to `.git/flow-review-<feature>.txt`.
- **The three fixes are in `skills/review-ticket/SKILL.md`.** Ticket 05 writes `guides/review.md` from that text, so copy it as it is now, not from an older checkout. One wording change from the probe copy: the verdict-matching sentence names `scripts/flow.py` as well as `scripts/auto-flow.sh`. The probe folder is no longer needed.
- **Stale git snapshot.** A subagent's session-start git status is frozen. One reviewer saw `init` and a clean tree while `git log` showed two more commits, and said so. Tell builder and reviewer prompts to run `git log` and `git status` themselves and not trust the snapshot.
- **Reviewers leave `__pycache__`.** Most reviewers' Done-when runs left a gitignored `__pycache__`, harmless but visible in a reply. `git status --porcelain` stayed empty, so the conductor's tracked-diff check is the right test.
