# Parse the check block in a ticket's Done when

Type: task
Status: resolved
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


Work started at d891c5db57f13126f987b3dbdbe5d10228cf368f.

**Built**

- `feature_flow/proof.py` (new): `ParseError(ValueError)`, `Check` (frozen dataclass: `command`, `exit` int or `"nonzero"`, `prints` tuple), `checks_in(text)`.
- `tests/py/test_proof.py` (new): 17 tests, written first and seen failing with `ImportError: cannot import name 'proof'`.

**Proof**

- `python3 -m unittest discover -s tests/py -k proof`: `Ran 17 tests ... OK`, exit 0. One test per rule: default exit 0, `exit 3`, `exit nonzero`, two `prints`, comment and blank line, block outside Done when ignored, ` ```bash ` block ignored, CRLF, and `ParseError` for an unknown line, `exit x`, `prints` before `$`, an unclosed fence (before a `## ` heading and at end of text). Extra: several blocks in order, `exit` before `$`, a second `exit`, no block returns `[]`.
- `python3 -c "from feature_flow import proof; print(proof.checks_in('# T\n\n## Done when\n\n- x\n\n## Answer\n'))"` printed `[]`, exit 0.
- `python3 -m unittest discover -s tests/py && bash tests/run.sh`: `Ran 186 tests ... OK`, then `441 passed, 0 failed`, exit 0.

**Decisions**

- `Check` is a `dataclasses.dataclass(frozen=True)`, not a `namedtuple`: `tests/run.sh` has a standard-library allowlist for `feature_flow` imports ("the conductor imports only the standard library") that lists `dataclasses` but not `collections`. My first version used `namedtuple` and failed that check.
- `prints` is a tuple (immutable record). Text after `prints ` is kept as written; the `$ ` command is stripped.
- Fences: any line starting with ```` ``` ```` opens a fence inside Done when; only a line exactly ```` ```check ```` is read; a fence closes on a line that is exactly ```` ``` ````. So a ` ```check ` line inside a ` ```bash ` block is not read as a check.
- A `## ` line ends Done when even inside an open fence, so an unclosed ```` ```check ```` raises at that point (message quotes the opening line).
- `$` with no command, `prints` with no text, and `exit` with no value are parse errors (they fall under "any other line" / "exit needs a whole number").
- Error messages quote the line with `%r`, e.g. `check block: 'exit x' needs a whole number or `nonzero``.

**Shortcuts taken**

none

**For later tickets**

- 02: `checks_in` takes the ticket text, so pass it `git show <base>:<ticket>` output directly. `ParseError` is the STOP case; its message already quotes the line, prefix it with the ticket path. `Check.exit` is an `int` or the string `"nonzero"`.
- Any new import in `feature_flow/` must be on the allowlist in `tests/run.sh` (near "the conductor imports only the standard library"); `collections` is not.
