# Find out whether Codex can start subagents, and what each runtime says about its context

Type: settle
Status: open
Blocked by: —
Test first: no

The Codex skill has two possible shapes: drive subagents like Claude Code, or relay mode, where every phase is its own session. Decide which by trying it in an interactive Codex session, locally and, if available, in Codex cloud. The user and the worker do this together.

Prepare a throwaway project with `FLOW_AGENT=codex bash tests/smoke-real.sh --prepare DIR` and open Codex in DIR:

1. **Subagents.** Can the session start a separate agent with its own instructions and a fresh context, and get its final reply back as text? Try the builder role (`.agents/flow-roles/ticket-builder.md` plus the `next-phase` skill text, for `hello auto`) and then the reviewer role. Check independence the same way as the Claude probe: a made-up word the parent knows and the child must not.
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
