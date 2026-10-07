# Teach planners and builders the check block, the test commit and the two reviews

Type: task
Status: resolved
Blocked by: 03, 04
Test first: no

Update the wording only, matching what tickets 03 and 04 built (read their Answers first):

- `guides/templates/ticket.md`: under `## Done when`, after the bullets, a ```` ```check ```` example with one `$` line, one `prints` line and a comment line saying the conductor runs this block before review.
- `guides/plan.md`, ticket rule 4: every bullet that names a command also goes into the ticket's `check` block (the grammar in three lines: `$ <command>`, `exit <N>|nonzero`, `prints <text>`); commands must be read-only and must run from the repo's top folder on the plan's platforms; a bullet that cannot be checked by a command stays prose for the reviewer. Rule 8: `Test first: yes` means the builder must commit a failing test alone first, so do not set it on a ticket whose test cannot fail before the code.
- `guides/build.md`: Step 7 `Test first: yes`: commit the new or changed test files alone first (message `test(<feature>): NN failing test`, no other files), see the Test command fail, then write the code and commit as Step 10 says; the conductor checks this. Step 8: the conductor also runs the ticket's `check` block; run it yourself first. Independent review: two fresh reviewers, spec then quality; findings from either come back as `## Review findings`.

## Not in this ticket

- `guides/review.md` and `guides/review-quality.md`: written with the code that uses them in ticket 04.
- `guides/debug.md`: ticket 05.
- README: ticket 08.

## Done when

- `grep -c '```check' guides/templates/ticket.md guides/plan.md` prints 1 or more for each file.
- `grep -c "failing test" guides/build.md` prints 1 or more, and `grep -c "quality" guides/build.md` prints 1 or more.
- `python3 -m unittest discover -s tests/py -k proof` passes, including a new test that `proof.checks_in` reads the example block in `guides/templates/ticket.md` without a `ParseError` (so the template cannot drift from the parser).
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Design, § Decisions
- guides/templates/ticket.md, guides/plan.md (Ticket rules 4 and 8), guides/build.md (Steps 7, 8, 10, Independent review), feature_flow/proof.py

## Answer


Built: `guides/templates/ticket.md` (check example under Done when), `guides/plan.md` (rule 4 grammar and a fenced ```check example, rule 8 Test first wording), `guides/build.md` (Step 7 test-only commit, Step 8 check block, Independent review two reviewers), `tests/py/test_proof.py` (new `TemplateExample` test).

Proof:
- `grep -c '```check' guides/templates/ticket.md guides/plan.md`: 1 for each file.
- `grep -c "failing test" guides/build.md`: 1; `grep -c "quality" guides/build.md`: 1.
- `python3 -m unittest discover -s tests/py -k proof`: 40 tests, OK (after the last edit); includes `test_the_ticket_template_block_parses`, which runs `proof.checks_in` on the template and on the example block in `guides/plan.md`.
- `python3 -m unittest discover -s tests/py`: 220 tests OK; `bash tests/run.sh`: 446 passed, 0 failed.

Decisions:
- The ticket text asked for a check example in the template only, but its Done when also counts one in `guides/plan.md`, so `plan.md` rule 4 carries a fenced example (reviewer note: keep Done when and guides consistent). The test parses both, so neither can drift from the parser.
- The template's `$` line is a placeholder in angle brackets; it parses as a command, which is all the test needs.

Shortcuts taken: none.

For later tickets: ticket 08 (README) can point to `guides/plan.md` rule 4 for the grammar.
