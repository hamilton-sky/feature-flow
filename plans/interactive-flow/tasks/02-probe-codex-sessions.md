# Find out whether Codex can start subagents, and what each runtime says about its context

Type: settle
Status: resolved
Blocked by: —
Test first: no

The Codex skill has two possible shapes: drive subagents like Claude Code, or relay mode, where every phase is its own session. Decide which by trying it in an interactive Codex session, locally and, if available, in Codex cloud. The user and the worker do this together.

Known starting evidence (2026-10-06): the Codex desktop session used to revise this plan exposes a subagent API that starts an agent with a separate context and returns its final reply to the parent. Do not generalize that observation to every installed or cloud Codex surface; use the probe below to verify the exact environment the skill will run in.

Prepare a throwaway project with `FLOW_AGENT=codex bash tests/smoke-real.sh --prepare DIR` and open Codex in DIR:

1. **Subagents.** Can the session start a separate agent with its own instructions and a fresh context, and get its final reply back as text? Record the tool or API used, not only that it exists. Try the builder role (`.agents/flow-roles/ticket-builder.md` plus the `next-phase` skill text, for `hello auto`) and then the reviewer role. Check independence the same way as the Claude probe: a made-up word the parent knows and the child must not.
2. **Read-only review.** If subagents work, can the child be limited to reading (no file edits)? If not, how does a fresh session get started read-only (for example `codex --sandbox read-only`)?
3. **Context usage.** Can a session in Codex, and in Claude Code, read how full its own context is (a command, a status value, a tool)? Record how, or `no`.

Put these lines in the Answer exactly, one per line:

```
Codex subagents work: yes|no
Codex read-only child: yes|no
Codex context usage readable: yes|no
Claude context usage readable: yes|no
Codex mode: subagents|relay
```

Then, under For later tickets: the exact wording that started a Codex subagent (if any), and the command a user types to start a read-only Codex session.

## Not in this ticket

- The Codex skill itself: it comes later and copies what this one finds.
- Claude Code subagents: ticket 01.

## Done when

- `grep -cE '^(Codex subagents work|Codex read-only child|Codex context usage readable|Claude context usage readable): (yes|no)$' plans/interactive-flow/tasks/02-probe-codex-sessions.md` prints `4`.
- `grep -cE '^Codex mode: (subagents|relay)$' plans/interactive-flow/tasks/02-probe-codex-sessions.md` prints `1`.
- For later tickets names the commands or wording that worked, so a stranger can repeat them.

## Reference

- spec.md § Design, Decisions (handoff trigger, relay mode)
- install.sh (`install_codex`) and README.md § Trying Codex interactively
- tests/smoke-real.sh, the `--prepare` mode

## Answer

Codex subagents work: yes
Codex read-only child: no
Codex context usage readable: yes
Claude context usage readable: yes
Codex mode: subagents

The local Codex desktop/runtime exposes `spawn_agent`, `wait_agent` and the
other collaboration calls. A child started with a fresh context returned
`KNOWS: no` when asked whether it knew a word given only to the parent, so the
contexts are independent. The builder child read the installed role and skill,
resolved demo ticket 01, ran both Done-when commands and committed it as
`963ded23022f140496a8f8ee289a64ac2a3a968d`. A second fresh reviewer child ran
the review and returned a reply ending in `REVIEW: FAIL`, proving that the
verdict text reaches the parent. Its complaint was about the demo change's
scope, not a failure of the reply path, and `git status --short` remained empty.

`spawn_agent` has no sandbox, permission or tool-list argument. Children share
the tools configured for the parent request, so this surface cannot enforce a
read-only child. Instruction-only read-only behavior is possible, and the
conductor can still detect a dirty tree, but a hard boundary needs a fresh
Codex session. A direct probe with `codex exec --sandbox read-only` tried
`touch readonly-child-probe.txt` and got `Operation not permitted`.

Codex CLI 0.147.0 displays `100% context left` in the interactive footer; an
`exec` session also prints its token total when it exits. Claude Code 2.1.291
has `/context`, described by the installed runtime as a visualization of used
tokens, free space and their percentages. These are runtime UI values rather
than values the model has to estimate.

### For later tickets

Exact child API and builder wording that worked:

```
spawn_agent(task_name="ticket_builder", fork_turns="none", message="Work only in <repo>. First read <repo>/.agents/flow-roles/ticket-builder.md and follow it. Then read <repo>/.agents/skills/next-phase/SKILL.md and follow it for `<feature> auto`, ticket <NN>. Run every Done-when command, resolve the ticket, and commit as instructed. Return a concise final report including the commit SHA.")
```

Exact reviewer wording that returned a verdict:

```
spawn_agent(task_name="ticket_reviewer", fork_turns="none", message="Work only in <repo>. Read <repo>/.agents/flow-roles/ticket-reviewer.md and follow it. Then read <repo>/.agents/skills/review-ticket/SKILL.md and follow it for feature `<feature>`, ticket `<NN>`, start commit `<sha>`. Do not edit any files or create commits. Your final reply must end with exactly `REVIEW: PASS` or `REVIEW: FAIL`.")
```

The parent gets either final reply through `wait_agent`. Keep
`fork_turns="none"` so the reviewer does not inherit the builder's context.
Because the child API cannot enforce read-only access, rely on the reviewer's
instructions plus the conductor's dirty-tree/HEAD checks, or start a hard
read-only reviewer as a fresh session:

```
{ cat .agents/flow-roles/ticket-reviewer.md; echo; echo '$review-ticket <feature> <NN> <sha>'; } | codex exec --sandbox read-only -
```

For a general interactive read-only session, a user can type:

```
codex --sandbox read-only -C <repo>
```

Read context fullness from Codex's `context left` footer. In Claude Code, run
`/context` (or `/context all` for the expanded breakdown).
