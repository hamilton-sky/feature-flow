# Files are the truth, the page is a view

[← README](../README.md) · [Docs index](README.md)

feature-flow keeps every decision in files, in git. The guided flow's page and the brainstorm's review page (Forkboard) only show those files and collect your picks. They are never a second place where the plan lives. This page sets out that contract. A change to the page that breaks it is a bug.

## Where each thing lives

| What | The file that holds it |
|---|---|
| The brainstorm: its type, scouts and team, the options, the pick | `.feature-flow/state/brainstorm-<feature>.md` (git ignored), copied into `plans/<feature>/brainstorm.md` when the plan is accepted |
| The plan: spec, tickets, levels, `Touches:`, Done when | `plans/<feature>/spec.md`, `plans/<feature>/tasks/*.md` |
| The build setup: commands, profile, lanes, gate, checks | `plans/<feature>/commands.md` |
| What the roles decided during the run, and why | `plans/<feature>/decisions.md` |
| What the run left for later | `plans/<feature>/followups.md` |
| Traps the builders found | `plans/<feature>/learnings.md` |
| What the run did, step by step | `.feature-flow/state/flow-<feature>.log`, read by `feature-flow report` and `eval` |
| The run's record and your verdict | `plans/<feature>/eval.json`, `eval-verdict.md` |

## The rules

1. **The page is made from the files.** `flow-status.py <feature> --page` (or `--live`) builds it fresh each time. Throw it away and build it again, and nothing is lost but what the next rule names.
2. **The page writes only its own `state.json`.** On a live page, your picks, your Approve, your saved diagram versions and your questions go into the page's `state.json`. Nothing on the page can write a repository file.
3. **Only the session writes the files, through named commands.** `--page --picks` writes the Style and Team picks into the brainstorm's header (`Type:`, `Scouts:`, `Helpers:`) and the Plan tab's picks into the draft's `commands.md` and tickets. `--apply` writes a diagram version into the brainstorm, and refuses if the brainstorm changed since the page was built. `--answer` answers a question on the page. Each says what it wrote.
4. **What is not written is not decided.** A pick you never approved, a diagram edited on the plain (not live) page, which lives only in your browser, and a question nobody answered are not in the files. The session works from the files.
5. **One yes freezes the plan.** Approving the Plan tab (or saying yes in the chat) is the plan's yes. After it, nothing on the page can change the plan or the build setup. Only a re-plan, with your own yes, can.
6. **Reality is read, never written.** The Build tab's Plan vs reality table and `feature-flow report` are made from the tickets and the run's log (`CHANGED`, `FOOTPRINT-*`, `LEVEL-*`, `DECISION`, `FOLLOWUPS`, `REPLAN`, `REPAIR`). They show what happened and decide nothing.
7. **The page is optional.** On Codex, or with no Artifact tool, the same stops happen in the chat with a plain HTML page beside the brainstorm. The files, and what gets written, are the same.

## Plan vs reality

After each build, the footprint check logs the paths the build changed (`CHANGED [...]`). For each ticket, `feature-flow report <feature>` and the Build tab put these side by side:

- **Planned:** the ticket's `Touches:` line and its level, as you approved them.
- **Changed:** what the ticket's last build changed (the plan folder left out).
- **Differences:** paths changed outside `Touches:`, planned paths left untouched, a build sent back for leaving `Touches:`, an extra file the builder named, a level raised during review, rebuilds, questions a role decided (in `decisions.md`), findings left for later (in `followups.md`).
- **The plan itself:** how many times it was re-planned or repaired during the run.

This shows paths and decisions, not intent. It cannot say whether a change inside `Touches:` did what the ticket meant. That is the reviewer's job, and the Done when checks'.
