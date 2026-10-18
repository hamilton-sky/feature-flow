# Debug a send-back

You were sent back. Something failed after you finished. Do not guess and do not patch until you know why.

## 1. Read every finding

Open the ticket's `## Review findings`. Take them in order. Each names a source (gate, floor guard, done when, test first, spec review, quality review) and, where it can, the exact command that failed.

## 2. Reproduce

Run the exact command the finding names, fresh, and read the whole output and exit code. If you cannot make it fail the same way, you do not yet understand the finding: say so in the Answer rather than changing code.

## 3. Isolate

Find the cause before you touch anything.

- Shrink it: the smallest failing case, the one test or one input that shows it.
- One hypothesis at a time. Say what you expect to see, then check it.
- Read the code path from the failing line back to where the wrong value or step comes from.
- Change one thing per experiment, and undo experiments that told you nothing.

## 4. Fix

Fix the cause, not the symptom. Never make a check pass by weakening it: no skipped or deleted tests, no loosened expectations, no silenced linters, no edits to lint, test or CI config.

## A class of defect

A finding marked `class: <pattern>`, or the same kind of mistake found a second time, is a kind of defect, not one site. Do not fix only the sites the finding lists: the next review finds the next site, and the ticket goes round again.

1. Search the whole codebase for the pattern and list every site, the ones the finding names and the ones it does not.
2. Add one guard test that fails on any site, present or future (a test that renders every screen and fails on a raw id, say, rather than one assertion per screen). Commit it first if the ticket is `Test first: yes`, and see it fail.
3. Fix every site, then see the guard test pass.

Say under **Review fixes** how you searched and how many sites you fixed.

## 5. Prove

Re-run the command that failed and see it pass. Then run the ticket's Done when again, in full. Only then write the Answer, with a line under **Review fixes** for each finding.

## When to stop

After two failed fixes of the same error, stop as the build guide says: set `Status: open`, write an Attempt note with what you tried and what you saw, and do not try a third time.
