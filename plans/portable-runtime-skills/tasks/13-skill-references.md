# Move long checklists into skill references

Type: task
Status: open
Blocked by: 04
Test first: yes

Move long checklists, rubrics and examples from `automation-design`, `architect-review` and other large skills into adjacent `references/` files, where the main instructions can link to them without changing behavior. Follow the "Skill layout guidance" entry of `references.md`. Both renderers copy `references/` unchanged, like other resources.

Move text; do not rewrite it. A reader who follows every link sees the same instructions as before.

## Not in this ticket

- Changing what any skill does, or its description.
- Deleting the sentence-replacement rules from `adapters/codex/skill.awk`.

## Done when

- Every main `SKILL.md` links every reference file it uses, and a test fails a fixture whose `SKILL.md` links a missing file.
- A test fails a fixture with a `references/` file that no `SKILL.md` links.
- For every moved block, the text in the reference file equals the removed text (a test or a recorded `diff` in the Answer shows it).
- Both rendered installations contain the reference files, and `bash tests/run.sh` exits 0.

## Reference

- spec.md § Interfaces
- references.md, the "Skill layout guidance" entry
- `skills/automation-design/SKILL.md`, `skills/architect-review/SKILL.md`
- the renderers from tickets 02 and 03, as converted by ticket 04

## Answer
