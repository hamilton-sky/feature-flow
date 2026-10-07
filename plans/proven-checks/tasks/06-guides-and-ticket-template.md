# Teach planners and builders the check block, the test commit and the two reviews

Type: task
Status: open
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

