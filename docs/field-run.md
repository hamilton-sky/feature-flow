# Trying feature-flow on your own repo

feature-flow has mostly been run on itself. A run on a different repo, with a feature you actually need, teaches more than another release. This page is the checklist, and `feature-flow report` gives you the numbers.

## Before

1. A repo with a test command that runs in about a minute or less, or a slow suite plus a faster subset you can name with `Quick:` in `commands.md`.
2. A feature of 3 to 6 tickets that you can describe in a few sentences.
3. Install it so it stays out of your history: `feature-flow install . --private` (or `--user` once for every repo).
4. For Codex: `--agent codex`, and run it on your own machine.

## During

Talk the feature through, then `/feature-flow` (Codex: `$feature-flow`). Say yes twice. Let it run, and write down anything you did not expect.

## After

From the repo:

```bash
feature-flow report <feature>
```

It reads `.feature-flow/state/flow-<feature>.log` and prints, per ticket, how many times it was built and reviewed, which checks failed, and the run's STOPs with their reasons, resets and handoffs. A ticket built more than once was reworked; a STOP is where the flow wanted you.

It does not see the trust runner's own STOPs (`flow-trust.py does not match this skill`, `flow files changed since the last step`), because the runner stops before the conductor logs anything. Count those from the session by hand: they are how you tell whether the session copied the long loader line correctly.

Then answer five questions:

1. Where did it stall?
2. Which STOPs did you not expect?
3. Which tickets needed a rework round, and why?
4. Did the session ever mangle the loader line or lose a digest?
5. Was the plan right: did the tickets match what you wanted built?

Keep `.feature-flow/state/` (the log and state files) and open an issue at https://github.com/hamilton-sky/feature-flow/issues with the report output and your answers.
