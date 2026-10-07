# Acceptance: run the bar end to end

Type: task
Status: open
Blocked by: 09
Test first: no

Run the map's bar: `python3 -m unittest discover -s tests/py && bash tests/run.sh`. Then run the three tamper tests from ticket 01 against 0.1.6: check out the `v0.1.6` tag into a temp folder, copy `tests/py/test_tamper.py` and `tests/py/helpers.py` there and run `python3 -m unittest discover -s tests/py -k tamper`; the three STOP tests must fail there and pass here. Put the two outputs in this ticket's Answer. Do not edit any file but this ticket's Status and Answer.

## Not in this ticket

- CI on the PR (the PR is checked by the thread); a real Codex or Windows agent run.

## Done when

- The Answer shows the suite passing on the branch and the three tamper tests failing on `v0.1.6`.

## Reference

- map.md (the bar), tests/py/test_tamper.py

## Answer

