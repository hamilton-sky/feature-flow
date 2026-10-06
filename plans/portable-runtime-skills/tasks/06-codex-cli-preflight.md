# Add a Codex CLI capability preflight

Type: task
Status: open
Blocked by: —
Test first: yes

Add a preflight used by `scripts/auto-flow.sh` before any Codex session starts. It needs nothing from the rest of this plan or from the in-session plan.

First record the real `codex exec --help` and `codex --version` output in `references.md` (its "Codex CLI" entry), with the date, from an installed Codex. If Codex is not installed where you work, stop and say so: the flag names must come from the real CLI, not from memory. Then confirm the `codex` executable exists and that `codex exec --help` advertises every flag the loop will use: sandbox selection, output-last-message, JSON events, model selection and structured output when that path is enabled. Check `jq` only for the features that require it. Report all missing capabilities together and exit before the smoke command or model invocation.

Extend the fake `codex` in `tests/run.sh` so it answers `codex exec --help` with a help text the test controls (today it treats `exec --help` as a session), and log each help probe. Test capabilities rather than comparing a hard-coded version. Cache the result for one loop run so every ticket does not spawn another help command. Continue to accept `FLOW_CODEX_ARGS`, but do not treat custom arguments as proof that a required built-in flag exists.

## Not in this ticket

- Changing review output, sandbox modes or model selection.
- Downloading or upgrading Codex automatically.

## Done when

- With the fake Codex exposing all required help flags, `FLOW_AGENT=codex bash scripts/auto-flow.sh f` reaches the first session and the fake log shows one help probe for the whole run.
- When one or several required flags are absent, the loop exits nonzero before smoke or a model session and prints every missing flag in one diagnostic.
- A missing `codex` executable retains the existing actionable error, and a Claude run never calls `codex --help`.
- Structured-output capability is required only when the structured path is selected; the documented fallback can pass without it.
- The "Codex CLI" entry of `references.md` holds real help output and a date, with no `<` placeholder line left.
- `bash tests/run.sh` exits 0 with a preflight section covering success, aggregation, caching and no-session-on-failure.

## Reference

- spec.md § Interfaces, Edge cases
- `scripts/auto-flow.sh` initialization and `run_codex`
- `tests/run.sh` fake Codex command and missing-executable cases
- `references.md`, the "Codex CLI" entry, which this ticket fills in

## Answer
