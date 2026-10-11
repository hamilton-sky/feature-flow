# Teach the planner to fold tiny changes and when to set `Review: full`

Type: task
Floor: allow flow-edit
Status: open
Blocked by: —
Test first: no

In `guides/plan.md` under "Ticket rules":

- Add a rule after rule 1: **A change too small to stand alone is folded in.** A rename, a doc line, a config value or a one-line fix that has no Done when of its own goes into the ticket whose work it belongs to, not a ticket of its own. Every ticket costs a builder, the gate and at least one reviewer, whatever its size.
- Add a rule after rule 8: **Set `Review: full`** on a ticket that is small but risky (validation at a trust boundary, security, the flow's own code, data that could be lost). Leave it out otherwise: the conductor gives a small ticket whose check block passed one combined review, and a larger one the spec and quality passes. `Type: convert` always gets both.
- Add `Review:` to the list of header lines the plan check validates in Step 5.

In `guides/plan-review.md` check 7, add: no ticket is so small it should have been folded into another (name it and the ticket it belongs with).

In `guides/templates/ticket.md`, add `Review: auto` after the `Test first:` line.

Refresh this repo's installed copy of the guides if `tests/py/test_own_install.py` needs it.

## Not in this ticket

- The conductor reading `Review:`: tickets 02 and 04.
- The README: ticket 06.

## Done when

- `guides/plan.md` contains `Review: full` and `folded`; `guides/plan-review.md` contains `folded`; `guides/templates/ticket.md` contains `Review: auto`.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ grep -c "Review: full" guides/plan.md
exit 0
$ grep -c "folded" guides/plan.md
exit 0
$ grep -c "folded" guides/plan-review.md
exit 0
$ grep -n "Review: auto" guides/templates/ticket.md
prints Review: auto
```

## Reference

- spec.md § Decisions (fewer tiny tickets is guide text only)
- `guides/plan.md`, `guides/plan-review.md`, `guides/templates/ticket.md`

## Answer
