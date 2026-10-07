# Build one ticket

Work one ticket of the feature you were given.

You are given the **feature**, and possibly the word `auto` and a ticket number. `auto` means unattended: ask nothing, commit at the end. A number means "this ticket" instead of the next ready one. Example: `csv-export auto 03`.

Default is **manual**: you confirm before work starts and you commit yourself.

## Step 1: Locate the tickets

Follow the repo's documented ticket location if it has one. Otherwise they are in `plans/<feature>/tasks/` with `plans/<feature>/map.md` beside them. If the folder is missing, list `plans/*/` and ask which one was meant (in auto mode, stop).

## Step 2: Pre-flight

Run `git status --porcelain`. Files listed in `.feature-flow/installed.txt`, and that list itself, are feature-flow's own install and do not count, and neither does untracked Python bytecode (`__pycache__/`, `*.pyc`).

- Clean: continue.
- Dirty, manual: show the files and offer to commit, stash, or continue anyway.
- Dirty, auto: **stop** and say so. An unattended run must start from a known state.

## Step 3: Pick the ticket

Run `python3 scripts/flow-status.py <feature> --next`.

- Exit 0: the path printed is your ticket.
- Exit 10: the feature is complete. Say so and stop.
- Exit 11: nothing is ready. Run it without flags, explain what is claimed or blocked, and stop.

If a ticket number was given, check that its `Status` is open and every ticket in `Blocked by` is resolved. If not, explain.

Without the script: read every ticket's `Status:` and `Blocked by:` lines and pick the lowest numbered open ticket whose blockers are all resolved.

## Step 4: Read

- The ticket, all of it.
- The spec sections it references, and every file under `## Reference`. Read before you edit.
- `map.md` Decisions so far.
- `commands.md` (the real build, test, lint and smoke commands: use these, do not guess) and `learnings.md` (traps earlier workers found: read all of it).
- The `## Answer` of every ticket it is blocked by. This is the handoff from earlier work: decisions, gotchas, changed assumptions. Trust it over the original plan.
- Any `## Review findings` in the ticket. They are mandatory fixes from an independent review or the floor guard. Deal with every one first, then prove them again. If you think a finding is wrong, do not skip it silently: say why, with evidence, under **Review fixes** in the Answer.

## Step 5: Claim

Run `git rev-parse HEAD` and note the commit: it is where this ticket's work starts, and a reviewer needs it. Then set `Status: claimed` in the ticket and save it, before touching any code.

## Step 6: Say what you will do

In manual mode, show this and wait for a yes. In auto mode, skip it.

```
Ticket NN: <title>   (Type: task | settle | convert)
Will change:   <files>
Will not touch: <the ticket's Not in this ticket>
Done when:     <the bullets>
Proceed?
```

## Step 7: Implement

- Follow the ticket and the project's conventions (the project's agent instructions file, CLAUDE.md or AGENTS.md, and any rules it points to).
- Stay inside the ticket. **No silent refactoring**: do not rename, extract, reformat, add comments or reorganise in files you touch unless the ticket asks. Messy neighbouring code stays as it is.
- **Lazy about the solution, never about reading.** Read every file you will touch first. Then take the smallest solution, in this order: does it need to exist at all? is it already in the codebase? the standard library? a native feature of the platform? a dependency that is already installed? one line? Only then write new code. Never cut: validation at trust boundaries, handling that prevents data loss, security, accessibility, or anything the ticket asks for.
- **`Test first: yes`**: write the failing test first, run it, and see it fail for the right reason. Then write the code. If you wrote production code before the test, delete it and start from the test.
- **Never weaken the bar to pass it.** No skipped or deleted tests, no silenced linters or type checks, no empty catches, no lowered thresholds, no edits to lint, test or CI config, unless the ticket has a `Floor: allow` line for it. If the bar cannot be met, stop and go to Failure handling.
- **Do not edit the flow's own code**: `feature_flow/`, `scripts/`, the guides and the roles, unless the ticket has `Floor: allow flow-edit`. The conductor stops the run if they change.
- Focused tests (`.only(`, `fit(`, `fdescribe(`) and skipped tests are findings.
- `settle` ticket: write no code. Weigh the options and write the decision, the reasons and the rejected alternatives in the Answer. If the decision is truly the user's, ask (manual) or stop and go to Failure handling (auto).
- `convert` ticket: run the converter, read its counts, and compare them with the ticket.

