# Assessment: the advisor-style agent vs feature-flow

Notes written 2026-11-22, alongside the captured build prompt in
`12-build-your-own-advisor-prompt.md` (transcribed from photos of the original
"Walled Garden advisor" document).

## Does feature-flow have this sort of agent?

No. Checked against the live repo (2026-11-22). What feature-flow has is an
**ask mechanism** in the conductor (`feature_flow/conductor/phases/ask.py`):

- A builder's `## Ask: <role>` section or a reviewer's `REVIEW: ASK <role>`
  pauses the job; the conductor hands the question to a consultant role; the
  reply goes through `verdict`; the job continues with the answer.
- Questions for the user stop the run; a third consultant question on one
  ticket also stops it.

That is an in-run consultation between peer roles working from the repo and the
plan. It is not a walled-garden advisor: no curated corpus with authority
tiers, no generated index, no graded claims (Fact / Derivation / Assumption /
Cannot-answer), no citation-verification scripts, no ledger, no golden evals.
The closest roles are `flow-skeptic`, `plan-reviewer` and `ticket-reviewer` —
all inside the execution, none read-only or corpus-bound.

## Verdict on the design

Strengths:

- **Grades that change behaviour** is the best idea in it: Assumption and
  Cannot-answer become explicit human decisions instead of silent guesses.
- **Verify by script, not by banner** (§6): the caller refuses to ledger a
  reply until `verify_citations.py` passes. A control, not a ritual.
- Read-only advisor with separate, human-gated writers (curator/governor), one
  owner per fact, computed rosters, and repeat-run evals that treat
  nondeterminism as measurable.

Costs and limits:

- Heavy: a 262-line build prompt, three skills, four scripts, 30+ golden
  evals — before the first question is answered. Pays off only where the
  corpus is stable and authoritative and a wrong answer is expensive.
- The machinery verifies **provenance, not truth**: a stale corpus yields
  graded, citation-checked wrong answers.
- The constants (150-line skill budget, 30 eval questions, three repeat runs)
  are admitted starting guesses in the document's own notes.
- The human-gated curator is a bottleneck: the advisor's knowledge ages at the
  speed of the slowest approval.

## Where the pattern already lives in this stack

- **codeintel** is the advisor pattern for code: read-only, one query over the
  graph/LSP/semantic engines, evidence envelopes (`resolved` vs `name-matched`,
  `safe_for_destructive`), never-raise.
- **sky-brain** is the corpus-governance half: typed knowledge, agents propose,
  humans approve, decisions end only when superseded.
- **feature-flow** is the execution arm. Its "corpus" — a living codebase plus
  a plan that exists to be changed — violates the advisor's first precondition
  (a stable authoritative body), so bolting a walled garden into it would
  duplicate codeintel's and sky-brain's jobs.

## The one piece worth stealing

Put **grades on the existing ask path**. When a consultant answers a builder
mid-ticket, an answer that is really an Assumption should not be silently built
on — it should escalate to the user, the same way questions for the user
already stop the run. Small change; it is the highest-value idea in the
document.
