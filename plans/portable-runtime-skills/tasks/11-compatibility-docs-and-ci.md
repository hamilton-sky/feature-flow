# Document compatibility and harden CI

Type: task
Status: open
Blocked by: 05, 06, 10
Test first: no
Floor: allow config

Update `README.md` with the one-source architecture, supported-runtime matrix, adapter output paths, portable plugin build/install flow, Codex preflight behavior, review isolation, structured/text fallback and commit-safety override. Keep the completed same-session documentation accurate: `drive-flow` remains Claude-only, while `run-flow` remains the headless multi-session path for both agents.

Replace fixed prose such as a hard-coded number of checks with wording that cannot drift. Qualify sandbox, network and `.git` behavior as tested-environment behavior rather than a universal Codex guarantee. Record the current compatibility baseline without promising future CLI flags.

Extend `.github/workflows/tests.yml` to run the offline suite, shell syntax checks, ShellCheck when available, both AWK variants, package validation and generated-output parity. No CI job may call a model, require credentials or publish an artifact. Add focused documentation checks for broken local links, obsolete invocation syntax and mismatches between the runtime matrix and the compatibility table.

## Not in this ticket

- A paid real-agent CI job, public release workflow or marketplace publication.
- New workflow behavior beyond documenting and validating what earlier tickets built.

## Done when

- README commands for Claude, Codex, same-session mode, unattended mode and plugin packaging match the generated files and pass their offline smoke commands.
- No README sentence hard-codes the total test count; the compatibility matrix names runtime, install path, invocation form, review mode and tested status.
- CI runs syntax, offline tests, parity and `scripts/package-plugin.sh --check` on its existing operating-system/AWK matrix, and ShellCheck findings fail only for checked shell files with documented exclusions.
- A documentation test fails fixtures containing a broken local link, a common skill assigned to the wrong runtime or obsolete slash/dollar syntax.
- `bash tests/run.sh` and `bash scripts/package-plugin.sh --check` both exit 0 with no network or credentials.

## Reference

- spec.md § Migration and compatibility
- parity/evaluation outputs from ticket 05
- preflight diagnostics from ticket 06
- plugin packager from ticket 10
- `README.md`, `.github/workflows/tests.yml`
- completed `plans/in-session-mode/spec.md` and `skills/drive-flow/SKILL.md`

## Answer
