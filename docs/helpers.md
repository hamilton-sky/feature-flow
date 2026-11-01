# Scouts and helper agents

[← README](../README.md) · [Docs index](README.md)

The agents that help the planner, builders and reviewers: scouts that read ahead, the optional codeintel tool, the architect, designer and product owner who answer questions, and the tester who writes acceptance tests.

## Scouts

Before a planner, builder or reviewer starts, the session can spawn cheap helpers that read ahead for it: `flow-scout` (read only, codebase) and `flow-web` (web only, for the planner). Both run on Haiku in Claude Code (`model: haiku` in their role files); in Codex the skill picks the lightest model `spawn_agent` allows. A scout looks at the code the way its role would (`ROLE: builder` looks for patterns and helpers to reuse, `ROLE: reviewer` for the rules the change must follow) and never decides anything.

| Before | Scouts |
|---|---|
| planning (`plan-scouts <brief>`) | one codebase scout and one web scout |
| a level 1 ticket | none |
| a build below level 3 (first attempt) | one builder scout on the ticket and its `Touches:` |
| a level 3 build (first attempt) | two builder scouts: the code it changes, and what depends on it |
| a level 3 ticket's first review | one reviewer scout on the conventions the diff must follow |
| the feature review (fast path) | one reviewer scout |

`scouts [lane]` lists `SCOUT <k> <agent> <reply file>` lines (or `NONE`) and clears the last ones' replies; `scout-prompt <k> [lane]` prints one scout's prompt. The session saves each reply into its file, and the phase's `prompt` adds them under `## Scout findings (unverified)`, cut to 60 lines each. A reply saved for one phase never reaches another. Retries and later rounds get no scouts. `FLOW_SCOUTS=off` turns them off. After a brainstorm, its `Scouts:` levels apply here too: `off` lists none of that kind, `light` only the first, and `deep` code scouts ask before a build as for a ticket one level higher ([Brainstorm types](brainstorm.md#brainstorm-before-planning)).

## codeintel (optional)

