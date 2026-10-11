# Document the single review and bump to 0.6.0

Type: task
Floor: allow flow-edit
Status: open
Blocked by: 04
Test first: no

In `README.md`:

- The flow diagram that shows "spec review" then "quality review": add that a small ticket whose check block passed gets one combined review instead, and name the rule (3 files and 60 changed lines at most, plan folder left out, measured by the conductor; `Review: full`, `Type: convert`, no check block or `FLOW_GATE=off` keep both).
- "What the script checks and what it trusts": replace "A ticket moves on only after two PASS verdicts" with: after two PASS verdicts, or one for a ticket the conductor judged small. Say the size is measured from the repo, never taken from the builder.
- The settings table: add `FLOW_SMALL_FILES` (`3`) and `FLOW_SMALL_LINES` (`60`, `0` turns the single review off).
- The sentence on the run limit that counts the spec and quality reviews as one phase each: a single review counts as one.
- The planner section: mention `Review: full` and that tiny changes are folded into the ticket they belong to.

In `adapters/codex/feature-flow/SKILL.md`, the `REVIEW` bullet: `<pass>` is `spec`, `quality` or `single` by the pass the prompt names (`(spec pass)`, `(quality pass)` or `(single pass)`). In `skills/feature-flow/SKILL.md`, the "Say what will happen" line: a fresh reviewer subagent for each review pass, one or two per ticket. Check the skill tests (`tests/py/test_skills.py`, `tests/py/test_skill_trust.py`) still pass; if a skill's pinned runner hash or wording test needs refreshing, refresh it.

Set `__version__ = "0.6.0"` in `feature_flow/__init__.py`, and update the `--version` expectation in `tests/run.sh` (it expects `feature-flow 0.5.0`) and any other test that names the version.

## Not in this ticket

- Release notes or tags: the user tags releases.
- The planner guides: ticket 05.

## Done when

- `python3 -c "import feature_flow; print(feature_flow.__version__)"` prints `0.6.0`.
- `README.md` contains `FLOW_SMALL_LINES` and `Review: full`; `adapters/codex/feature-flow/SKILL.md` contains `(single pass)`.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ python3 -c "import feature_flow; print(feature_flow.__version__)"
prints 0.6.0
$ grep -c "FLOW_SMALL_LINES" README.md
exit 0
$ grep -c "Review: full" README.md
exit 0
$ grep -n "(single pass)" adapters/codex/feature-flow/SKILL.md
prints (single pass)
```

## Reference

- spec.md § Goal and the bar, § Interfaces
- `README.md`, `adapters/codex/feature-flow/SKILL.md`, `skills/feature-flow/SKILL.md`, `feature_flow/__init__.py`

## Answer
