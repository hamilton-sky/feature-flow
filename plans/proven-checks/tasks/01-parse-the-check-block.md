# Parse the check block in a ticket's Done when

Type: task
Status: open
Blocked by: —
Test first: yes

Create `feature_flow/proof.py` with `class ParseError(ValueError)`, a small `Check` record (`command`, `exit`, `prints`) and `checks_in(text)`, which returns the checks of every ```` ```check ```` fenced block inside the `## Done when` section of a ticket's text (from the `## Done when` line up to the next line starting with `## `), in order. Grammar, from spec.md § Design (Check block): blank lines and `#` lines are ignored; `$ <command>` starts a check; `exit <N>` (whole number) or `exit nonzero` sets the expected exit code (default 0); `prints <text>` adds a substring the output must contain (several allowed). Any other line, an `exit`/`prints` line before the first `$`, a second `exit` for one command, or a fence that is never closed raises `ParseError` whose message quotes the line. Fences outside Done when, and fences with another tag (` ```bash `), are ignored. Text with `\r\n` line endings reads the same as `\n`. No block at all returns `[]`.

Pure text in, records out: no git, no subprocess. Put the tests in a new `tests/py/test_proof.py`.

## Not in this ticket

- Running the checks or calling them from the conductor: ticket 02.
- Validating check blocks in `flow-status.py --check`: left out of this plan (spec.md § Decisions).

## Done when

- `python3 -m unittest discover -s tests/py -k proof` passes, with a test for each grammar rule above: default exit 0, `exit 3`, `exit nonzero`, two `prints` lines, a comment and a blank line, a block outside Done when ignored, a ` ```bash ` block ignored, CRLF text, and one `ParseError` test each for an unknown line, `exit x`, `prints` before `$`, and an unclosed fence.
- `python3 -c "from feature_flow import proof; print(proof.checks_in('# T\n\n## Done when\n\n- x\n\n## Answer\n'))"` prints `[]`.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Design (Check block), § Interfaces
- feature_flow/tickets.py (`records` for line handling), feature_flow/floorguard.py (`allow_line`, a similar reader of ticket text)

## Answer

