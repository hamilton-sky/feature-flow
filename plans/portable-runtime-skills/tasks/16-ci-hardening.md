# Harden CI

Type: task
Status: open
Blocked by: 10, 11
Test first: no
Floor: allow config

Extend `.github/workflows/tests.yml` to run the offline suite, shell syntax checks, ShellCheck when available, both AWK variants, package validation (`scripts/package-plugin.sh --check`) and generated-output parity. No CI job may call a model, require credentials or publish an artifact.

## Not in this ticket

- A paid real-agent CI job, public release workflow or marketplace publication.
- New checks in `tests/run.sh`; this ticket only wires existing ones into CI.

## Done when

- CI runs syntax, offline tests, parity and `scripts/package-plugin.sh --check` on its existing operating-system/AWK matrix.
- ShellCheck findings fail only for checked shell files, with each exclusion documented in the workflow or a config file beside it.
- `grep -cE 'claude -p|codex exec|secrets\.' .github/workflows/tests.yml` prints `0`.
- `bash tests/run.sh` and `bash scripts/package-plugin.sh --check` both exit 0 locally, with no network or credentials.

## Reference

- `.github/workflows/tests.yml`
- the packager from ticket 10 and the documentation checks from ticket 11
- the parity command from ticket 05

## Answer
