# Trying feature-flow on your own repo

A run on your repo, with a feature you actually need, teaches more than another release. The field runs so far are why 0.19.0 to 0.23.0 exist (see [releases.md](releases.md)). This page is the checklist, and `feature-flow eval` and `feature-flow report` give you the numbers.

## Before

1. A repo with a test command that runs in about a minute or less, or a slow suite plus a faster subset you can name with `Quick:` in `commands.md`.
2. A feature of 3 to 6 tickets that you can describe in a few sentences. If it has a behaviour a test can reach from outside, keep the planner's `Acceptance:` line, so a tester writes acceptance tests from the spec before the build.
3. Pick a profile: `normal` for a first run, `careful` where a wrong "done" is expensive, `fast` for a small, low-risk feature.
4. Install it so it stays out of your history: `feature-flow install . --private` (or `--user` once for every repo).
5. For Codex: `--agent codex`, and run it on your own machine.

## During

Talk the feature through, then `/feature-flow` (Codex: `$feature-flow`). Say yes twice. To try the brainstorm too, add `brainstorm` (`/feature-flow <feature> brainstorm`); [brainstorm.md](brainstorm.md) shows what to expect, and the review page and its diagram editor are worth a note of their own. Let it run, and write down anything you did not expect. To try the guided flow, start with `brainstorm` and no type: the session asks the start card's question, and the run should stop for you three times in all (the start card, the brainstorm's pick and the plan's yes). On the plan's yes, look at the width the card shows and try one choice (the lanes, a full review or a builder note); [guided-flow.md](guided-flow.md) shows each stop. If another agent drives the session for you, add `agent` (`/feature-flow <feature> agent`), so the eval does not count its stops as your time.

## After

The skill records the run when it reaches `DONE`: `plans/<feature>/eval.json` and the form `plans/<feature>/eval-verdict.md`, which it fills in with your answers. If it did not (an old install, or a run that stopped), run it from the repo:

```bash
feature-flow eval <feature>          # writes eval.json and the form; fill the form, run it again
feature-flow report <feature>        # the same log, as a table
feature-flow eval <feature> --later  # a week or two later: fixes and reverts on the files the run touched
```

It reads `.feature-flow/state/flow-<feature>.log` and prints, per ticket, how many times it was built and reviewed, which checks failed, and the run's STOPs with their reasons, resets and handoffs. A ticket built more than once was reworked; a STOP is where the flow wanted you.

It does not see the trust runner's own STOPs (`flow-trust.py does not match this skill`, `flow files changed since the last step`), because the runner stops before the conductor logs anything. Count those from the session by hand: they are how you tell whether the session copied the long loader line correctly.

Fill in `eval-verdict.md`, above all whether each catch was real or a false alarm: that count is the only way to tell whether the checks earn their cost. Then answer five questions:

1. Where did it stall?
2. Which STOPs did you not expect?
3. Which tickets needed a rework round, and why?
4. Did the session ever mangle the loader line or lose a digest?
5. Was the plan right: did the tickets match what you wanted built?
6. For a guided run: did it stop more than three times (eval's `guided stops` line), was the start card's setup right, and did the helpers' ideas reach the pick (eval's `helpers' ideas` line)? Did `Lanes: auto` build as many tickets at once as the card said?

Keep `.feature-flow/state/` (the log and state files) and open an issue at https://github.com/hamilton-sky/feature-flow/issues with `eval.json` attached, the report output and your answers.

## Recording a run (eval)

Every finished run can leave a record of what it cost and what it caught, so a trial on your own repo gives an answer, not an impression. On `DONE` the skill runs `python3 scripts/flow-status.py <feature> --eval` (or run `feature-flow eval <feature>` yourself) and asks you a few questions.

- **`plans/<feature>/eval.json`**: tickets, builds, reviews and rework; tickets settled when the plan was approved and never built; every catch by the check that made it (gate, floor guard, Done when, test first, footprint, reviewer, feature review); the follow-ups in `followups.md` and the deferred checks; who drove the run (`driver`: `person` or `agent`); where the run needed its driver (stops, questions, handoffs, resets); active minutes; and tokens.
- **`plans/<feature>/followups.md`**: what the run left for later, committed as it goes: the `minor` findings of every passing review, the findings a level 2 ticket passed with after its full rounds, and each `needs` check (below) that could not pass on this host.
- **Tokens** come from Claude Code's own session transcripts (`~/.claude/projects/`, or `CLAUDE_CONFIG_DIR`), never from the agent: every message of the sessions and subagents that worked in this repo during the run, each counted once, by model and, without lanes, split per ticket by time. Codex sessions are not read yet.
- **codeintel**: when an agent asked [codeintel](helpers.md#codeintel-optional), `codeintel` in `eval.json` counts the queries by op and what the agents said of the answers (helped, no answer, wrong, and why), and the form below asks whether it helped.
- **`plans/<feature>/eval-verdict.md`**: a form for you. Was the plan right, how many fixes you made by hand, would you use it again, and for each catch whether it was real or a false alarm. Run `--eval` again and your answers land in `eval.json`. The false-alarm count is the only way to tell whether the checks are worth their cost.
- **Timing**: `timing` in `eval.json` gives the wall clock, the minutes by phase, by ticket and by level, the slowest ticket and how many times the whole `Test` ran. `feature-flow eval <feature> --compare <eval.json> ...` puts several runs side by side.
- **Later:** `feature-flow eval <feature> --later`, a week or two on, lists the commits since the run whose subject says fix, revert, bug or regression on the paths each ticket's `Touches:` names: the defects the run let through.

Both files sit in the plan folder, so they are committed with it and survive a cloud session. Nothing is sent anywhere; attach `eval.json` to a field-run issue if you want to share it. Run logs from before 0.15.0 have no dates, so they give no tokens.
