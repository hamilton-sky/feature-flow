# Trying feature-flow on your own repo

A run on your repo, with a feature you actually need, teaches more than another release. The field runs so far are why 0.19.0 to 0.23.0 exist (see [releases.md](releases.md)). This page is the checklist, and `feature-flow eval` and `feature-flow report` give you the numbers.

## Before

1. A repo with a test command that runs in about a minute or less, or a slow suite plus a faster subset you can name with `Quick:` in `commands.md`.
2. A feature of 3 to 6 tickets that you can describe in a few sentences. If it has a behaviour a test can reach from outside, keep the planner's `Acceptance:` line, so a tester writes acceptance tests from the spec before the build.
3. Pick a profile: `normal` for a first run, `careful` where a wrong "done" is expensive, `fast` for a small, low-risk feature.
4. Install it so it stays out of your history: `feature-flow install . --private` (or `--user` once for every repo).
5. For Codex: `--agent codex`, and run it on your own machine.

## During

Talk the feature through, then `/feature-flow` (Codex: `$feature-flow`). Say yes twice. To try the brainstorm too, add `brainstorm` (`/feature-flow <feature> brainstorm`); [brainstorm.md](brainstorm.md) shows what to expect, and the review page and its diagram editor are worth a note of their own. Let it run, and write down anything you did not expect. If another agent drives the session for you, add `agent` (`/feature-flow <feature> agent`), so the eval does not count its stops as your time.

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

Keep `.feature-flow/state/` (the log and state files) and open an issue at https://github.com/hamilton-sky/feature-flow/issues with `eval.json` attached, the report output and your answers.
