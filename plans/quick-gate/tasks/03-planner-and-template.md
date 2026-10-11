# Teach the planner to write Quick: and the plan reviewer to check it

Type: task
Floor: allow flow-edit
Status: open
Blocked by: —
Test first: no

- `guides/templates/commands.md`: add a `Quick:` line after `Test:` — `<optional: the fast subset of Test, run after the tickets in the middle of the plan; Test runs after the last ticket and before each handoff>` — and one sentence in the intro saying so.
- `guides/plan.md` Step 2 (the part that finds the real commands): the planner picks `Quick:` only when the project's own config has a clearly faster subset (a unit-only target, a fast marker or folder). It must be a strict subset of `Test`, must exit non zero on failure, and must run without asking anything. Otherwise leave it out: no `Quick:` means the full Test every time. Say that the planner never invents one.
- `guides/plan-review.md` check 4: if `commands.md` has `Quick:`, run it and report that it exits 0, that it is part of what `Test` runs, and whether it covers the areas the tickets touch.

Refresh this repo's installed copy of the guides if `tests/py/test_own_install.py` needs it.

## Not in this ticket

- The conductor reading `Quick:`: tickets 01 and 02.
- README and version: ticket 04.

## Done when

- `guides/templates/commands.md` contains `Quick:`; `guides/plan.md` contains `Quick:` and `strict subset`; `guides/plan-review.md` contains `Quick:`.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ grep -q "Quick:" guides/templates/commands.md
exit 0
$ grep -q "Quick:" guides/plan.md
exit 0
$ grep -q "strict subset" guides/plan.md
exit 0
$ grep -q "Quick:" guides/plan-review.md
exit 0
```

## Reference

- spec.md § Decisions (who writes Quick)
- `guides/templates/commands.md`, `guides/plan.md`, `guides/plan-review.md`

## Answer
