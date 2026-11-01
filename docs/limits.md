# Limits and safety

[← README](../README.md) · [Docs index](README.md)

What feature-flow's checks can and cannot stop, and what is protected during a run.

## Limits

feature-flow's layers are tripwires, not a security boundary. They catch accidents and lazy shortcuts by an agent; a determined agent that controls the session could still get around them.

- **The verdict relay is trusted.** The session saves a reviewer's reply and hands it to `flow.py verdict`. The conductor reads `REVIEW: PASS` or `REVIEW: FAIL` from that file and cannot prove the session passed it on unedited.
- **The floor guard reads diffs with patterns.** It does not see a test made trivially true by other means (a mock that returns the expected answer, an `assert` on something that is always set, a test that no longer exercises the code), or an assertion weakened without being deleted. It does catch assertions that cannot fail (`trivial-assert`) and warns the reviewer when a test file loses assertions. A new test with no assertion at all is not caught. The red-first proof only covers tickets with `Test first: yes`.
- **A plan can be wrong and still pass.** The plan lint checks that every ticket has a way to be proven and that `commands.md` has a Test command. It cannot tell whether the plan builds the right thing; the second yes is yours.
- **The trust runner stops accidents, not the session.** It catches a builder editing the conductor mid-run. The session that runs it is the thing it cannot check; a hand-run `flow-trust.py` is unprotected (see above).
- **Some paths are newer than the field runs.** The Codex skill and the Codex planner have not been run by hand, the plugin install and the brainstorm have not had a real run, and the Quick gate has only been run by tests. See [docs/field-run.md](field-run.md) for how to try it on your own repo and what to send back.
- **One ticket at a time**, with a handoff to a new session every few tickets, unless you turn on lanes.
- **Lanes share one disk.** A builder in one lane can still write into another lane's folder or the main worktree. The conductor sees that as a dirty tree and stops, but only afterwards. Overlap of `Touches:` is judged from the patterns, so two tickets that could never meet may still run one after the other.

## Caution

The builder subagent has edit and shell access and commits after each ticket. Each ticket costs at least two subagents. Build on a branch you can throw away. Ignore build output in `.gitignore`, because the conductor stops if the tree is dirty after a ticket. The gate and the smoke test stop after 30 minutes (`FLOW_GATE_TIMEOUT`). The session runs every conductor call through `scripts/flow-trust.py`, which sits beside the conductor it runs (`scripts/` in the repo, or `~/.feature-flow/scripts/` for a `--user` install). The skill pins the runner's sha256 and starts it with a one-line loader that checks and runs those same bytes, so a subagent cannot change the check. The runner prints `TRUST <code>.<state>` before the conductor's output, and the session passes that digest to the next call as `FLOW_TRUST`.

**Protected:** edits by the builder, reviewer or planner subagents during a session to feature-flow's own files (its `feature_flow` package, its files in `scripts/` (`flow.py`, `flow-status.py`, `gate.py`, `floor-guard.py`, `flow-view.py`, `flow-trust.py`), the guides, the roles and the skill folders, in the repo and in the install folders) and to the run state in `.feature-flow/state/`. That includes edits made by code the conductor runs during a step, such as tests, `check` commands and git hooks. Any of these makes the runner print a `STOP` instead of `TRUST`, naming the changed files where it can, and the session stops. It also holds between sessions when the `HANDOFF` line carries its digest (`HANDOFF /feature-flow <feature> <digest>`). `Floor: allow flow-edit` on a ticket allows its build to change the flow's code (never the run state, and never `scripts/flow-trust.py`, whose hash the skill pins: change the runner outside the flow, or build it with a conductor from another install, then update the pinned sha in both skills); the runner then prints `FLOW-EDIT <files>`, and a session run without `auto` tells you which flow files changed.

**Not protected:** a subagent that changes `python3` on PATH or the system Python, the agent itself, or anything outside the repo and the install folders. The session's very first conductor call: whatever is on disk then is trusted. A background process left running by a step's own commands: it can swap a flow file in the instant between the runner's check and the conductor loading it, then put it back. A session that stops passing its digest, or a resume from a `HANDOFF` line without one (the session warns). The conductor's own code check (`STOP flow code changed while building <ticket>: <files>`) stays as a second line that catches accidental edits; on its own it cannot stop deliberate tampering.

The floor guard is pattern matching: it can miss things and it can raise false alarms, and `Floor: allow` is the release valve. The run stops on its own when a ticket stays unresolved, when the smoke test or the gate keeps failing, when a ticket keeps failing review, or when it reaches its phase limit.