[codeintel](https://github.com/hamilton-sky/codeintel) is a separate code-intelligence tool: one command answers who calls a function, what a change would break, or where the code that does something lives, from a call graph, a language server and semantic search. feature-flow never needs it. When it is installed and has the repository indexed, two roles get a short `## codeintel` section in their prompt:

- **Scouts** (`flow-scout`, not `flow-web`) are told to ask it `callers`, `impact` or `search` where grep would take several tries.
- **Reviewers** (every ticket review and the feature review) are told to run `codeintel query --op changed --target <base>`, which lists each function the change removed, re-signed or rewrote with the callers it did not update.

Each of them ends its reply with one line per question, `codeintel: <op> <target>: helped | no answer | wrong: <why>`, and is told to check an answer before relying on it and to fall back to grep. `eval` counts the queries and those lines, and the verdict form asks whether codeintel helped, made no difference or misled the run, with a line for an answer it got wrong: material for a codeintel issue.

To set it up: `pip install "feature-flow-cli[codeintel]"` (or `pip install codecortex`), then `codeintel setup --all .` in the repository. feature-flow asks `codeintel doctor --json` which engines are ready and keeps the answer for an hour in `.feature-flow/state/codeintel.json`; with nothing ready, or no `codeintel` on PATH, the prompts are as before. `FLOW_CODEINTEL=off` leaves it out. In a lane, the agents run it in the lane's worktree, where codeintel may not have an index, and then fall back to grep. The two tools are released on their own and neither imports the other.

## Questions for the architect, designer or product owner

A builder, reviewer or planner that hits a question it should not decide alone asks it instead of guessing, and the flow pauses that job until the right role answers.

- **Who answers.** `flow-architect` answers technical design questions, `flow-designer` answers UI and UX questions, and `flow-po` answers what the feature must do where the spec is silent. Each is a fresh, read only agent that sees the plan, the ticket as it was planned and the code, never the asker's reasoning or a ticket's Answer. Each gets one scout with its own lens first.
- **A builder** appends `## Ask: architect|designer|po` with the question to its ticket and stops. `next` hands out `ASK <role> <ticket> <NN> <sha>`. The answer goes into the ticket under `## Consulted (<role>)`, and the ticket is built again. The question does not count as a failed attempt.
- **A reviewer** ends with a `## Question` and `REVIEW: ASK <role>`. The answer comes back in the next review's notes. On the fast path's feature review, the reviewer writes the question as a finding, and the fix ticket's builder can ask it.
- **The planner** starts each open question with `architect:`, `designer:`, `po:` or `user:`. The session runs `consult-prompt <role> <question file>` for the first three, adds the answers to the brief under `Consulted:`, kept apart from your `Decided:` lines, and plans again.
- **A question for you goes to the product owner first.** A builder's or reviewer's question marked `user` is sent to `flow-po` once per ticket. The architect, designer and product owner decide what the spec leaves open; only scope, cost and steps outside the repo come to you.
- **`plans/<feature>/decisions.md`** keeps every answer: the ticket, who asked, which role answered, the question, the answer and the role's `## Why`, committed with the ticket (`DECISION` in the log).
- **What still comes to you.** Any question the product owner sends on with `ANSWER: USER`, any answer a consultant ends with `ANSWER: USER` (it changes what you get, so its options come to you), and a third consultant question on one ticket all stop the run with the question, written into the ticket under `## Ask: user`. You answer under `## Consulted (user)` at the end of the ticket, commit, and run `next`. A reviewer's question for you reopens the ticket, so its builder builds again with your answer.

## Acceptance tests (the tester)

A builder writes its own tests, so they tend to check what it built rather than what was asked. With an `Acceptance:` line in `commands.md` (the planner writes one for any feature a test can reach from outside), a separate tester writes the feature's acceptance tests before any of it is built, from the product owner's words alone.

- **Before the first ticket**, `next` hands out `TEST <plan folder> <sha>`. A fresh `flow-tester` reads `spec.md` (its bar, stories and acceptance criteria, edge cases and interfaces), `map.md`, `commands.md` and the existing code's conventions, never the tickets, and commits tests under `plans/<feature>/acceptance/` that only the `Acceptance:` command runs. The conductor then checks its work: the commits change nothing outside that folder, the gate still passes with the tests in place, and the tests fail now, since nothing is built yet (`TEST-WRITTEN` in the log). Otherwise a fresh tester gets the job again, with a note saying what was wrong. It has no lane, even when lanes run.
- **Builders cannot change them.** The tests sit inside the plan folder, so the floor guard fails any builder's change there (`acceptance-edit`), and no `Floor:` line allows it. A builder may run them to see where the feature stands.
- **Once every ticket is resolved**, the conductor runs the `Acceptance:` command itself (`ACCEPT-PASS` or `ACCEPT-FAIL`). A failure becomes a new ticket, `NN-acceptance-fixes-<round>.md`, with the failing output in it, built and reviewed like any other; then the tests run again. After `FLOW_MAX_REVIEW_ROUNDS` failed rounds the run stops for you. With the fast path, the tests run before the feature review.
- **A disputed test.** The tester can be wrong too, most often where the spec is vague. A fix ticket's builder that is sure a test asks for something `spec.md` does not say asks the product owner with `## Ask: po`. `flow-po` rules from `spec.md` alone with `RULING: TEST WRONG` or `RULING: CODE WRONG` (`RULING-TEST` or `RULING-CODE` in the log). The builder leaves a test ruled wrong failing and finishes the rest; once the ticket is resolved, a tester changes exactly the tests ruled wrong, as the rulings say, and the tests run again. The usual limit on questions holds, so a third one goes to you.
- **No `Acceptance:` line, no tester**: a plan written before 0.23.0 runs as before.
