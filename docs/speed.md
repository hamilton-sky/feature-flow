# Speed and long runs

[← README](../README.md) · [Docs index](README.md)

How to make a run faster or more careful (profiles, lanes, the fast path, checkpoints, a time budget) and how a long feature moves across sessions.

## Profiles

Most of the settings in [Commands and settings](commands-and-settings.md) never need touching. One word picks a sensible set:

| Profile | Sets | For |
|---|---|---|
| `careful` | `FLOW_GATE_FULL=1`, `FLOW_REVIEWERS=2`, `FLOW_ROUND_REVIEW=on`, `FLOW_BASE_GATE=on`, `FLOW_FAST=0`, `FLOW_SMALL_LINES=0`, `FLOW_TICKETS_PER_SESSION=3` | code where a wrong "done" is expensive: the full gate and an own review for every ticket |
| `standard` | `FLOW_REVIEWERS=2`, `FLOW_ROUND_REVIEW=on`, `FLOW_BASE_GATE=on`, and `Gate: batch 3` unless the plan says otherwise | everyday features, and what a new plan's `commands.md` names: slower than `fast`, faster than `careful` |
| `normal` | nothing: the defaults | plans written before 0.30.0 |
| `fast` | `FLOW_FAST=1`, `FLOW_SCOUTS=off`, `FLOW_TICKETS_PER_SESSION=6`, and `Gate: end` unless the plan says otherwise | small, low-risk features: one feature review at the end |

**What `standard` does.** The gate runs once at the base before the first ticket, so a red base stops the run before a builder is blamed for it. Where one review would run, a quality reviewer and a ticket reviewer read the ticket side by side, both read only, in one subagent call each (`REVIEW <ticket> ... pair`); the session sends both replies to `verdict` and the conductor keeps the worse. On a level 1 or 2 ticket only a blocker sends the ticket back to its own builder; smaller findings go to `followups.md`, which later tickets' builders read. With an `Acceptance:` line the tester's tests run after each ticket and their output goes to the reviewers. Once every ticket is done, one more reviewer reads the whole round's diff against the plan. Level 3 and `Sensitive:` tickets keep their full own reviews. Since 0.34.0 `standard` also checkpoints the gate every 3 tickets (`Gate: batch 3`): the pair of reviewers then reads only the tickets that keep their own review, and one reviewer reads each checkpoint's tickets together. Write `Gate: each` in `commands.md` for a review of every ticket.

Pick one with `/feature-flow <feature> careful` (or `standard`, `fast`), `FLOW_PROFILE=<name>` on `start`, or a `Profile:` line in the plan's `commands.md`, approved with the plan. A profile fills only settings you did not set: `FLOW_PROFILE=fast FLOW_SCOUTS=on` keeps the scouts. The log records `PROFILE-<NAME>` at the start. A level 3 or `Sensitive:` ticket keeps its own reviews in every profile.

The long `python3 -I -c ...` line the skill uses to call the conductor stays as it is: it is how the skill checks `flow-trust.py` against the sha256 it pins before running it, and a shorter wrapper would be one more file nothing checks. The session copies it from the skill; you never type it.

## Tickets side by side (lanes)

With `Lanes: auto` (or `2` to `4`) in the plan's `commands.md`, or `FLOW_LANES=2` (up to 4) on `start`, tickets that do not touch the same files are built at the same time, each with its own builder and reviewers in its own git worktree. Only the start and the end of a ticket change: the build, the gate, the floor guard and the reviews are the same as with one lane.

