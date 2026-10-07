# Feature planner — Spec

## Problem

Planning is the one phase of feature-flow without its own agent. When `/feature-flow <feature>` finds no plan, the user's own session follows `guides/plan.md` inline: it asks, researches the codebase and writes the files itself. Three things follow from that:

- A conversation does not become a feature. Typing `/feature-flow` with no name after talking a feature through lists `plans/*/` and asks which one.
- The planner has no role of its own. The builder and reviewer have role files, tool lists and rules that never bend; planning has a guide read by whatever session is open, and its research and drafting fill the user's chat.
- Research stops at the codebase. A feature that uses a library or an outside API is planned from memory, with no source for what it assumes.

## Goal and the bar

After a conversation, `/feature-flow` (or `$feature-flow` on Codex) turns what was said into a plan in two approvals. First the session shows a short **feature brief** it wrote from the conversation and waits for yes, edit or cancel. Then a fresh **feature-planner** subagent, fed only by the approved brief, researches and writes a draft plan into the git-ignored state folder; a fresh, read-only **plan-reviewer** checks the draft against the brief; the session shows the plan and waits for a second yes. Only then does the conductor copy the draft into `plans/<feature>/`.

The bar: `bash tests/run.sh` passes, including a fixture drive that runs `plan-prompt`, writes a draft as a planner would, runs `plan-review-prompt` and `plan-accept`, and then `start` prints `OK <token>`; and a hand run in Claude Code (ticket 08) turns a short conversation into a plan that passes `flow-status --check`.

## Scope

In: the two role files, the planning guides, three conductor commands (`plan-prompt`, `plan-review-prompt`, `plan-accept`), the Plan section of both skills, the README, tests.

Not in scope:
- Building tickets. Everything from `start` with a plan present stays as it is.
- Adding tickets to an existing plan. That stays a hand edit following `guides/plan.md`'s ticket rules; `plan-accept` refuses an existing plan folder.
- A Codex hand run. There are no Codex tokens; the Codex skill ships unverified by hand, like `plans/interactive-flow` ticket 13.

## Design

```
conversation ... user types /feature-flow  (no name, or a new one)
  1. session writes the feature brief from the conversation     guides/brief.md
     APPROVAL 1: yes / edit / cancel
     brief saved to .feature-flow/state/brief-<feature>.md
  2. flow.py <feature> plan-prompt <brief>     -> feature-planner subagent
     planner writes .feature-flow/state/draft/<feature>/, ends PLAN: READY | PLAN: QUESTIONS
  3. flow.py <feature> plan-review-prompt      -> plan-reviewer subagent (read only)
     ends PLAN-REVIEW: PASS | PLAN-REVIEW: FAIL
     FAIL: one more planner round, plan-prompt <brief> <findings>
  4. APPROVAL 2: goal, bar, commands, graph, dropped list, open questions, review result
  5. flow.py <feature> plan-accept             -> copies the draft to plans/<feature>/, runs --check
  6. suggest the commit, as today
```

### Decisions

- **A fresh planner fed by the brief, not a planner in the user's session.** Another design kept the planner in the user's own session so it sees the whole conversation, with research subagents and a plan-reviewer around it. We chose the fresh planner because (a) only a separate agent can have a role file with a thinking strategy and a tool list, which is what the user asked for, the same as the builder and reviewer; (b) the research and drafting stay out of the user's chat context; (c) everything the plan relies on is in the brief, which is saved into `spec.md`, so a plan never depends on something said only in chat. The cost is that nuance left out of the brief is lost; approval 1 is where the user catches that. The plan-reviewer is taken from the other design.
- **The draft lives in `.feature-flow/state/draft/<feature>/`.** The state folder already ignores itself, so a draft never dirties the tree, and `plan-accept` is the only way into `plans/`. "Write nothing until yes" is enforced by the conductor, not only asked of the agent. That also contains the planner on Codex, where a child agent's tools cannot be limited.
- **The conductor keeps no planning state.** The three commands are stateless: they read the brief, the draft and the plan folder. A crashed plan is restarted by running `plan-prompt` again, which clears the old draft.
- **Approvals belong to the session, never to a subagent.** The planner cannot talk to the user; anything it cannot decide comes back as `PLAN: QUESTIONS`, and the session asks.
- **`auto` skips both approvals**, as it skips the yes before building today. With no conversation and no brief to write, the session asks `guides/plan.md`'s Step 1 questions and writes the brief from the answers.
- **Outside research is cited.** The planner looks outside the repo only where the code cannot answer (a library's docs for the version in the lockfile, an outside API), and every outside fact gets a source line in `map.md`. A runtime without web access says so in the planner's reply and plans from the codebase.

## Migration and compatibility

Existing plans and the build loop are untouched. `/feature-flow <feature>` with a plan present behaves as today. Without a plan it now goes through the brief and the planner instead of planning inline. The installer already copies every `agents/*.md`, so the two new roles install with no installer change.

## Risks

- A subagent's reply can arrive before it finishes (the build loop already handles this); the skill waits for the final reply the same way.
- A weak brief makes a weak plan. The brief's format forces a bar and an Unsure line, and the plan-reviewer checks the draft against the brief.
