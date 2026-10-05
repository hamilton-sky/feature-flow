# Add a Codex CLI capability preflight

Type: task
Status: open
Blocked by: 01
Test first: yes

Add a preflight used by `scripts/auto-flow.sh` before any Codex session starts. It builds on the completed prerequisite and runtime contract established by ticket 01. Confirm the `codex` executable exists and that `codex exec --help` advertises every flag the loop will use: sandbox selection, output-last-message, JSON events, model selection and structured output when that path is enabled. Check `jq` only for the features that require it. Report all missing capabilities together and exit before the smoke command or model invocation.

Test capabilities rather than comparing a hard-coded version. Cache the result for one loop run so every ticket does not spawn another help command. Continue to accept `FLOW_CODEX_ARGS`, but do not treat custom arguments as proof that a required built-in flag exists.

## Not in this ticket

- Changing review output, sandbox modes or model selection.
- Downloading or upgrading Codex automatically.

## Done when

- With the fake Codex exposing all required help flags, `FLOW_AGENT=codex bash scripts/auto-flow.sh f` reaches the first session and the fake log shows one help probe for the whole run.
- When one or several required flags are absent, the loop exits nonzero before smoke or a model session and prints every missing flag in one diagnostic.
- A missing `codex` executable retains the existing actionable error, and a Claude run never calls `codex --help`.
- Structured-output capability is required only when the structured path is selected; the documented fallback can pass without it.
- `bash tests/run.sh` exits 0 with a preflight section covering success, aggregation, caching and no-session-on-failure.

## Reference

- spec.md § Interfaces, Edge cases
- runtime and prerequisite contract from ticket 01
- `scripts/auto-flow.sh` initialization and `run_codex`
- `tests/run.sh` fake Codex command and missing-executable cases
- current `codex exec --help` output recorded during planning

## Answer
