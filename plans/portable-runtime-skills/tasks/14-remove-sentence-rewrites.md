# Remove the Codex adapter's sentence replacements

Type: task
Status: open
Blocked by: 04
Test first: yes

With the canonical skills neutral and the runtime fragments explicit, delete the exact sentence-replacement rules from `adapters/codex/skill.awk`. Keep only what the Codex renderer still needs (frontmatter, `agents/openai.yaml`, role files), and remove the transitional fallback the Codex renderer kept.

Deleting those rules means deleting the "one rule at a time" checks in `tests/run.sh` that exercise them. That is expected and is not weakening the bar: the golden files of the rendered Codex installation, which must stay unchanged, replace them. Say in the Answer which checks were removed and which golden check now covers each.

## Not in this ticket

- Changing the rendered output. Any change to a golden file is a failure of this ticket.
- Moving checklists into `references/`.

## Done when

- `adapters/codex/skill.awk` no longer contains the replaced sentences (the Answer lists the `grep -c` of three of them, each `0`).
- The rendered Codex installation is byte for byte the same as before this ticket: the golden comparison in `tests/run.sh` passes unchanged.
- The Answer maps every removed check to the golden check that covers it.
- `bash tests/run.sh` exits 0.

## Reference

- `adapters/codex/skill.awk`
- `tests/run.sh`, the Codex adapter section
- the Codex renderer from ticket 03 and the golden files from ticket 04

## Answer
