# Document the changes and bump the version to 0.2.0

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04, 05, 06, 07, 08
Test first: no

Only build this after PR #34 is merged and this branch has merged main. Update `README.md`: the `Floor:` categories line (the `skip` and `config` additions, `flow-edit` as an allow word for the conductor's code check), the settings table (`FLOW_GATE_TIMEOUT`), the Caution section (the gate and smoke test now time out after 30 minutes; the conductor checks that the code it runs did not change during a build and that this is a tripwire, not a sandbox; `Floor: allow flow-edit`; focused and skipped tests and more config files are flagged) and the line about the run limit. Update `guides/build.md` (and nothing else in the guides) so the builder knows: do not edit `feature_flow/`, `scripts/`, the guides or the roles unless the ticket says `Floor: allow flow-edit`; focused tests and skipped tests are findings. Set `__version__ = "0.2.0"` in `feature_flow/__init__.py`. Run `python3 install.py . --agent all --force` for the `.claude`/`.agents` copies only if `guides/build.md` is part of what the installer writes there (it writes guides into `.feature-flow/`, which must stay untracked in this repo).

## Not in this ticket

- Tagging `v0.2.0`: the user pushes the tag (cloud sessions cannot).
- Any change to the one-line protocol or the `REVIEW: PASS|FAIL` contract.

## Done when

- `python3 -c "import feature_flow; print(feature_flow.__version__)"` prints `0.2.0`.
- `grep -c "flow-edit" README.md guides/build.md` prints 1 or more for each file; `grep -c "FLOW_GATE_TIMEOUT" README.md` prints 1 or more.
- `python3 -m unittest discover -s tests/py && bash tests/run.sh` passes.

## Reference

- spec.md § Scope, § Design
- README.md (floor guard section, settings table, Caution), guides/build.md

## Answer

**Built**: README.md (Floor categories line with `flow-edit`, skip/config coverage and the assertion warning; `FLOW_GATE_TIMEOUT` row; run limit counted in phases; Caution: gate and smoke timeout, code tripwire and `Floor: allow flow-edit`; the mawk/gawk CI wording removed), guides/build.md (two bullets: no edits to flow code without `Floor: allow flow-edit`; focused and skipped tests are findings), feature_flow/__init__.py (0.2.0).

**Proof**: `python3 -c "import feature_flow; print(feature_flow.__version__)"` printed `0.2.0`. `grep -c flow-edit README.md guides/build.md` printed 2 and 1; `grep -c FLOW_GATE_TIMEOUT README.md` printed 2. `python3 -m unittest discover -s tests/py` ran 168 tests, OK; `bash tests/run.sh` 441 passed, 0 failed.

**Decisions**: did not run the installer: the `.claude`/`.agents` role copies do not contain guides/build.md text (grep found none), and guides go to untracked `.feature-flow/`. skills/ and adapters/ untouched.

**Shortcuts taken**: none.

**For later tickets**: the `v0.2.0` tag is pushed by the user. Ticket 10 runs the full bar.
