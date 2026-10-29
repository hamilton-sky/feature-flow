# Make the acceptance tests pass, round 1

Type: task
Status: open
Blocked by: —
Test first: no
Level: 2
Check: none the conductor runs the acceptance tests again once every ticket is resolved

Every ticket is resolved, but the acceptance tests fail. The tester wrote them in `plans/conductor-rebuild/acceptance/` from spec.md before the build, so they check what the product owner asked for, not how it was built. Fix the code so they pass. You may run them with `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`.

If you are sure a test asks for something spec.md does not say, do not work around it, and do not change the test: the floor guard fails any change under `plans/conductor-rebuild/acceptance/`. Add a `## Ask: po` section to this ticket that names the test, what it expects and the spec.md line it disagrees with, and stop. The product owner rules on it. A test it rules wrong is left failing here and goes back to the tester once this ticket is resolved.

## Not in this ticket

- Any file under `plans/conductor-rebuild/acceptance/`.

## Done when

- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v` passes, apart from tests the product owner ruled wrong in this ticket.
- commands.md's Test command passes.

## The failing run

       'Smoke: `"/usr/bin/python3" -c "pass"`\n'
       'Test: `"/usr/bin/python3" -c "pass"`\n'
       'Acceptance: `"/usr/bin/python3" plans/f/acceptance/check.py`\n',
       'plans/f/learnings.md:\n# Learnings: f\n\n- (NN) <what you found>\n',
       'plans/f/map.md:\n'
       '# Map: f\n'
       '\n'
       '## Decisions so far\n'
       '\n'
       '<One line per resolved ticket.>\n',
       'plans/f/spec.md:\n# Spec\n\n## Stories\n\n- [ ] every ticket is built\n',
       'plans/f/tasks/01-t.md:\n'
       '# T1\n'
       '\n'
       'Type: task\n'
       'Status: open\n'
       'Blocked by: —\n'
       'Test first: no\n'
       'Touches: t01/\n'
       '\n'
       'body\n'
       '\n'
       '## Done when\n'
       '\n'
       '- x\n'
       '\n'
       '```check\n'
       '$ "/usr/bin/python3" -c "print(\'fine\')"\n'
       'prints fine\n'
       '```\n'
       '\n'
       '## Answer\n',
       'plans/f/tasks/02-t.md:\n'
       '# T2\n'
       '\n'
       'Type: task\n'
       'Status: open\n'
       'Blocked by: 01\n'
       'Test first: no\n'
       'Touches: t02/\n'
       '\n'
       'body\n'
       '\n'
       '## Done when\n'
       '\n'
       '- x\n'
       '\n'
       '```check\n'
       '$ "/usr/bin/python3" -c "print(\'fine\')"\n'
       'prints fine\n'
       '```\n'
       '\n'
       '## Answer\n',
       'commits on the branch:\nplan\ninit',
       'all commits:\ninit\nplan'] : the run left different files on the current code
    
    ----------------------------------------------------------------------
    Ran 48 tests in 157.084s
    
    FAILED (failures=13)

## Answer
