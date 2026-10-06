# Normalize structured Codex review results

Type: task
Status: open
Blocked by: 06
Test first: yes

Before changing anything, check the prerequisite: `test -f scripts/flow-step.sh && grep -c '^Status: resolved' plans/in-session-mode/tasks/03-*.md` must print `1`. The in-session conductor mirrors `review()`, so this ticket changes `review()` only after that mirror exists. Otherwise leave this ticket open and stop.

If the "Codex CLI" entry of `references.md` shows no structured-output flag, build only the mode setting and the text path, say so in the Answer, and leave the structured path for a later ticket.

Add a checked-in JSON Schema for Codex review results with a `PASS` or `FAIL` verdict, Done-when check results, scope and test-first results, and severity-rated findings. When the preflight finds structured-output support and `jq` is available, run Codex reviewers with that schema, validate the last message, and render the existing short review report ending in the exact `REVIEW: PASS` or `REVIEW: FAIL` line.

Keep the current text review protocol as a supported fallback when structured output is unavailable or explicitly disabled. Malformed structured output is not silently treated as text: retry it under the existing retry limit, then stop with the validation error. Builder sessions remain unstructured. The `review-ticket` skill tells the reviewer to end with a text verdict line, which a JSON schema contradicts, so in structured mode the loop adds a short Codex-only prompt fragment, kept in `adapters/codex/`, telling the reviewer to answer with the schema's object instead of the text report. `flow-step.sh` and the interactive reviewer continue to exchange the existing text contract.

Add one setting that reports which review mode is active and allows the user to select automatic, structured or text behavior. Automatic prefers structured only when both the CLI capability and parser exist.

## Not in this ticket

- Changing pass/fail policy, finding severity rules or the interactive conductor interface.
- Changing where the reviewer runs; isolation is the next change to the headless review path.

## Done when

- `test -f scripts/flow-step.sh` succeeds.
- In structured mode the reviewer prompt contains the fragment, and in text mode it does not.
- A fake structured PASS and FAIL each validate against the schema and normalize to the existing report shape with the correct final verdict line.
- Missing required fields, an unknown verdict, malformed JSON and a schema violation each retry and then stop with a diagnostic that names the invalid field or parse failure.
- Automatic mode selects structured only when preflight support and `jq` are present; forced text mode sends no output-schema flag and preserves the current behavior.
- Tests prove builder sessions use no schema and `flow-step.sh` text verdict fixtures still pass unchanged.
- `bash tests/run.sh` exits 0 with no real Codex invocation.

## Reference

- spec.md § Review contract decision, Interfaces
- Codex preflight from ticket 06
- `scripts/auto-flow.sh` (`run_codex`, `review`)
- `skills/review-ticket/SKILL.md`
- `scripts/flow-step.sh` from the completed prerequisite plan (read only unless a shared normalization test requires a fixture)

## Answer
