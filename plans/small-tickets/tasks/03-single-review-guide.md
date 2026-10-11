# Write the single review guide and give it a prompt phase

Type: task
Floor: allow flow-edit
Status: open
Blocked by: —
Test first: yes

Add `guides/review-single.md`, one reviewer doing the spec and quality passes together for a small ticket. Start from `guides/review.md` and keep its sections word for word where they apply: who you are, the fresh-session rule, "What you may read" (ticket at base, the range ending at the ticket's own last commit, the diff with the ticket folder held back, never the Answer) and "What you must not do". Then one verdict section, in this order:

1. **Scope** over `<base>..$END`, as in review.md.
2. **Done when**: for each bullet, if the conductor's notes say its check block passed, write `MET (conductor)` without re-running it; run the prose-only bullets yourself.
3. **Test first: yes**: does the diff add or change a test, and would it fail without the production change.
4. **Quality**: the list from `guides/review-quality.md` (boundary bugs, weakened checks, code that need not exist, what a later ticket will trip over), rated blocker, major or minor.

Output shape: a `SPEC` block (bullets, scope, test first) then a `QUALITY` block, then the verdict line, with the same rules as review.md for the last line. `PASS` only if every Done when bullet is MET, scope is OK, test first is not MISSING, and there is no blocker or major finding.

Wire it in: in `feature_flow/prompts.py` add the phase `review-single` to `ROLES` (`ticket-reviewer.md`) and `GUIDES` (`review-single.md`), and make the task line say `(single pass)` for it (today it says `quality` or `spec`). Add `review-single` to the phases `feature_flow/codehash.py`'s `_files` loops over, and `review-single.md` to `GUIDES` in `scripts/flow-trust.py`. Adding to `GUIDES` changes `scripts/flow-trust.py`, whose LF sha256 both skills pin in their loader lines: update the pinned hash in `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md`, and in this repo's tracked own-install copies (`.claude/skills/feature-flow/SKILL.md`, `.agents/skills/feature-flow/SKILL.md`), so `tests/py/test_skill_trust.py` and `tests/py/test_own_install.py` pass. Refresh the own-install copy of the guides too if `test_own_install.py` needs it.

Tests in `tests/py/test_prompts.py`: `prompts.build("review-single", ...)` contains `(single pass)`, the scope section and the quality list, and ends its task with the `REVIEW: PASS` or `REVIEW: FAIL` instruction; `codehash.flow_code` changes when `guides/review-single.md` changes.

## Not in this ticket

- The conductor handing out this phase: ticket 04.
- The Codex skill's reviewer task names: ticket 06.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_prompts.py"` prints `OK`, with a test that the `review-single` prompt contains `(single pass)`.
- `grep -c "REVIEW: PASS" guides/review-single.md` prints a number above 0, and `grep -n "review-single.md" scripts/flow-trust.py` finds the GUIDES line.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_prompts.py"
prints OK
$ grep -n "review-single.md" scripts/flow-trust.py
prints review-single.md
$ grep -c "REVIEW: PASS" guides/review-single.md
exit 0
```

## Reference

- spec.md § Decisions (what the single pass covers)
- `guides/review.md`, `guides/review-quality.md`, `feature_flow/prompts.py` (`build`), `feature_flow/codehash.py` (`_files`), `scripts/flow-trust.py` (`GUIDES`)

## Answer
