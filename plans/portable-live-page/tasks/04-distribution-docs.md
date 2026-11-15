# Ship the adapters and document both agent workflows

Type: task
Status: open
Blocked by: 03
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: packages/forkboard/README.md, README.md, docs/guided-flow.md, docs/source-of-truth.md, docs/brainstorm.md, guides/brainstorm.md, guides/plan.md, guides/build.md, skills/feature-flow/SKILL.md, adapters/codex/feature-flow/SKILL.md, packages/forkboard/tests/package_smoke.py, tests/package_smoke.py, tests/py/test_profiles.py

Document the implemented commands from spec.md Interfaces in Forkboard and FeatureFlow entrypoints. Preserve native Claude publishing instructions, add Codex local launch and request polling/reply/graph-proposal/apply/picks examples, describe localhost lifetime/restart and explicit agent checking (no promised wakeup), connection recovery and staged picks, tab Approve as user approval intent, agent processing of named commands, frozen accepted plans, and why HTTP never executes builds/commits. Include setup/options, draft planning, active/completed build and no-brainstorm launch examples. Keep the same URL throughout one server session and document that a restart with port 0 prints a new URL.

Extend both existing package smoke programs to assert the adapter and backend module/assets ship and run installed local render/serve/request operations from an unrelated temporary working directory. Existing assets/* globs should suffice; do not change package or test-runner configuration. Add focused doc-contract assertions in test_profiles.py for current CLI examples and approval wording. The manual Codex smoke recipe must save a diagram, cause a stale revision, queue/check/answer a question, preview a graph proposal, process a draft pick and observe ticket-status refresh; mark real-agent execution as manual, with no account/model in automated checks.

## Not in this ticket

- Changes to conductor prompts outside page guidance or automatic chat wakeups are outside this feature; live behavior was implemented before this documentation/package slice.

## Done when

- Both distributions include the new modules and embedded adapter assets, and their existing smoke programs exercise installed local commands from outside a checkout.
- `python3 -m unittest discover -s tests/py -p "test_profiles.py" -v` prints `OK`, including documentation contracts.
- Documentation provides a complete copyable manual Codex smoke sequence and retains native Claude and static fallback instructions.

```check
$ python3 -m unittest discover -s tests/py -p "test_profiles.py" -v
exit 0
prints OK
```

## Reference

- spec.md (read-only)
- pyproject.toml (read-only)
- packages/forkboard/pyproject.toml (read-only)
- tests/package_smoke.py (read-only)
- packages/forkboard/tests/package_smoke.py (read-only)

## Answer
