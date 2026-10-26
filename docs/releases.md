# Releases

What each version added, newest first. The [README](../README.md) describes how each part works today. Versions with a tag are on [PyPI](https://pypi.org/project/feature-flow-cli/) as `feature-flow-cli`; the others were merged to `main` and first published in the next tagged version.

Upgrade between features, not in the middle of a run (see [Upgrading](../README.md#upgrading)).

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
