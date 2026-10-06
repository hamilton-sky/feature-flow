---
name: review-ticket
description: Use to independently review one finished ticket in a fresh session. Reads only the ticket and its diff, re-runs every Done-when, hunts for bugs and weakened checks, and ends with REVIEW PASS or REVIEW FAIL. Never edits anything.
argument-hint: "[feature] [ticket-number] [base-commit]"
disable-model-invocation: true
---

You are the **reviewer**, not the author. You did not write this change and you do not trust the author's account of it.

Parse `$ARGUMENTS`: feature, ticket number (two digits), and optionally the commit the work started from. If no base commit is given, review `HEAD~1..HEAD`.

**You must be a fresh session.** If this conversation shows that you wrote or edited code for this ticket, stop. Do not review it here. Tell the user to run this from a terminal instead, and give them the command with the arguments filled in:

```
claude -p "/review-ticket <feature> <NN> <base-commit>" --agent ticket-reviewer --allowedTools "Read,Glob,Grep,Bash" < /dev/null
```

(Leave out `--agent ticket-reviewer` if the agent file is not installed.)

## What you may read

The author writes the `## Answer` into the ticket itself, so the ticket as it stands now carries their account of the change, and so does the ticket's own hunk in the diff. Both routes leak it into your context before you notice. Avoid both:

**The ticket, as it was before the work.** At `<base>` the `## Answer` heading is still empty, so this gives you the whole ticket with none of the claim. Resolve the exact filename first, then ask for that one blob:

```
TICKET=$(git ls-files 'plans/<feature>/tasks/NN-*.md')   # exactly one path, or fix the pattern
git show "<base>:$TICKET"
```

Never put a `*` inside the `<rev>:<path>` argument. `git show '<base>:plans/<feature>/tasks/NN-*.md'` does not glob and does not fail: git rereads it as a pathspec, prints the **HEAD** commit instead, and hands you the ticket hunk with the Answer in it. Exit status is 0 either way, so the only tell is the commit header at the top of the output.

Take from the ticket the description, `Type`, `Test first`, `Not in this ticket`, `Done when`, `Reference`, and any `## Review findings` from earlier rounds. If the ticket did not exist at `<base>` (it was added later), read the working copy but cut it off at the Answer: `sed '/^## Answer/q' "$TICKET"`.

**The range: stop at the ticket's own last commit, not at `HEAD`.** `HEAD` keeps moving. A later ticket, a tooling change, anything committed after this ticket lands inside `<base>..HEAD`, and the scope check then charges it to an author who never touched it. Find where this ticket's work actually ends:

```
END=$(git log --format=%H "<base>..HEAD" -- "$TICKET" | head -1)   # newest commit touching this ticket
[ -n "$END" ] || END=HEAD                                          # none found: fall back, and say so
```

Every commit for a ticket touches its ticket file, because the author commits the code, the ticket and the map together. If `$END` is not `HEAD`, there are later commits you are deliberately not reviewing: say so in your report.

**The diff, with the ticket folder held back:**

```
git diff --stat "<base>..$END"                                   # every changed file, for the scope check
git diff "<base>..$END" -- . ':(exclude)plans/<feature>/tasks/'  # the content you review
```

Read the files that diff touches. For the ticket's own `Status` line, grep the hunk rather than opening it: `git diff "<base>..$END" -- "$TICKET" | grep '^[+-]Status:'`.

(Substitute the repo's own ticket folder if it keeps them elsewhere.)

**Do not read `## Answer`.** It is the author's claim. Your job is to check the work without it. If it reaches you anyway, do not pretend it did not: say so in your report, and name any verdict you had already formed before it arrived.

## What you must not do

Edit, write, stage, commit, stash, check out or reset anything. You may run read-only commands and the commands in `Done when`. If a command leaves files behind, say so in your report and leave them.

## Verdict 1: does it meet the ticket?

For every bullet under **Done when**: run its command yourself, now, and write `MET` or `NOT MET` with what the command printed. A bullet you could not run is `NOT MET`.

Then scope: over `<base>..$END` only, list every changed file that the ticket does not call for, or that `Not in this ticket` rules out. Unrelated refactors, renames and reformatting count. A file changed by a commit outside that range is not this author's and is not a scope violation.

If the ticket says `Test first: yes`: check that the diff adds or changes a test, and say whether that test would fail without the production change.

## Verdict 2: is it good?

Look for, in this order:

- bugs and missing handling at boundaries (input, files, network, empty and error cases)
- checks made weaker instead of being met: skipped or deleted tests, silenced linters, empty catches, lowered thresholds, tests that cannot fail
- code that need not exist: something the standard library, the platform or the codebase already provides; a feature nobody asked for; a longer way of doing a shorter thing
- anything a later ticket will trip over

Rate each finding `blocker`, `major` or `minor`, name the file, and say what to change.

## Output

Use exactly this shape. Keep it short; no praise.

    SPEC
    - <Done when bullet>: MET | NOT MET - <command and what it printed>
    - scope: OK | <files outside the ticket>
    - test first: n/a | OK | MISSING

    QUALITY
    1. blocker|major|minor <file>: <finding> - <what to change>

    REVIEW: PASS

The indentation above only marks where the template starts and stops. Write your own report flush left, as plain text, and **do not wrap it in a code fence** - a fence closes with a line of its own after the verdict, which breaks the rule below.

The last line of your whole reply must be exactly `REVIEW: PASS` or `REVIEW: FAIL`, flush left: no closing fence, no trailing note, no sign-off, nothing after it. The flow (`scripts/auto-flow.sh` and `scripts/flow.py`) takes the last line that matches `^REVIEW: (PASS|FAIL)[[:space:]]*$`, so a verdict line that is indented, bulleted, bolded or otherwise decorated is not found at all and the flow records the review as having returned no verdict. Anything you still want to say goes above the verdict line.

`PASS` only if every Done when bullet is `MET`, scope is `OK`, test first is not `MISSING`, and there is no `blocker` or `major` finding. `minor` findings are listed but do not fail the review. When in doubt, fail it and say why.
