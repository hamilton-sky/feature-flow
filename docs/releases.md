# Releases

What each version added, newest first. The [README](../README.md) describes how each part works today. Versions with a tag are on [PyPI](https://pypi.org/project/feature-flow-cli/) as `feature-flow-cli`; the others were merged to `main` and first published in the next tagged version.

Upgrade between features, not in the middle of a run (see [Upgrading](../README.md#upgrading)).

## 0.30: the standard profile

| Version | Added |
|---|---|
| 0.30.0 | **`standard`, the profile a new plan names** ([README](../README.md#profiles)): slower than `fast`, faster than `careful`. Where one review would run, a quality reviewer and a ticket reviewer read the ticket side by side, both read only (`REVIEW ... pair`, `FLOW_REVIEWERS=2`); on a level 1 or 2 ticket only a blocker sends it back to its builder, and smaller findings go to `followups.md` for later tickets. One reviewer reads the whole round at the end (`FLOW_ROUND_REVIEW=on`). The gate runs once at the base before the first ticket, so a red base stops the run instead of failing a builder (`FLOW_BASE_GATE=on`). With an `Acceptance:` line the tests run after each ticket and their output goes to the reviewers. **Questions stay with the roles**: a question for you goes to the product owner first, the architect, designer and product owner decide what the spec leaves open, and every answer and its reason is kept in `plans/<feature>/decisions.md`. **A repair re-plan** (`replan-prompt <feature> repair`) rewrites the open tickets when one cannot be built as planned, and the run goes on. **Run fixes** from two field runs: fast batches honour `Shared:`, a builder's question in a batch is routed, a Done when check that is the gate's own command is not run twice, the test-first proof tries `Quick` first, one declared `Extra file:` outside `Touches:` is allowed, `install` refuses while a run is open, `reset` keeps the tester's work, `prompt <feature> file` writes long prompts to a file, and `eval` records where the time went (`timing`, `--compare`). Plans written before 0.30.0 keep their old behaviour. |

## 0.29: debugging before fixing

| Version | Added |
|---|---|
| 0.29.1 | The debugging guide now also comes with a rebuild after an attempt that left the ticket unresolved, not only after a send-back. |
| 0.29.0 | **A fuller debugging guide.** The guide a builder gets after a send-back now also has it look at its own diff first, compare with similar code that works, rerun a flaky test to see how often it fails and wait on a condition instead of a fixed time, read the last Attempt note so it does not repeat a failed fix, and write a failing test for the cause before a logic fix. An Attempt note now lists each hypothesis tried and what it showed. When each fix moves the failure somewhere else, the builder asks the architect instead of patching a third time. The build guide's own failure handling asks for the cause first too. |

## 0.28: arranging and styling the review page

| Version | Added |
|---|---|
| 0.28.0 | **Forkboard 0.2.0.** An **Arrange** button on each diagram lays the boxes out left to right, top to bottom, radial (the most joined box in the middle) or as a grid; it is an edit like any other, so Undo puts the boxes back and a saved version keeps it. Four new styles beside `route` and `blueprint`: `sketch` (hand drawn, for early ideas), `paper` (editorial, prints cleanly), `terminal` (for infra and dev tools) and `bright` (for UI and consumer features). A style can now shape the boxes too: corners, line weight, shadow, font. `forkboard themes` says what each style suits, and the brainstorm guide has the agent pick the style from the subject unless you name one, and colour boxes by role (people, screens, services, data, outside systems, risk). |

## 0.27: codeintel for the agents

| Version | Added |
|---|---|
| 0.27.0 | **codeintel, optional** ([README](../README.md#codeintel-optional)): when [codeintel](https://github.com/hamilton-sky/codeintel) is installed and has the repository indexed, scouts are told to ask it who calls what and where code lives, and reviewers to ask it which callers the change left behind (`--op changed`). Each ends its reply with a line per question saying whether the answer helped, and `eval` counts them; the verdict form asks whether codeintel helped. `pip install "feature-flow-cli[codeintel]"` installs both; `FLOW_CODEINTEL=off` leaves it out. Nothing changes without it. |

## 0.25: reviewing the brainstorm together

| Version | Added |
|---|---|
| 0.26.0 | **Forkboard**: the review page is now its own package, [packages/forkboard/](../packages/forkboard/) (Forkboard 0.1.0), with its own tests, browser tests in CI and its own PyPI build. feature-flow turns the brainstorm into a review document (`bundle/1`) and Forkboard renders it; `brainstorm-page`, its flags and the pages it writes are unchanged. The page's script and CSS are now real files instead of Python strings. Every install carries Forkboard inside the package. Styles moved from `guides/styles/` to Forkboard's themes. A walkthrough of the brainstorm and the page: [docs/brainstorm.md](brainstorm.md). |
| 0.25.0 | **Live brainstorm page** (Claude only; `brainstorm-page <feature> --live <folder>`, published as an artifact that saves itself). Everyone it is shared with can save their own version of each diagram, switch between the original and anyone's version, and **compare with original** (added, removed and renamed boxes and arrows marked). **Ask Claude** in the page redraws a diagram with that person's own Claude. **Talk to Claude** sends the session questions; the session answers on the page (`--asks`, `--answer`) and can put a version into the brainstorm (`--apply`). **Sketch first** (`/feature-flow <feature> brainstorm sketch`): you draw the idea, and the options build on it. |

## 0.24: seeing the brainstorm

| Version | Added |
|---|---|
| 0.24.0 | **Brainstorm review page** (`feature-flow brainstorm-page <feature>`): one HTML file with a section sidebar, a light or dark switch, and flowchart diagrams you can edit (drag, add boxes of seven kinds, 12 colours, rename, connect, delete, undo and redo) and copy back as mermaid. **Lenses**: a read only `flow-lens` helper looks at the options as `positive`, `researcher`, `open-minded`, `artistic`, `ux` or `security`, limited per profile. **Styles**: `route` and `blueprint` token files in `guides/styles/`, picked by `--style`, a `Style:` line or `FLOW_STYLE`. |

## 0.19 to 0.23: from the first field run

A field run on a separate application repo (two features) found 7 issues in review, all real, and listed the friction. These releases answer it.

| Version | Added |
|---|---|
| 0.23.0 | **Acceptance tests.** With an `Acceptance:` line in `commands.md`, a `flow-tester` writes acceptance tests from `spec.md` before the first ticket. Builders cannot change them (`acceptance-edit`), they run once every ticket is resolved, and a failure becomes a fix ticket. A builder can dispute a test with the product owner, who rules `TEST WRONG` or `CODE WRONG`. **One review at level 3**: the spec checklist and the quality review with the hostile caller probe in one pass, since the 19 separate spec reviews of the field run caught nothing. `Review: full` keeps two passes. |
| 0.22.0 | **Brainstorm** before the brief (`/feature-flow <feature> brainstorm`): up to three questions, two or three options with diagrams, pros, cons, size and risky areas, a recommendation, and `brainstorm.md` in the plan. Six read only helpers, including `flow-skeptic`, who attacks each option. |
| 0.21.0 | **Batches in fast mode.** One builder takes up to 5 small (level 1 or 2), disjoint tickets; the conductor still checks each ticket at its own last commit, and a failing one is built alone. `FLOW_BATCH=1` turns it off. |
| 0.20.0 | **Agent-driven runs** (`agent`, `FLOW_DRIVER=agent`): no handoffs, and the eval records who drove. **`followups.md`** collects the minor findings of passing reviews and the majors a level 2 ticket passed with. **`needs <what>`** on a Done when check defers it when the host cannot run it. Argument mistakes say what to do, and a `next` without a `verdict` changes nothing. |
| 0.19.0 | **Read only reviewers.** A `PreToolUse` hook blocks file-changing shell commands for reviewers, consultants and scouts in Claude Code. Everywhere, the conductor undoes a reviewer's edit, saves it as a patch and hands the review to a fresh reviewer; a second edit or a commit stops the run. |

## 0.15 to 0.18: measuring and adopting

| Version | Added |
|---|---|
| 0.18.0 | **Import** a Spec Kit feature folder or an OpenSpec change (`feature-flow import`): one ticket per phase or section, user story phases side by side. |
| 0.17.0 | **Profiles**: `careful`, `normal`, `fast` set several `FLOW_` settings at once, from the command, `FLOW_PROFILE` or a `Profile:` line. |
| 0.16.0 | **Claude Code plugin**: this repo is its own marketplace (`/plugin install feature-flow@feature-flow`). |
| 0.15.0 | **Eval**: `feature-flow eval` writes `eval.json` (cost, tokens, every catch by the check that made it, where the run needed you) and a verdict form; `--later` finds the fixes that came after. |

## 0.9 to 0.14: review effort and speed

| Version | Added |
|---|---|
| 0.14.0 | **Time budget** (`FLOW_BUDGET`): over budget, fast mode turns on by itself; still over, the run offers a re-plan, which needs your yes. |
| 0.13.0 | **Questions** go to `flow-architect`, `flow-designer` or `flow-po` agents instead of being guessed; what changes the feature still comes to you. |
| 0.12.0 | **Scouts**: cheap read only Haiku helpers (`flow-scout`, `flow-web`) read ahead for the planner, builder and reviewer. `FLOW_SCOUTS=off` turns them off. |
| 0.11.0 | **Fast path**: tickets below level 3 skip their own review until one feature review at the end; `fast on` and `fast off` mid-run. |
| 0.10.0 | **Lanes** (`FLOW_LANES=2` to `4`): tickets with disjoint `Touches:` built side by side in worktrees, merged one at a time by the conductor. A conflict rebuilds the ticket; no agent resolves it. The footprint check sends back a build outside its `Touches:`. |
| 0.9.0 | **Ticket levels**: 1 light, 2 standard, 3 boundary decide the reviews and the rework rounds. The conductor can raise a level from what it measures, never lower it. |

## Before 0.9

| Version | Added |
|---|---|
| 0.8.0 | Run report, plan lint, the `trivial-assert` guard, the mode matrix tests. |
| 0.7.0 | The optional `Quick:` gate command. |
| 0.6.0 | One combined review for small tickets. |
| 0.5.0 | Trusted checks: every conductor call goes through the hash-pinned `flow-trust.py`. |
| 0.4.0 | `install --user`, once for every repo. |
| 0.3.x | `feature-flow uninstall`; Done when checks, the test-first proof, the debugging guide on a send-back, and two review passes. |
| 0.2.0 | Guard hardening: a tripwire for builder edits to the flow's own code. |
| 0.1.x | The one-skill interactive flow in Python, the planner and plan reviewer, the PyPI package, `--private`, `reset`. |