- **How many.** `Lanes: auto` takes the plan's width (`flow-status.py <feature> --width`), capped by the profile ([The guided flow](guided-flow.md)); `FLOW_LANES` overrides the line.
- **Plan.** Each ticket lists the paths it changes on a `Touches:` line (a folder ends with `/`, a `*` glob crosses folders). `commands.md` may name `Shared:` paths that many tickets change, and a `Setup:` command a fresh checkout needs. The plan reviewer checks the footprints; you approve them with the plan.
- **Schedule.** The conductor leases a ready ticket to a free lane only when its `Touches:` (read from the feature branch, never from a builder) does not overlap any running ticket's, it touches nothing on `Shared:`, and, when either ticket is level 3, the two keep to different top-level folders. A ticket with no `Touches:` line runs alone.
- **Lanes.** The lanes are worktrees in `.feature-flow/lanes/<feature>/` (git ignores the folder), created on first use, with `Setup:` run once in each. Each ticket gets a branch `ff/<feature>/<NN>` from the feature head.
- **Footprint check.** After every build, with or without lanes, a change to a path outside the ticket's `Touches:` sends the ticket back (`FOOTPRINT-FAIL` in the log).
- **Merge.** A ticket that passes its review is merged by the conductor, one at a time, in `.feature-flow/lanes/<feature>/integrate` with `git merge --no-ff`, so the reviewed commits land unchanged. The gate runs on the merge (Quick mid-plan, the full Test for the last ticket). Only a green merge fast-forwards the feature branch; then the ticket's branch is deleted with `git branch -d`. When two lanes both appended to `map.md`, `learnings.md` or `followups.md`, the conductor keeps both sides' lines; no agent ever resolves a conflict.
- **Rebuild.** Any other conflict, or a gate that fails on the merge, sends the ticket back to be built again from the feature branch as it is now, with what went wrong and its earlier commit in the ticket. A second collision stops the run for you: the plan's `Touches:` are likely wrong.
- **Level 3.** When another ticket merged after a level 3 ticket started, it is merged with the new feature head in its lane, gated, and given its quality review again before it merges.
- **The end.** After the last merge the lanes are removed. `reset` removes them too, with the ticket branches.

The session runs `prompt`, `next` and `verdict` with the lane from the `BUILD` or `REVIEW` line, and `next` answers `WAIT <lanes>` when every lane that can work is busy (see `## Lanes` in the skill).

## The fast path

`/feature-flow <feature> fast` trades per-ticket reviews for speed. The planner gets `Pace: fast` in the brief and writes a short plan of fewer, larger tickets, and the plan reviewer is skipped. With `FLOW_FAST=1` on `start`, a ticket below level 3 (one with no `Level:` line too) that passes the gate, the floor guard and its Done when checks passes at once (`REVIEW-DEFERRED` in the log). With `FLOW_GATE=off` nothing would check it, so every ticket keeps its review. A level 3 ticket, or one that touches a `Sensitive:` path, still gets its own reviews.

