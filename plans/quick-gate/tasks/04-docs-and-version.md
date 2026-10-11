# Document the quick gate and bump to 0.7.0

Type: task
Floor: allow flow-edit
Status: open
Blocked by: 02, 03
Test first: no

In `README.md`: where the gate is described, say that the gate runs Build, Test and Lint after every ticket, and that with an optional `Quick:` line in `commands.md` it runs Build, Quick and Lint after the tickets in the middle of a plan, and the full Build, Test and Lint after the last ticket, before a handoff, and under `FLOW_GATE_FULL=1`; a plan without `Quick:` runs the full gate every time. Add `FLOW_GATE_FULL` to the settings table. Say that the test-first proof still runs the full `Test` command. Update `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md` and their two tracked own-install copies (`.claude/skills/feature-flow/SKILL.md`, `.agents/skills/feature-flow/SKILL.md`) only if they describe the gate; keep each pair identical, and if you change a skill, check `tests/py/test_skill_trust.py` still passes.

Set `__version__ = "0.7.0"` in `feature_flow/__init__.py`, and update the `--version` expectation in `tests/run.sh` (it expects `feature-flow 0.6.0`) and any other test that names the version.

## Not in this ticket

- Release notes or tags: the user tags releases.

## Done when

- `python3 -c "import feature_flow; print(feature_flow.__version__)"` prints `0.7.0`.
- `README.md` contains `FLOW_GATE_FULL` and `Quick:`.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ python3 -c "import feature_flow; print(feature_flow.__version__)"
prints 0.7.0
$ grep -c "FLOW_GATE_FULL" README.md
exit 0
$ grep -c "Quick:" README.md
exit 0
```

## Reference

- spec.md § Goal and the bar, § Interfaces
- `README.md`, `feature_flow/__init__.py`, `tests/run.sh`

## Answer