## Step 8: Prove it

For every bullet in **Done when**, in this order:

1. Name the command.
2. Run it fresh, in full, now. A result from earlier in the session does not count.
3. Read all of its output and its exit code.
4. Check that the output says what the bullet claims.
5. Only then write the claim.

"Should", "probably", "seems" and "looks right" mean you have not proved it. Reading the code is not running it. If a bullet cannot be run here (a service is down, a credential is missing), the ticket is not done: go to Failure handling.

Fix failures that are inside the ticket. If a fix needs changes outside it, go to Failure handling.

| You think | What is true |
|---|---|
| "It passed before my last edit." | Run it again after the last edit. |
| "The suite is slow, I will run it once at the end." | A late failure costs more. Run it now. |
| "I will loosen this check a little." | That is weakening the bar. Stop and report. |
| "This neighbouring file is messy, I will tidy it." | Not in the ticket. Leave it. |
| "The reviewer will catch it." | You are the first check. Prove it yourself. |
| "Same command twice, so it must be fine." | Running an identical command with no change in between proves nothing. |

## Step 9: Resolve

Under `## Answer` write:

- **Built**: the files created or changed.
- **Proof**: for each Done when bullet, the numbers or output that showed it.
- **Decisions**: what you chose and why.
- **Shortcuts taken**: each deliberate shortcut, where it stops working, and what would make it worth upgrading. Write them here, not as code comments. Write "none" if there were none.
- **Review fixes**: only if the ticket had `## Review findings`: for each, what you changed, or why you disagree.
- **For later tickets**: anything the next worker must know. If your work makes a later ticket wrong, name that ticket and say what changes. Do not edit other tickets yourself.

Set `Status: resolved`. Add one line to `map.md` under Decisions so far: `NN — <the gist>`. Do not write status into the map.

If you learned something a fresh worker would waste time rediscovering (a command that works, a trap, a quirk of the environment), append one or two lines to `learnings.md`, tagged `(NN)`. Append only: never edit or delete another line, and do not repeat what is already there.

**You may change only:** your own ticket's `Status` line and Answer, lines appended to `map.md` and `learnings.md`, and the code the ticket calls for. The floor guard fails anything else: other tickets, the spec, `commands.md`, and any edit to your own ticket's text above the Answer (rewriting your own Done when to make it pass is the same as skipping a test). If one of those really has to change, say so in the Answer and stop; a human decides.

## Step 10: Commit

- **Auto**: commit the code, the ticket and the map together. Message: `<type>(<feature>): NN <ticket title>`. Follow the repo's commit conventions and any attribution rule in the project's agent instructions file, CLAUDE.md or AGENTS.md. If the ticket folder is git ignored, leave it out of `git add`. Never push.
- **Manual**: show the suggested message and leave the commit to the user.

## Independent review

You wrote this change, so you are the wrong one to judge it.

- **Auto**: do not review your own work. The flow runs the gate, the floor guard and a fresh reviewer (one that never saw your reasoning, following the review guide) after you finish, and sends you back with `## Review findings` if either objects.
- **Manual**: after the commit, offer to run the independent review now. If the user says yes, hand it to a fresh reviewer that never saw your reasoning (a subagent, or a new session) with the ticket-reviewer role and the review guide, for `<feature> NN <start-commit>`, and show them the verdict.

  Use the commit you noted in Step 5. Never review it in this conversation yourself.

## Step 11: What is next

Run `python3 scripts/flow-status.py <feature> --counts` and `--next`, then report:

```
NN resolved: <title>
Next ready: MM <title>      (or: feature complete)
Continue in a fresh session with the feature-flow skill for <feature>
```

## Failure handling

- **Build or test fails inside the ticket**: fix it and re-run. After two failed fixes of the same error, stop.
- **The fix needs files outside the ticket**: stop. Set `Status: open`, add an `## Attempt note` (what failed, what is needed), and offer: widen the ticket, add a new ticket for the outside part and block this one on it, or roll back.
- **A test that was already failing**: report it and leave it alone.
- **The ticket names code that moved**: search for the real location, adapt, and say so in the Answer.
- **Rollback**: show `git diff --stat` and ask before `git checkout --` (manual). In auto mode never discard work; stop.
- **Auto mode and you must stop**: leave `Status: open`, add the Attempt note, and exit. The flow treats a ticket that is not resolved as a failed attempt.