- **The feature review.** Once every ticket is resolved, `next` hands out `REVIEW <plan folder> all <sha>`: one fresh reviewer reads the deferred tickets as they were planned and the whole diff from the oldest deferred ticket's base to HEAD, with `guides/review-feature.md`. It has no lane, even when lanes run.
- **A failed feature review** becomes a new ticket, `NN-feature-review-fixes-<round>.md`, with the findings in it. A builder fixes it, and the feature is reviewed again. After `FLOW_MAX_REVIEW_ROUNDS` failed rounds the run stops for you.
- **Batches.** In fast mode one builder takes up to 5 ready tickets at once (`BATCH <n>` in the log), when each is level 1 or 2, has a `Touches:` line, and touches nothing another ticket of the batch or a `Sensitive:` path touches. The `BUILD` line names the first ticket and the prompt lists the rest. The builder finishes them one at a time, each with its own commits. The conductor then checks each ticket on its own commits: the gate once at the end (and, if it fails there, at each ticket's last commit, to find the first one that broke it), then the floor guard, the footprint, Done when and test first with HEAD at that ticket's last commit. A ticket that passes is deferred to the feature review like any other. One that fails, or that the builder never finished, goes back to open with its findings and is built alone (`BATCH-FAIL`), never in a batch again. That saves a builder and its context for every ticket but the first. A mistake in one ticket can still carry into the later ones of the batch, which is why only small, separate tickets are batched. Lanes, `FLOW_RELAY` and `FLOW_GATE=off` turn batches off, and so does `FLOW_BATCH=1` (`FLOW_BATCH=<n>` sets the size, at most 5).
- **Mid-run.** `fast on` and `fast off` (through the runner, like `next`) switch it between phases. Asking the session to go faster runs `fast on`. Asking again while fast is on offers the re-plan below. Tickets already passed without a review still get the feature review, whichever way it is switched.
- **The cost.** A mistake in an early ticket is found at the end, when later tickets may have built on it. Use it for small or low-risk features. `reset` keeps the list of deferred tickets, so they still get the feature review.

## When the gate runs (checkpoints)

A `Gate:` line in `commands.md` says when the expensive checks run. The cheap ones are scripts that take seconds, so they still run after every ticket and catch a cheating build at once. The full gate and the reviewer are what cost time and money, so they can wait for a few tickets.

| `Gate:` | After each ticket | At a checkpoint |
|---|---|---|
| `each` | the gate (Quick mid-plan), the floor guard, the footprint, Done when, test first, and the ticket's own review | nothing: there is none |
| `batch N` | `Quick` with Build and Lint (nothing when the plan has no `Quick:`), the floor guard, the footprint and test first; no review below level 3 | every N tickets and at the end: the full gate at HEAD, each ticket's Done when checks, then one reviewer reads the tickets' combined diff |
| `end` | as `batch N` | once, when every ticket is resolved |

The defaults come from the profile: `fast` is `end`, `standard` is `batch 3`, `careful` and `normal` are `each`. The plan-yes card shows the choice, and a line in `commands.md` overrides the profile. `Gate: off unsafe` and `FLOW_GATE=off` still turn the gate off, and then every ticket keeps its own review. A level 3 or `Sensitive:` ticket, or one with `Review: full`, keeps its own reviews at any setting.

- **A failure points at one ticket.** A failing Done when check reopens its own ticket. A red full gate is traced to the first ticket at whose last commit the gate fails, by halving the list of tickets since the last checkpoint, so 8 tickets take at most 3 more gate runs. Only that ticket is reopened, with the gate's output in it, and built again on top of the code as it is now; the others wait for the next checkpoint (`CHECKPOINT-FAIL` in the log). After `FLOW_MAX_REVIEW_ROUNDS` failed checkpoints in a row the run stops for you.
- **The review.** A passing checkpoint (`CHECKPOINT-PASS`) hands out the feature review (`REVIEW <plan folder> all <sha>`) for the tickets since the last checkpoint. Its reviewer is told the full gate and the Done when checks just passed at HEAD, and, before the end, that tickets not built yet are not part of it. A failed review becomes a fix ticket as in [the fast path](#the-fast-path), and the next checkpoint waits for that fix.
- **With lanes**, no new ticket is leased once a checkpoint is due: the busy lanes finish and merge, then the checkpoint runs. A merge runs `Quick` when the plan has one, and leaves the full gate to the checkpoint. **With fast batches**, the batch's own gate at the end runs only `Quick`.
- **The cost.** Between checkpoints a ticket can build on a mistake in the one before it that only the full Test would catch. That is why `batch 3` is the everyday default and `end` is for small, low-risk features.

## Who runs the full suite, and how long it takes

- **The conductor runs the whole Test command; the builder does not.** A builder runs the tests its change touches, the `Quick:` command and any `Check <path>:` command for a path it changed. The conductor's gate (or its checkpoint) then runs the whole Test command once, and the reviewer takes that result. A Done when bullet that only says the whole suite passes gets `left to the conductor's gate` in the builder's Proof. When the gate is off (`Gate: off unsafe`, `FLOW_GATE=off`), the build prompt says so and the builder runs the whole suite itself, once, at the end.
- **The gate says what it is doing.** Each command's output goes to `.feature-flow/state/gate-<feature>.log` (it ignores itself in git), which you can read while it runs. The gate names that log, prints a `gate: Test still running, 4m00s, output in …` line every minute on stderr, and ends with how long each command took (`gate: 2 command(s) passed in 3m10s (Test 3m02s, Lint 8s)`). The run log gets a `GATE-TIME Test=182 Lint=8` line per gate run, and `feature-flow eval` adds them up as `gate minutes by command`.
- **A slow Test command is often a serial one.** If your CI already splits the tests into shards, run those shards side by side in `commands.md`'s Test command too. feature-flow's own `tests/run.sh` does this with `python3 tests/shard.py all 4`.

## A time budget

`FLOW_BUDGET=<minutes>` on `start` gives the feature a budget of active minutes. The conductor counts the time between its steps, at most an hour for one step, so a session left open overnight does not eat the budget, and the time between two sessions does not count. `budget` (through the runner) reports it, and `budget <minutes>`, `budget +<minutes>` or `budget off` change it between phases.

- **Over the budget, fast mode first.** Before the next ticket starts, the conductor turns fast mode on by itself (`BUDGET-FAST` in the log).
- **Still over, a re-plan offer.** Once fast mode has finished a ticket and the run is still over (or at once, if fast mode was already on), the run stops once with the minutes spent, the tickets left, and an offer to re-plan. If one ticket took more than half the time over several attempts, the stop names it as stuck, since that is a stuck ticket, not a slow plan. `next` goes on as planned, and a new `budget` earns a new offer.
- **The re-plan needs your yes.** On your yes, between tickets, `replan-prompt` hands the `feature-planner` the open tickets with `guides/replan.md`. It folds them into fewer, larger tickets with the same bar: every Done when item and check moves into the ticket that takes over, folded tickets become `Status: parked (folded into NN)`, and resolved tickets stay as they are. The session shows you the change and commits it only on a second yes. The next `next` stops if the re-plan changed a resolved ticket. Nothing is ever cut without you.

## Long features and handoff

A session's context fills up, so the flow moves to a fresh session every few tickets. After `FLOW_TICKETS_PER_SESSION` tickets (default 4) pass review, `next` prints a `HANDOFF` line instead of the next ticket, for example `HANDOFF /feature-flow csv-export 3f9c0a1b2c3d4e5f.0a1b2c3d4e5f6a7b` (the last word is the runner's digest, which lets the new session check that the flow's files did not change in between). The session stops and tells you to open a new session and type that line. The new session picks up exactly where the last one stopped. Set `FLOW_TICKETS_PER_SESSION=0` to never hand off.

- **One owner at a time.** `start` gives the session a token, and every later call must carry it, so two sessions can never drive the same feature. `HANDOFF` and `DONE` release it.
- **Resuming after a closed session.** If a session ended without `HANDOFF` (you closed it, it crashed, it ran out of budget), the feature is still owned by it, and a new session stops and says so. Once you are sure the old session is gone, answer yes when the new session asks, or start it with `FLOW_TAKEOVER=1`. With `auto` the skill never takes over on its own.
- **Stuck on a ticket.** `python3 scripts/flow.py <feature> reset` (or `feature-flow reset <feature>`) reopens a ticket left `claimed` or `in-progress`, commits that, and clears the conductor's run state, so the next `/feature-flow <feature>` starts clean from the ticket files. `reset <NN>` reopens that one ticket, even a resolved one, to build it again. While a session owns the feature it needs `FLOW_TAKEOVER=1`. A mistyped command or feature name gets a `did you mean` hint.
- **A ticket that cannot be built as planned.** `replan-prompt <feature> repair` gives a planner the stopped ticket and the run so far; it rewrites the open tickets, the session commits, and `next` reopens the stopped ticket and goes on (`REPAIR` in the log). It refuses once the stopped ticket has code commits.
- **Long prompts.** `prompt <feature> file` writes the prompt to `.feature-flow/state/prompt-<feature>-<k>.md` and prints `PROMPT-FILE <path> <sha256>`, so the session hands a subagent a path, not the text.
- **Relay mode.** `FLOW_RELAY=1` hands off after every build and every review, so each phase gets a session of its own.
- **When an agent drives.** An orchestrating agent (another Claude session driving the skill for you) has no context to refresh, so handoffs are pure overhead. `/feature-flow <feature> agent` runs `start` with `FLOW_DRIVER=agent`: no `HANDOFF` unless `FLOW_TICKETS_PER_SESSION` is set by hand, builders skip the "continue in a fresh session" line (they leave it out whenever the flow runs them), and the eval records that an agent drove the run, so its stops, handoffs and resets are not read as your time. `next` runs the gate and the checks before it answers, which can take minutes: a caller with a 2 minute tool timeout should give it 10 minutes or more, or run it in the background.
- **Argument mistakes say what to do.** `verdict` without its file, `--after-build` in the wrong place (the runner now accepts it anywhere), a `next` after a REVIEW with no `verdict` in between (it used to hand out the same review again; now it changes nothing and says to run `verdict` first), a digest from another feature (the runner says to pass `FLOW_TRUST=new` on a feature's first call), and a commit made between a review and its `next` (the stop says how to take it out and make it again later).
- **Nobody needs to watch.** With `auto` the skill asks nothing, and a Claude Code cloud session keeps working while you are away. You only come back to type the `HANDOFF` line.

The state lives in `.feature-flow/state/` (the state, a log of every step, and the last review reply). That folder ignores itself, so it never shows up in `git status`, and a normal Codex session can write it, which it cannot do under `.git`.
