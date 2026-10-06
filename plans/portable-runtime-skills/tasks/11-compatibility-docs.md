# Document compatibility

Type: task
Status: open
Blocked by: 05, 06, 07, 08, 09, 10
Test first: no

Update `README.md` with the one-source architecture, supported-runtime matrix, adapter output paths, portable plugin build/install flow, Codex preflight behavior, review isolation, structured/text fallback and commit-safety override, and say that the commit-safety check covers only the Codex loop. Keep the completed same-session documentation accurate: `drive-flow` remains Claude-only, while `run-flow` remains the headless multi-session path for both agents.

Replace fixed prose such as a hard-coded number of checks with wording that cannot drift. Qualify sandbox, network and `.git` behavior as tested-environment behavior rather than a universal Codex guarantee. Record the current compatibility baseline without promising future CLI flags.

Add focused documentation checks to `tests/run.sh` for broken local links, obsolete invocation syntax and mismatches between the runtime matrix and the compatibility table.

## Not in this ticket

- Changes to `.github/workflows/tests.yml`: ticket 16.
- A paid real-agent CI job, public release workflow or marketplace publication.
- New workflow behavior beyond documenting and validating what earlier tickets built.

## Done when

- README commands for Claude, Codex, same-session mode, unattended mode and plugin packaging match the generated files and pass their offline smoke commands.
- No README sentence hard-codes the total test count; the compatibility matrix names runtime, install path, invocation form, review mode and tested status.
- A documentation test fails fixtures containing a broken local link, a common skill assigned to the wrong runtime or obsolete slash/dollar syntax.
- `bash tests/run.sh` and `bash scripts/package-plugin.sh --check` both exit 0 with no network or credentials.

## Reference

- spec.md § Migration and compatibility
- parity outputs from ticket 05
- preflight diagnostics from ticket 06
- plugin packager from ticket 10
- `README.md`
- completed `plans/in-session-mode/spec.md` and `skills/drive-flow/SKILL.md`

## Answer
