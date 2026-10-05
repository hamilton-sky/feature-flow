# Map: portable-runtime-skills

## Destination

Feature Flow has one canonical definition for each skill, a runtime-support declaration, and thin renderers that install correct Claude and Codex packages. The completed `in-session-mode` work remains intact: `drive-flow` is Claude-only and `flow-step.sh` keeps its text verdict contract. The Codex headless loop checks capabilities, normalizes structured reviews, uses disposable writable review worktrees and refuses suspicious commits. A build script produces a validated portable plugin containing only Codex-supported skills.

**The bar.** `bash tests/run.sh` exits 0, reports no failed checks, validates both generated installations and the portable plugin, and exercises every new Codex safety path offline. The last ticket runs it.

## How to work this

- External prerequisite: finish `plans/in-session-mode` first. Confirm `bash scripts/flow-status.sh in-session-mode --next` exits 10 before claiming any ticket. Ticket 01 is the gate for every branch of this graph.
- See what is ready: `bash scripts/flow-status.sh portable-runtime-skills`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `bash scripts/flow-status.sh portable-runtime-skills --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.

## Decisions so far

<One line per resolved ticket: `NN — the decision or finding, in a sentence`.>

## Open questions

- Which high-risk untracked filename patterns need a documented override after the first implementation tests expose legitimate cases.
- Whether the portable plugin artifact should become a release attachment, a marketplace entry, or both; this plan builds and validates it but does not publish it.
- Whether real-agent activation evaluations should later run on a schedule; this plan keeps them opt-in.
