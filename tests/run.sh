#!/bin/bash
# offline tests for the scripts. no network and no model is called.
# usage: bash tests/run.sh
# exit code is the number of failed checks, capped at 1.

set -uo pipefail
unset FLOW_INVOKE

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP:?}"' EXIT

PASS=0
FAILS=0

ok() { PASS=$((PASS + 1)); echo "  ok    $1"; }
bad() { FAILS=$((FAILS + 1)); echo "  FAIL  $1${2:+ ($2)}"; }
expect_rc() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "exit $3, wanted $2"; fi; }
# a here-string, not a pipe: grep -q stops reading at the first match, and with pipefail the
# printf feeding a pipe then fails on a broken pipe and turns a match into a miss
expect_has() { if grep -qF -- "$2" <<< "$3"; then ok "$1"; else bad "$1" "missing: $2"; fi; }
expect_lacks() { if grep -qF -- "$2" <<< "$3"; then bad "$1" "unexpected: $2"; else ok "$1"; fi; }

ticket() { # dir name status blocked-by [extra header line]
  printf '# %s\n\nType: task\nStatus: %s\nBlocked by: %s\nTest first: no\n%s\n\nbody\n\n## Done when\n\n- x\n\n## Answer\n' \
    "$2" "$3" "$4" "${5:-}" > "$1"
}

newrepo() { # name -> prints the repo dir
  local d="$TMP/$1"
  mkdir -p "$d/scripts" "$d/plans/f/tasks"
  (
    cd "$d" || exit 1
    git init -q
    git config user.email t@t
    git config user.name t
    echo "readme" > README.md
    ticket plans/f/tasks/01-a.md A open "—"
    ticket plans/f/tasks/02-b.md B open "01"
    ticket plans/f/tasks/03-c.md C open "01"
    ticket plans/f/tasks/04-d.md D open "02, 03"
    printf '# Map: f\n\n## Decisions so far\n\n<One line per resolved ticket.>\n\n## Open questions\n\n- <fog>\n' > plans/f/map.md
    printf '# Learnings: f\n\n- (NN) <what you found>\n' > plans/f/learnings.md
    printf '# Commands: f\n\nBuild: `<command>`\nSmoke: `<the quickest command>`\n' > plans/f/commands.md
    printf '# Spec\n' > plans/f/spec.md
    git add -A
    git commit -qm init
  )
  echo "$d"
}

echo "flow-status.py"
D="$(newrepo status)"
S="$ROOT/scripts/flow-status.py"
cd "$D" || exit 1
out="$(python3 "$S" f)"; expect_has "table marks the first ticket READY" "01  open      READY" "$out"
expect_has "table shows blockers" "after 02,03" "$out"
out="$(python3 "$S" f --next)"; expect_has "--next prints the lowest ready ticket" "plans/f/tasks/01-a.md" "$out"
out="$(python3 "$S" f --counts)"; expect_has "--counts" "total=4 resolved=0 open=4" "$out"
out="$(python3 "$S" f --check)"; expect_has "--check passes on a good graph" "OK: 4 tickets" "$out"
out="$(python3 "$S" f --mermaid)"; expect_has "--mermaid has nodes" 'T01["01 A"]:::ready' "$out"
expect_has "--mermaid has edges" "T02 --> T04" "$out"
out="$(python3 "$S" f --mermaid plain)"; expect_lacks "--mermaid plain has no colours" "classDef" "$out"
python3 "$S" f --next > /dev/null; expect_rc "--next exits 0 when something is ready" 0 $?

mkdir -p plans/stuck/tasks plans/done/tasks plans/bad/tasks plans/aws/tasks
ticket plans/stuck/tasks/01-a.md A claimed "—"; ticket plans/stuck/tasks/02-b.md B open "01"
python3 "$S" stuck --next > /dev/null 2>&1; expect_rc "--next exits 11 when stuck" 11 $?
ticket plans/done/tasks/01-a.md A resolved "—"; ticket plans/done/tasks/02-b.md B parked "01"
python3 "$S" done --next > /dev/null 2>&1; expect_rc "--next exits 10 when complete" 10 $?
ticket plans/aws/tasks/01-a.md A done "—"; ticket plans/aws/tasks/02-b.md B ready-for-agent "01"; ticket plans/aws/tasks/03-c.md C ready-for-human "—"
out="$(python3 "$S" aws)"; expect_has "aws status words: done counts as resolved" "01  resolved" "$out"
expect_has "aws status words: ready-for-agent is open and ready" "02  open      READY" "$out"
expect_has "aws status words: ready-for-human waits" "03  waiting" "$out"
ticket plans/bad/tasks/01-a.md A open "03"; ticket plans/bad/tasks/02-b.md B open "01"; ticket plans/bad/tasks/03-c.md C open "02"
ticket plans/bad/tasks/04-d.md D banana "99"; printf '# E\n\nStatus: open\nBlocked by: —\nTest first: maybe\n' > plans/bad/tasks/05-e.md
out="$(python3 "$S" bad --check 2>&1)"; rc=$?
expect_rc "--check exits 1 on a bad graph" 1 $rc
expect_has "--check finds the cycle" "part of a dependency cycle" "$out"
expect_has "--check finds a missing blocker" "blocked by 99, which does not exist" "$out"
expect_has "--check finds an unknown status" "unrecognised Status value" "$out"
expect_has "--check finds a missing Done when" "no ## Done when section" "$out"
expect_has "--check finds a bad Test first" "Test first must be yes or no" "$out"
python3 "$S" nope --next > /dev/null 2>&1; expect_rc "a missing feature exits 2" 2 $?
mkdir -p .scratch/x/issues; ticket .scratch/x/issues/01-a.md A ready-for-agent "—"
FLOW_DIR=.scratch FLOW_TICKETS=issues python3 "$S" x --next > /dev/null; expect_rc "FLOW_DIR and FLOW_TICKETS relocate the tickets" 0 $?

echo "floor-guard.py"
guard() { python3 "$ROOT/scripts/floor-guard.py" "$@"; } # run from the repo under test, like the flow does
D="$(newrepo guard)"
cd "$D" || exit 1
mkdir -p tests src
printf 'def test_a():\n    assert 1 == 1\n' > tests/test_a.py; printf 'x = 1\n' > src/app.py
printf 'fail_under = 80\n' > setup.cfg; printf '{}\n' > .eslintrc.json; printf 'def test_gone():\n    assert True\n' > tests/test_gone.py
ticket plans/f/tasks/02-b.md B open "01" "Floor: allow skip, suppress, empty-catch, threshold, config, test-delete"
git add -A; git commit -qm base; B0="$(git rev-parse HEAD)"
printf 'x = 2\ny = 3\n' > src/app.py; git add -A; git commit -qm clean
guard f 01 "$B0" > /dev/null; expect_rc "a clean diff passes" 0 $?
B1="$(git rev-parse HEAD)"
printf '@pytest.mark.skip\ndef test_a():\n    assert 1 == 1\n' > tests/test_a.py
printf 'x = 2  # noqa\ntry:\n    y = 1\nexcept Exception: pass\n' > src/app.py
printf 'fail_under = 10\n' > setup.cfg; printf '{"rules": {}}\n' > .eslintrc.json
git add -A; git commit -qm weaken
git rm -q tests/test_gone.py; git commit -qm delete
out="$(guard f 01 "$B1" 2>&1)"; rc=$?
expect_rc "a weakening diff fails" 1 $rc
expect_has "finds a skipped test" "skip: tests/test_a.py" "$out"
expect_has "finds a silenced check" "suppress: src/app.py" "$out"
expect_has "finds an empty catch" "empty-catch: src/app.py" "$out"
expect_has "finds a lowered threshold" "threshold: setup.cfg" "$out"
expect_has "finds edited lint config" "config: .eslintrc.json" "$out"
expect_has "finds a deleted test" "test-delete: tests/test_gone.py" "$out"
expect_has "warns about fewer assertions" "assertion line(s) removed" "$out"
guard f 02 "$B1" > /dev/null 2>&1; expect_rc "Floor: allow in the ticket at base lets the diff through" 0 $?
ticket plans/f/tasks/01-a.md A open "—" "Floor: allow skip, suppress, empty-catch, threshold, config, test-delete, ticket-edit"
git add -A; git commit -qm selfallow
out="$(guard f 01 "$B1" 2>&1)"; rc=$?
expect_rc "a worker cannot excuse itself by adding Floor: allow" 1 $rc
expect_has "and the edit to its own header is reported" "ticket-edit: plans/f/tasks/01-a.md" "$out"
guard f 99 "$B1" > /dev/null 2>&1; expect_rc "a missing ticket exits 2" 2 $?
# more fixtures: other languages, config files, odd arguments. ASCII only: mawk cuts a finding at 100
# bytes and gawk at 100 characters, so a non-ASCII line has no single answer in an awk-based check;
# tests/py/test_floorguard.py pins the byte cut.
ticket plans/f/tasks/04-d.md D open "02, 03" "Floor: skip, Config"
git add -A; git commit -qm extras-base; B2="$(git rev-parse HEAD)"
long="$(printf 'x%.0s' $(seq 1 120))"
printf 'it.skip("a", () => {})\nxit("b")\ntest.todo("c")\ndescribe.skip(x)\nmy_it.skip(y)\ntry { x() } catch (e) {}\ntry { y() } catch {   }\n// eslint-disable-next-line\n// @ts-ignore\nexpect(1).toBe(1)\n\t  // nolint %s\n# noqa %s cut at the hundredth character\n' "$long" "${long:0:92}" > src/web.test.js
printf '[pytest]\naddopts = --cov-fail-under=10\n' > pytest.ini
printf '#[ignore]\n#[allow(dead_code)]\nt.Skip("no")\n@Disabled\n' > src/lib.rs
mkdir -p .github/workflows; printf 'on: push\n' > .github/workflows/ci.yml
printf 'def test_b():\n    assert 2 == 2\n' > tests/test_assert_names.py
git add -A; git commit -qm extras
git rm -q tests/test_a.py; git commit -qm "drop test_a"
out="$(guard f 03 "$B2" 2>&1)"; rc=$?
expect_rc "other languages and config files fail the guard" 1 $rc
expect_has "JS skips are found" 'skip: src/web.test.js: it.skip("a", () => {})' "$out"
expect_has "so are xit, test.todo and describe.skip" 'skip: src/web.test.js: describe.skip(x)' "$out"
expect_lacks "my_it.skip is not a skip" "my_it.skip" "$out"
expect_has "both empty catch forms are found" 'empty-catch: src/web.test.js: try { y() } catch {   }' "$out"
expect_has "ts-ignore is a suppression" "suppress: src/web.test.js: // @ts-ignore" "$out"
expect_has "Rust and Go skips are found" 'skip: src/lib.rs: t.Skip("no")' "$out"
expect_has "a Rust allow is a suppression" "suppress: src/lib.rs: #[allow(dead_code)]" "$out"
expect_has "a lowered coverage threshold is found" "threshold: pytest.ini: addopts = --cov-fail-under=10" "$out"
expect_has "a workflow file is config" "config: .github/workflows/ci.yml" "$out"
expect_has "a finding is cut at 100 characters" "# noqa xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" "$out"
expect_lacks "and nothing past the cut is shown" "cut at the hundredth" "$out"
out="$(guard f 04 "$B2" 2>&1)"; rc=$?
expect_rc "Floor: skip, Config in the ticket allows those categories only" 1 $rc
expect_lacks "an allowed skip is not reported" "skip: src/web.test.js" "$out"
expect_lacks "an allowed config is not reported" "config: pytest.ini" "$out"
expect_has "but a suppression still is" "suppress: src/web.test.js: // @ts-ignore" "$out"
out="$(guard f 03 2>&1)"; expect_has "the base commit defaults to HEAD~1" "test-delete: tests/test_a.py" "$out"
out="$(guard f 03 "" 2>&1)"; expect_has "an empty base commit means the default too" "test-delete: tests/test_a.py" "$out"
guard f 03 no-such-commit > /dev/null 2>&1; expect_rc "a bad base commit exits with 128 from the revision lookup" 128 $?
guard f > /dev/null 2>&1; expect_rc "a missing ticket number is a usage error" 2 $?
guard > /dev/null 2>&1; expect_rc "no arguments is a usage error" 2 $?
expect_has "the usage line names the Python command" "usage: python3 scripts/floor-guard.py <feature> <NN> [base-commit]" "$(guard 2>&1)"
FLOW_DIR=elsewhere guard f 03 "$B2" > /dev/null 2>&1; expect_rc "FLOW_DIR moves the plans folder" 2 $?
FLOW_TICKETS=issues guard f 03 "$B2" > /dev/null 2>&1; expect_rc "FLOW_TICKETS moves the tickets folder" 2 $?

echo "floor-guard.py, protecting the plan"
addfloor() { awk -v l="$2" '{ print } /^Test first:/ { print l }' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; }
tamper() { # name expected(clean|flag) mutation [prelude]
  local d out rc base slug
  slug="$(printf '%s' "$1" | tr -c 'A-Za-z0-9' '_')"
  d="$(newrepo "tamper_$slug")"
  (
    cd "$d" || exit 1
    if [ -n "${4:-}" ]; then eval "$4"; git add -A; git commit -qm prelude; fi
    base="$(git rev-parse HEAD)"
    eval "$3"
    git add -A; git commit -qm change
    guard f 01 "$base" > .guard.out 2>&1
    echo $? > .guard.rc
  )
  rc="$(cat "$d/.guard.rc")"; out="$(cat "$d/.guard.out")"
  if [ "$2" = clean ]; then expect_rc "$1" 0 "$rc"; else expect_rc "$1" 1 "$rc"; fi
  TAMPER_OUT="$out"
}
T=plans/f/tasks
tamper "own Status and Answer may change" clean \
  "sed -i.bak 's/^Status: open/Status: resolved/' $T/01-a.md; rm $T/01-a.md.bak; printf 'Built: x\n' >> $T/01-a.md"
tamper "own Done when must not change" flag "sed -i.bak 's/^- x\$/- y/' $T/01-a.md; rm $T/01-a.md.bak"
expect_has "and the report says why" "text outside the Status line and the Answer was changed" "$TAMPER_OUT"
tamper "own header must not change" flag "addfloor $T/01-a.md 'Floor: allow skip'"
tamper "another ticket must not change" flag "sed -i.bak 's/^Status: open/Status: resolved/' $T/02-b.md; rm $T/02-b.md.bak"
expect_has "and the report names it" "ticket-edit: plans/f/tasks/02-b.md" "$TAMPER_OUT"
tamper "a new ticket must not appear" flag "cp $T/02-b.md $T/05-new.md"
tamper "the spec must not change" flag "printf 'more\n' >> plans/f/spec.md"
tamper "map.md may be appended to" clean "printf '01 - decided something\n' >> plans/f/map.md"
tamper "map.md placeholder may be replaced" clean "sed -i.bak 's/^<One line per resolved ticket.>\$/01 - real decision/' plans/f/map.md; rm plans/f/map.md.bak"
tamper "map.md real lines must not be removed" flag "sed -i.bak '/^## Decisions so far\$/d' plans/f/map.md; rm plans/f/map.md.bak"
tamper "learnings.md may be appended to" clean "printf -- '- (01) a trap\n' >> plans/f/learnings.md"
tamper "learnings.md lines must not be deleted" flag "sed -i.bak '/a trap/d' plans/f/learnings.md; rm plans/f/learnings.md.bak" \
  "printf -- '- (01) a trap\n' >> plans/f/learnings.md"
tamper "commands.md is frozen" flag "printf 'Test: \`true\`\n' >> plans/f/commands.md"
expect_has "and the report says so" "commands-edit: plans/f/commands.md" "$TAMPER_OUT"
tamper "commands.md may change when the ticket allows it" clean "printf 'Test: \`true\`\n' >> plans/f/commands.md" \
  "addfloor $T/01-a.md 'Floor: allow commands-edit'"
tamper "a ticket may allow ticket-edit" clean "printf 'more\n' >> plans/f/spec.md" \
  "addfloor $T/01-a.md 'Floor: allow ticket-edit'"

echo "flow-status.py, ordering hints"
cd "$TMP" || exit 1
mkdir -p ord/plans/g/tasks
cd ord || exit 1
S="$ROOT/scripts/flow-status.py"
printf '# A\n\nType: task\nStatus: open\nBlocked by: —\nTest first: no\n\nTicket 02 builds on this.\n\n## Not in this ticket\n\n- ticket 03 is separate\n\n## Done when\n\n- x\n' > plans/g/tasks/01-a.md
printf '# B\n\nType: task\nStatus: open\nBlocked by: 01\nTest first: no\n\nbody\n\n## Done when\n\n- x\n' > plans/g/tasks/02-b.md
printf '# C\n\nType: task\nStatus: open\nBlocked by: 01\nTest first: no\n\nUses the output of ticket 02 directly.\n\n## Done when\n\n- x\n' > plans/g/tasks/03-c.md
printf '# D\n\nType: task\nStatus: open\nBlocked by: 03\nTest first: no\n\nNeeds what tickets 01 and 02 leave behind.\n\n## Done when\n\n- x\n' > plans/g/tasks/04-d.md
out="$(python3 "$S" g --check)"; rc=$?
expect_rc "ordering warnings do not fail --check" 0 $rc
expect_has "a ticket that uses another without ordering is warned" "03: mentions ticket 02 but is not ordered against it" "$out"
expect_lacks "mentioning a later ticket that builds on this one is fine" "01: mentions" "$out"
expect_lacks "mentioning an ancestor through the chain is fine" "04: mentions ticket 01" "$out"
expect_has "an ancestor not on any chain is warned" "04: mentions ticket 02 but is not ordered against it" "$out"
mkdir -p plans/h/tasks; cp plans/g/tasks/01-a.md plans/h/tasks/01-a.md
i=0; : > plans/h/learnings.md; while [ "$i" -lt 45 ]; do echo "- (01) lesson $i" >> plans/h/learnings.md; i=$((i + 1)); done
out="$(python3 "$S" h --check)"; expect_has "a long learnings.md is flagged" "warning: learnings.md has 45 lines" "$out"

echo "gate.py"
D="$(newrepo gate_unit)"
cd "$D" || exit 1
G="$ROOT/scripts/gate.py"
printf '# Commands: f\n\nBuild: `echo building`\nTest: `echo testing`\nLint: `echo linting`\n' > plans/f/commands.md
out="$(python3 "$G" f 2>&1)"; rc=$?
expect_rc "all three commands passing exits 0" 0 $rc
expect_has "it reports the count" "gate: 3 command(s) passed" "$out"
order="$(printf '%s' "$out" | grep -oE 'gate: (Build|Test|Lint):' | tr '\n' ' ')"
expect_has "it runs build, then test, then lint" "gate: Build: gate: Test: gate: Lint:" "$order"
printf '# Commands: f\n\nBuild: `echo building`\nTest: `echo it broke; exit 3`\nLint: `echo linting`\n' > plans/f/commands.md
out="$(python3 "$G" f 2>&1)"; rc=$?
expect_rc "a failing command exits 1" 1 $rc
expect_has "it names the failing step" "gate: Test failed" "$out"
expect_has "it shows what the command printed" "it broke" "$out"
expect_lacks "it stops before the later steps" "gate: Lint:" "$out"
printf '# Commands: f\n\nBuild: `<command>`\nTest:\nSmoke: `<x>`\n' > plans/f/commands.md
out="$(python3 "$G" f 2>&1)"; rc=$?
expect_rc "placeholders and empty values are skipped" 0 $rc
expect_has "and it says nothing ran" "no commands defined" "$out"
out="$(python3 "$G" nofeature 2>&1)"; rc=$?
expect_rc "a feature without commands.md is not an error" 0 $rc
python3 "$G" > /dev/null 2>&1; expect_rc "no feature is a usage error" 2 $?

echo "planning roles"
expect_has "the planner ends with a plan verdict" "PLAN: READY" "$(cat "$ROOT/agents/feature-planner.md")"
expect_has "the planner checks the draft folder" "FLOW_DIR=.feature-flow/state/draft" "$(cat "$ROOT/agents/feature-planner.md")"
expect_has "the plan reviewer ends with a review verdict" "PLAN-REVIEW: PASS" "$(cat "$ROOT/agents/plan-reviewer.md")"

echo "install.py"
planner_tools="$(awk 'NR > 1 && /^---$/ {exit} NR > 1 {print}' "$ROOT/agents/feature-planner.md" 2>/dev/null)"
reviewer_tools="$(awk 'NR > 1 && /^---$/ {exit} NR > 1 {print}' "$ROOT/agents/plan-reviewer.md" 2>/dev/null)"
expect_has "the feature planner lists WebSearch" "- WebSearch" "$planner_tools"
expect_lacks "the feature planner has no Edit tool" "- Edit" "$planner_tools"
expect_lacks "the plan reviewer has no Edit tool" "- Edit" "$reviewer_tools"
expect_lacks "the plan reviewer has no Write tool" "- Write" "$reviewer_tools"
cd "$TMP" || exit 1
I="$TMP/inst"; mkdir -p "$I/repo" "$I/fresh"
out="$(python3 "$ROOT/install.py" "$I/repo" 2>&1)"; rc=$?
expect_rc "installs into a repo" 0 $rc
for f in .claude/skills/feature-flow/SKILL.md .claude/skills/architect-review/SKILL.md .claude/skills/automation-design/SKILL.md .claude/agents/ticket-builder.md .claude/agents/ticket-reviewer.md scripts/flow.py scripts/gate.py scripts/floor-guard.py scripts/flow-status.py scripts/flow-view.py scripts/flow-view.html .feature-flow/feature_flow/cli.py .feature-flow/guides/build.md .feature-flow/guides/templates/ticket.md .feature-flow/agents/ticket-reviewer.md; do
  if [ -f "$I/repo/$f" ]; then ok "installed $f"; else bad "installed $f"; fi
done
if [ -f "$I/repo/.claude/agents/feature-planner.md" ] && [ -f "$I/repo/.claude/agents/plan-reviewer.md" ]; then ok "Claude installs both planning roles"; else bad "Claude installs both planning roles"; fi
n="$(find "$I/repo/scripts" -name '*.sh' | wc -l | tr -d ' ')"; expect_rc "no bash script is installed under scripts/" 0 "$n"
expect_has "only the three skills are installed" "architect-review automation-design feature-flow" "$(ls "$I/repo/.claude/skills" | tr '\n' ' ')"
n="$(find "$I/repo/.feature-flow" \( -name __pycache__ -o -name '*.pyc' \) | wc -l | tr -d ' ')"; expect_rc "no __pycache__ is installed" 0 "$n"
expect_has "it points at the one skill" "next: /feature-flow <feature-name> in Claude Code" "$out"
out="$(cd "$I/repo" && git init -q && python3 scripts/flow.py f start 2>&1)"
expect_has "the installed scripts/flow.py runs" "PLAN" "$out"
mkdir -p "$I/repo/plans/f/tasks"
out="$(cd "$I/repo" && python3 scripts/flow.py f start 2>&1)"
expect_has "and starts a session on a plan" "OK " "$out"
rm -rf "$I/repo/.git" "$I/repo/plans"
out="$(python3 "$ROOT/install.py" "$I/repo" 2>&1)"
expect_has "a second run adds nothing" "added 0, updated 0" "$out"
echo "my own edit" >> "$I/repo/.claude/skills/feature-flow/SKILL.md"
out="$(python3 "$ROOT/install.py" "$I/repo" 2>&1)"
expect_has "a changed file is kept and reported" "kept" "$out"
expect_has "and it still has the user's edit" "my own edit" "$(cat "$I/repo/.claude/skills/feature-flow/SKILL.md")"
out="$(python3 "$ROOT/install.py" "$I/repo" --force 2>&1)"
expect_has "--force replaces it" "update" "$out"
expect_lacks "and the edit is gone" "my own edit" "$(cat "$I/repo/.claude/skills/feature-flow/SKILL.md")"
python3 "$ROOT/install.py" "$I/fresh" --dry-run > /dev/null 2>&1
if [ -z "$(ls -A "$I/fresh")" ]; then ok "--dry-run writes nothing"; else bad "--dry-run writes nothing"; fi
mkdir -p "$I/old/.claude/skills/my-skill"
echo "mine" > "$I/old/.claude/skills/my-skill/SKILL.md"
python3 "$ROOT/install.py" "$I/old" > /dev/null 2>&1
[ "$(cat "$I/old/.claude/skills/my-skill/SKILL.md")" = "mine" ] && ok "a skill it does not own is left alone" || bad "a skill it does not own is left alone"
mkdir -p "$I/old/.claude/skills/old-build" "$I/old/.claude/skills/old-review"
printf 'Run `python3 scripts/flow-status.py <feature> --next`.\n' > "$I/old/.claude/skills/old-build/SKILL.md"
printf 'End with `REVIEW: PASS` or `REVIEW: FAIL`.\n' > "$I/old/.claude/skills/old-review/SKILL.md"
out="$(python3 "$ROOT/install.py" "$I/old" 2>&1)"
expect_has "a leftover flow skill from an earlier version is named" "no longer installed: old-build old-review." "$out"
expect_lacks "but not the user's own skill" "my-skill" "$out"
if [ -f "$I/old/.claude/skills/old-build/SKILL.md" ]; then ok "and nothing is deleted"; else bad "and nothing is deleted"; fi
expect_lacks "the installed feature-flow skill is never named as a leftover" "no longer installed" "$(python3 "$ROOT/install.py" "$I/repo" 2>&1)"
mkdir -p "$I/repo2"
CLAUDE_HOME="$I/home/.claude" python3 "$ROOT/install.py" "$I/repo2" --user > /dev/null 2>&1
if [ -f "$I/home/.claude/skills/feature-flow/SKILL.md" ] && [ -f "$I/home/.claude/agents/ticket-reviewer.md" ]; then ok "--user puts skills and agents in the user folder"; else bad "--user puts skills and agents in the user folder"; fi
if [ -f "$I/repo2/scripts/flow.py" ] && [ -f "$I/repo2/.feature-flow/guides/build.md" ] && [ ! -e "$I/repo2/.claude" ]; then ok "--user still puts scripts and .feature-flow in the repo and no .claude"; else bad "--user still puts scripts and .feature-flow in the repo and no .claude"; fi
python3 "$ROOT/install.py" --nonsense > /dev/null 2>&1; expect_rc "an unknown option is a usage error" 2 $?
mkdir -p "$I/viash"
bash "$ROOT/install.sh" "$I/viash" --dry-run > /dev/null 2>&1; expect_rc "the install.sh wrapper runs the Python installer" 0 $?
expect_has "and passes its arguments on" "would add" "$(bash "$ROOT/install.sh" "$I/viash" --dry-run 2>&1)"
if [ ! -e "$ROOT/adapters/codex/skill.awk" ]; then ok "adapters/codex/skill.awk is gone"; else bad "adapters/codex/skill.awk is gone"; fi

echo "install.py, codex"
C="$TMP/codex"; mkdir -p "$C/repo" "$C/fresh" "$C/home"
SKILLS_BEFORE="$(cat "$ROOT"/skills/*/SKILL.md "$ROOT"/agents/*.md "$ROOT"/adapters/codex/feature-flow/SKILL.md | cksum)"
printf 'my own instructions\n' > "$C/repo/AGENTS.md"
out="$(python3 "$ROOT/install.py" "$C/repo" --agent codex 2>&1)"; rc=$?
expect_rc "--agent codex installs" 0 $rc
expect_has "it says which agent" "(codex)" "$out"
expect_has "it points at the Codex invocation" 'next: $feature-flow <feature-name> in Codex' "$out"
expect_lacks "and not at the Claude one" "in Claude Code" "$out"
for f in SKILL.md agents/openai.yaml; do
  if cmp -s "$ROOT/adapters/codex/feature-flow/$f" "$C/repo/.agents/skills/feature-flow/$f"; then ok "the Codex skill's $f is installed as it is"; else bad "the Codex skill's $f is installed as it is"; fi
done
for f in .agents/flow-roles/ticket-builder.md .agents/flow-roles/ticket-reviewer.md scripts/flow.py .feature-flow/feature_flow/cli.py .feature-flow/guides/review.md; do
  if [ -f "$C/repo/$f" ]; then ok "codex installed $f"; else bad "codex installed $f"; fi
done
if [ -f "$C/repo/.agents/flow-roles/feature-planner.md" ] && [ -f "$C/repo/.agents/flow-roles/plan-reviewer.md" ]; then ok "Codex installs both planning roles"; else bad "Codex installs both planning roles"; fi
mkdir -p "$C/repo/.agents/skills/old-build"; printf 'python3 scripts/flow-status.py f\n' > "$C/repo/.agents/skills/old-build/SKILL.md"
expect_has "codex: a leftover flow skill is named" "no longer installed: old-build." "$(python3 "$ROOT/install.py" "$C/repo" --agent codex 2>&1)"
rm -rf "$C/repo/.agents/skills/old-build"
expect_has "codex: only the three skills are installed" "architect-review automation-design feature-flow" "$(ls "$C/repo/.agents/skills" | tr '\n' ' ')"
if [ ! -e "$C/repo/.claude" ]; then ok "--agent codex writes no .claude"; else bad "--agent codex writes no .claude"; fi
[ "$(cat "$C/repo/AGENTS.md")" = "my own instructions" ] && ok "an existing AGENTS.md is never touched" || bad "an existing AGENTS.md is never touched"
[ "$(cat "$ROOT"/skills/*/SKILL.md "$ROOT"/agents/*.md "$ROOT"/adapters/codex/feature-flow/SKILL.md | cksum)" = "$SKILLS_BEFORE" ] && ok "installing never changes the sources" || bad "installing never changes the sources"
CS="$C/repo/.agents/skills"
n="$(grep -rlE '^(argument-hint|disable-model-invocation):' "$CS" | wc -l | tr -d ' ')"; expect_rc "no installed skill keeps a Claude only frontmatter key" 0 "$n"
bad_names=""
for s in "$CS"/*/; do
  s="$(basename "$s")"
  [ "$(sed -n 2p "$CS/$s/SKILL.md")" = "name: $s" ] || bad_names="$bad_names $s"
  sed -n 3p "$CS/$s/SKILL.md" | grep -q '^description: "' || bad_names="$bad_names $s"
done
if [ -z "$bad_names" ]; then ok "frontmatter is the name, then a quoted description, in every skill"; else bad "frontmatter is the name, then a quoted description, in every skill" "$bad_names"; fi
if [ "$(sed '1,/^---$/d' "$ROOT/skills/architect-review/SKILL.md" | sed '1,/^---$/d')" = "$(sed '1,/^---$/d' "$CS/architect-review/SKILL.md" | sed '1,/^---$/d')" ]; then ok "the other skills keep their body word for word"; else bad "the other skills keep their body word for word"; fi
printf -- '---\nname: q\ndescription: Says "hi" \\ there: ok\nargument-hint: "[a]"\n---\n\nbody\n' > "$C/q.md"
out="$(python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1]); from feature_flow.install import codex_header; sys.stdout.buffer.write(codex_header(open(sys.argv[2], "rb").read()))' "$ROOT" "$C/q.md")"
expect_has "a description with quotes and a backslash is escaped" 'description: "Says \"hi\" \\ there: ok"' "$out"
expect_lacks "and the other header keys are dropped" "argument-hint" "$out"
if command -v python3 > /dev/null 2>&1 && python3 -c 'import yaml' > /dev/null 2>&1; then
  python3 - "$CS" > "$C/yaml.out" 2>&1 << 'PY'
import glob, sys, yaml
root = sys.argv[1]
for f in sorted(glob.glob(root + "/*/SKILL.md")):
    fm = open(f, encoding="utf-8").read().split("\n---\n", 1)[0][4:]
    d = yaml.safe_load(fm)
    assert set(d) == {"name", "description"}, f
for f in sorted(glob.glob(root + "/*/agents/openai.yaml")):
    d = yaml.safe_load(open(f, encoding="utf-8"))
    assert set(d["interface"]) == {"display_name", "short_description", "default_prompt"}, f
PY
  expect_rc "a strict YAML parser reads every installed header and openai.yaml" 0 $?
else
  echo "  skip  python3 with PyYAML is not installed, so the YAML was not parsed"
fi
RB="$(cat "$C/repo/.agents/flow-roles/ticket-builder.md")"; RR="$(cat "$C/repo/.agents/flow-roles/ticket-reviewer.md")"
expect_has "the builder role keeps its rules" "You are the builder." "$RB"
expect_has "the reviewer role keeps its rules" "You are the reviewer, not the author." "$RR"
expect_lacks "a role file has no frontmatter" "tools:" "$RR"
[ "$(head -1 "$C/repo/.agents/flow-roles/ticket-reviewer.md")" = "You are the reviewer, not the author. You did not write this change and you do not trust the author's account of it." ] && ok "a role file starts with its first sentence" || bad "a role file starts with its first sentence"
out="$(python3 "$ROOT/install.py" "$C/repo" --agent codex 2>&1)"
expect_has "a second codex run adds nothing" "added 0, updated 0" "$out"
echo "my own edit" >> "$CS/architect-review/SKILL.md"
out="$(python3 "$ROOT/install.py" "$C/repo" --agent codex 2>&1)"
expect_has "an edited Codex skill is kept and reported" "kept" "$out"
expect_has "and keeps the user's edit" "my own edit" "$(cat "$CS/architect-review/SKILL.md")"
out="$(python3 "$ROOT/install.py" "$C/repo" --agent codex --force 2>&1)"
expect_has "--force rewrites it" "update" "$out"
expect_lacks "and the edit is gone" "my own edit" "$(cat "$CS/architect-review/SKILL.md")"
python3 "$ROOT/install.py" "$C/fresh" --agent codex --dry-run > /dev/null 2>&1
if [ -z "$(ls -A "$C/fresh")" ]; then ok "--agent codex --dry-run writes nothing"; else bad "--agent codex --dry-run writes nothing"; fi
out="$(python3 "$ROOT/install.py" "$C/fresh" --agent codex --dry-run 2>&1)"
expect_has "and still reports what it would add" "would add" "$out"
mkdir -p "$C/repo2"
AGENTS_HOME="$C/home/.agents" python3 "$ROOT/install.py" "$C/repo2" --agent codex --user > /dev/null 2>&1
if [ -f "$C/home/.agents/skills/feature-flow/SKILL.md" ] && [ -f "$C/home/.agents/skills/feature-flow/agents/openai.yaml" ]; then ok "--user puts the Codex skills in the user folder"; else bad "--user puts the Codex skills in the user folder"; fi
if [ -f "$C/repo2/.agents/flow-roles/ticket-reviewer.md" ] && [ -f "$C/repo2/scripts/flow.py" ] && [ ! -e "$C/repo2/.agents/skills" ]; then ok "--user keeps roles and scripts in the repo"; else bad "--user keeps roles and scripts in the repo"; fi
if [ ! -e "$I/repo/.agents" ]; then ok "the default install writes no .agents"; else bad "the default install writes no .agents"; fi
if cmp -s "$ROOT/skills/feature-flow/SKILL.md" "$I/repo/.claude/skills/feature-flow/SKILL.md"; then ok "the Claude install copies the skill byte for byte"; else bad "the Claude install copies the skill byte for byte"; fi
mkdir -p "$C/both"
out="$(python3 "$ROOT/install.py" "$C/both" --agent all 2>&1)"
if [ -f "$C/both/.claude/skills/feature-flow/SKILL.md" ] && [ -f "$C/both/.agents/skills/feature-flow/SKILL.md" ] && [ -f "$C/both/.claude/agents/ticket-builder.md" ] && [ -f "$C/both/.agents/flow-roles/ticket-builder.md" ]; then ok "--agent all installs both"; else bad "--agent all installs both"; fi
expect_has "and points at both" 'next: $feature-flow' "$out"
expect_has "and at Claude Code" "/feature-flow <feature-name> in Claude Code" "$out"
python3 "$ROOT/install.py" "$C/fresh" --agent nonsense > /dev/null 2>&1; expect_rc "an unknown agent is a usage error" 2 $?
python3 "$ROOT/install.py" --agent > /dev/null 2>&1; expect_rc "--agent without a value is a usage error" 2 $?
out="$(python3 "$ROOT/install.py" "$C/fresh" --agent=codex --dry-run 2>&1)"; expect_has "--agent=codex works too" "(codex)" "$out"

echo "flow-status.py, json"
set_status() { awk -v s="$2" 'FNR<=20 && !d && /^Status:/ {print "Status: " s; d=1; next} {print}' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; }
cd "$TMP" || exit 1
mkdir -p js/plans/f/tasks
cd js || exit 1
S="$ROOT/scripts/flow-status.py"
ticket plans/f/tasks/01-a.md 'Say "hi" \ and <b>caf'$'\xc3\xa9''</b>' resolved "—"
ticket plans/f/tasks/02-b.md B open "01"
ticket plans/f/tasks/03-c.md C open "01, 02"
out="$(python3 "$S" f --json)"
printf '%s' "$out" | jq -e . > /dev/null 2>&1; expect_rc "--json prints valid JSON" 0 $?
[ "$(printf '%s' "$out" | jq -r '.tickets[0].title')" = 'Say "hi" \ and <b>caf'$'\xc3\xa9''</b>' ] && ok "quotes, backslashes, tags and accents survive" || bad "quotes, backslashes, tags and accents survive"
expect_has "counts are included" '"total":3' "$out"
[ "$(printf '%s' "$out" | jq -r '[.tickets[] | select(.ready) | .label] | join(",")')" = "02" ] && ok "readiness matches the table" || bad "readiness matches the table"
[ "$(printf '%s' "$out" | jq -r '.tickets[2].blocked_by | join(",")')" = "01,02" ] && ok "blockers are listed" || bad "blockers are listed"
[ "$(printf '%s' "$out" | jq -r '.tickets[0].type')" = "task" ] && ok "a missing Type defaults to task" || bad "a missing Type defaults to task"

echo "flow-status.py, odd plans"
# a duplicate number, a CRLF Status line and an empty ticket file: the table and the checks still work
mkdir -p "$TMP/status/plans/dup/tasks"
ticket "$TMP/status/plans/dup/tasks/01-a.md" A open "—"; ticket "$TMP/status/plans/dup/tasks/01-b.md" B resolved "02"
printf '# C\r\n\r\nStatus: open\r\nBlocked by: 01\r\n\r\nSee ticket 01 and 03.\r\n' > "$TMP/status/plans/dup/tasks/02-c.md"
: > "$TMP/status/plans/dup/tasks/03-empty.md"
cd "$TMP/status" || exit 1
S="$ROOT/scripts/flow-status.py"
out="$(python3 "$S" dup --check 2>&1)"; rc=$?
expect_rc "a duplicate number fails --check" 1 $rc
expect_has "and the check names it" "01: two tickets share this number" "$out"
expect_has "a CRLF Status line reads like any other" "02  open" "$(python3 "$S" dup)"
expect_has "an empty ticket file is skipped" "total=2 " "$(python3 "$S" dup --counts)"
python3 "$S" > /dev/null 2>&1; expect_rc "no feature is a usage error" 2 $?
expect_has "and the usage line names the Python command" "usage: python3 scripts/flow-status.py <feature>" "$(python3 "$S" 2>&1)"
out="$(python3 "$S" dup --json)"
printf '%s' "$out" | jq -e . > /dev/null 2>&1; expect_rc "--json is valid JSON on a plan with a duplicate number" 0 $?

echo "flow-view.py"
V="$ROOT/scripts/flow-view.py"
mkdir -p "$TMP/view/plans/f/tasks"
cd "$TMP/view" || exit 1
git init -q
git config user.email t@t
git config user.name t
ticket plans/f/tasks/01-a.md 'First ticket' open "—"
ticket plans/f/tasks/02-b.md '</script><script>window.__xss=1</script><img src=x onerror=alert(1)>' open "01"
git add -A; GIT_AUTHOR_DATE="1790000000 +0000" GIT_COMMITTER_DATE="1790000000 +0000" git commit -qm plan
set_status plans/f/tasks/01-a.md resolved
printf 'Built: the first thing\nProof: it ran\n<img src=x onerror=alert(2)>\n' >> plans/f/tasks/01-a.md
git add -A; GIT_AUTHOR_DATE="1790001000 +0000" GIT_COMMITTER_DATE="1790001000 +0000" git commit -qm resolve
set_status plans/f/tasks/01-a.md open
printf '\n## Review findings (round 1, gate)\n\nfix it\n' >> plans/f/tasks/01-a.md
git add -A; GIT_AUTHOR_DATE="1790002000 +0000" GIT_COMMITTER_DATE="1790002000 +0000" git commit -qm reopen
set_status plans/f/tasks/01-a.md resolved
git add -A; GIT_AUTHOR_DATE="1790003000 +0000" GIT_COMMITTER_DATE="1790003000 +0000" git commit -qm resolve-again

python3 "$V" f --no-open --out "$TMP/view.html" > /dev/null 2>&1; expect_rc "the page is written" 0 $?
page="$(cat "$TMP/view.html")"
data="$(grep -F '<script id="flow-data"' "$TMP/view.html" | sed 's/^<script id="flow-data" type="application\/json">//; s/<\/script>$//')"
printf '%s' "$data" | jq -e . > /dev/null 2>&1; expect_rc "the embedded data is valid JSON" 0 $?
expect_has "the page has the animated graph code" "@keyframes flow" "$page"
[ "$(printf '%s' "$data" | jq -r '[.details["01"].history[].status] | join(",")')" = "open,resolved,open,resolved" ] && ok "history lists every status change from git" || bad "history lists every status change from git"
[ "$(printf '%s' "$data" | jq -r '.details["01"].history[1].t')" = "1790001000" ] && ok "history carries the commit time" || bad "history carries the commit time"
[ "$(printf '%s' "$data" | jq -r '.details["01"] | has("cost")')" = "false" ] && ok "there is no cost data" || bad "there is no cost data"
[ "$(printf '%s' "$data" | jq -r '.details["01"].rounds[0] | "\(.n) \(.source)"')" = "1 gate" ] && ok "sent back rounds are read from the ticket" || bad "sent back rounds are read from the ticket"
[ "$(printf '%s' "$data" | jq -r '.details["01"].done_when[0]')" = "x" ] && ok "Done when bullets are included" || bad "Done when bullets are included"
expect_has "the Answer excerpt is included" "Built: the first thing" "$(printf '%s' "$data" | jq -r '.details["01"].answer')"
[ "$(printf '%s' "$data" | jq -r '.details["02"].history | length')" = "1" ] && ok "a ticket with one commit has one history entry" || bad "a ticket with one commit has one history entry"

expect_lacks "hostile ticket text cannot close the data script" '</script><script>window' "$page"
expect_lacks "hostile ticket text cannot inject an element" '<img src=x' "$page"
expect_has "the angle brackets are escaped in the data" 'u003c/script' "$page"
expect_lacks "the page never writes HTML from data" "innerHTML" "$page"
expect_lacks "the page never evaluates strings" "eval(" "$page"
urls="$(grep -oE 'https?://[^" <>)]+' "$TMP/view.html" | grep -vF 'http://www.w3.org/2000/svg' || true)"
if [ -z "$urls" ]; then ok "the page is self contained, no external addresses"; else bad "the page is self contained, no external addresses" "$urls"; fi
expect_lacks "an ordinary page does not auto refresh" 'http-equiv="refresh"' "$page"

out="$(python3 "$V" f --no-open 2>&1)"
expect_has "the default location is inside .git" ".git/flow-f.html" "$out"
if [ -z "$(git status --porcelain)" ]; then ok "writing the page never dirties the tree"; else bad "writing the page never dirties the tree"; fi
python3 "$V" nosuchfeature --no-open > /dev/null 2>&1; expect_rc "a missing feature exits 2" 2 $?
python3 "$V" f --bogus > /dev/null 2>&1; expect_rc "an unknown option exits 2" 2 $?
python3 "$V" > /dev/null 2>&1; expect_rc "no feature exits 2" 2 $?

mkdir -p "$TMP/nogit/plans/f/tasks" "$TMP/nogit_out"
(cd "$TMP/nogit" && ticket plans/f/tasks/01-a.md A open "—" && TMPDIR="$TMP/nogit_out" python3 "$V" f --no-open > /dev/null 2>&1)
if [ -f "$TMP/nogit_out/flow-f.html" ]; then ok "outside a git repo the page goes to the temp folder"; else bad "outside a git repo the page goes to the temp folder"; fi
data2="$(grep -F '<script id="flow-data"' "$TMP/nogit_out/flow-f.html" | sed 's/^<script id="flow-data" type="application\/json">//; s/<\/script>$//')"
[ "$(printf '%s' "$data2" | jq -r '.details["01"].history | length')" = "0" ] && ok "and it simply has no history" || bad "and it simply has no history"

cd "$TMP/view" || exit 1
set_status plans/f/tasks/02-b.md resolved
git add -A; git commit -qm both
out="$(FLOW_WATCH_SECONDS=0.1 python3 "$V" f --watch --no-open --out "$TMP/watch_done.html" 2>&1)"
expect_has "watching a finished feature ends at once" "feature complete" "$out"
expect_lacks "and leaves a page that does not refresh" 'http-equiv="refresh"' "$(cat "$TMP/watch_done.html")"
set_status plans/f/tasks/02-b.md open
git add -A; git commit -qm reopen-02
( FLOW_WATCH_SECONDS=0.2 python3 "$V" f --watch --no-open --out "$TMP/watch_live.html" > /dev/null 2>&1 & echo $! > "$TMP/watch.pid" )
sleep 2
expect_has "watching a running feature writes a page that refreshes itself" 'http-equiv="refresh"' "$(cat "$TMP/watch_live.html" 2> /dev/null)"
kill "$(cat "$TMP/watch.pid")" 2> /dev/null || true

echo "flow-view.py, edge cases"
# capitals in headings, more than 8 Done when bullets, a bullet over 240 characters, an Answer over 700,
# quotes, backslashes and tabs, review rounds with and without a number or a source, the template's
# Answer placeholder, a CRLF Status line. ASCII only: tests/py/test_view.py pins the non-ASCII cuts.
VE="$TMP/viewe"
mkdir -p "$VE/plans/e/tasks" "$VE/plans/blank/tasks" "$VE/.scratch/x/issues"
cd "$VE" || exit 1
git init -q
git config user.email t@t
git config user.name t
ve_long="$(printf '%0300d' 0)"
{
  printf '# Edge "quoted" \\ back\tslash\n\nType: task\nStatus: open\nBlocked by: -\nTest first: no\n\nbody\n\n## DONE WHEN\n\n'
  printf -- '- %s\n' "$ve_long"
  for i in 1 2 3 4 5 6 7 8 9 10; do printf -- '- bullet %s\n' "$i"; done
  printf -- '\n## Answer\n\n<!-- a comment -->\nBuilt: "it" \\ and\ttab\n   indented\n\t\n<b>skipped</b>\n'
  printf '%s%s%s\nafter the cut\n' "$ve_long" "$ve_long" "$ve_long"
  printf '\n## Review findings (round 3, gate)\n\nx\n## Review findings\n## review findings (round 12)\n## Review Findings (round 4, a, b) (c)\n'
} > plans/e/tasks/01-a.md
printf '# B\n\nStatus: parked (later)\nBlocked by: 01\n\n## Done when\n\n- y\n\n## Answer\n\n<left empty until the ticket is resolved>\nleft empty until done\n' > plans/e/tasks/02-b.md
printf '# C\r\n\r\nStatus: resolved\r\nBlocked by: 01\r\n\r\n## Done when\r\n\r\n- z\r\n' > plans/e/tasks/03-c.md
: > plans/blank/tasks/01-zero.md
ticket .scratch/x/issues/01-a.md A ready-for-agent "-"
git add -A; git commit -qm edge
ve() { FLOW_NO_OPEN=1 python3 "$V" "$@"; }
vdata() { grep -F '<script id="flow-data"' "$1" | sed 's/^<script id="flow-data" type="application\/json">//; s/<\/script>$//'; }
ve e --no-open --out "$TMP/ve.html" > /dev/null 2>&1; expect_rc "a plan with odd tickets writes a page" 0 $?
ed="$(vdata "$TMP/ve.html")"
printf '%s' "$ed" | jq -e . > /dev/null 2>&1; expect_rc "and its data is valid JSON" 0 $?
[ "$(printf '%s' "$ed" | jq -r '.details["01"].done_when | length')" = 8 ] && ok "only the first 8 Done when bullets are kept" || bad "only the first 8 Done when bullets are kept"
[ "$(printf '%s' "$ed" | jq -r '.details["01"].done_when[0] | length')" = 240 ] && ok "a long bullet is cut at 240 characters" || bad "a long bullet is cut at 240 characters"
[ "$(printf '%s' "$ed" | jq -r '.details["01"].answer | length')" -le 700 ] && ok "an Answer is cut at 700 characters" || bad "an Answer is cut at 700 characters"
expect_has "the Answer keeps quotes, backslashes and tabs" 'Built: "it" \ and	tab' "$(printf '%s' "$ed" | jq -r '.details["01"].answer')"
expect_lacks "and drops a comment line" "a comment" "$(printf '%s' "$ed" | jq -r '.details["01"].answer')"
[ "$(printf '%s' "$ed" | jq -r '[.details["01"].rounds[] | "\(.n):\(.source)"] | join(",")')" = "3:gate,0:,12:,4:a, b" ] && ok "review rounds are read with and without a number or a source" || bad "review rounds are read with and without a number or a source"
[ "$(printf '%s' "$ed" | jq -r '.details["02"].answer')" = "" ] && ok "the template's Answer placeholder is no answer" || bad "the template's Answer placeholder is no answer"
[ "$(printf '%s' "$ed" | jq -r '.details["03"].history[0].status')" = "resolved" ] && ok "a CRLF Status line reads like any other in the history" || bad "a CRLF Status line reads like any other in the history"
[ "$(printf '%s' "$ed" | jq -r '.details["02"].history[0].status')" = "parked" ] && ok "a parked ticket has a parked history" || bad "a parked ticket has a parked history"
FLOW_DIR=.scratch FLOW_TICKETS=issues ve x --no-open --out "$TMP/vx.html" > /dev/null 2>&1; expect_rc "FLOW_DIR and FLOW_TICKETS relocate the tickets" 0 $?
ve blank --no-open --out "$TMP/vb.html" > /dev/null 2>&1; expect_rc "an empty ticket file does not stop the page" 0 $?
ve f --out > /dev/null 2>&1; expect_rc "--out without a value exits 2" 2 $?
expect_has "the usage line names the Python command" "usage: python3 scripts/flow-view.py <feature>" "$(ve 2>&1)"
mkdir -p "$TMP/vnotpl/scripts"; cp "$ROOT/scripts/flow-view.py" "$TMP/vnotpl/scripts/"; cp -R "$ROOT/feature_flow" "$TMP/vnotpl/feature_flow"
out="$(FLOW_NO_OPEN=1 python3 "$TMP/vnotpl/scripts/flow-view.py" e --no-open 2>&1)"; rc=$?
expect_rc "a copy without the page template exits 2" 2 $rc
expect_has "and says which file is missing" "flow-view.html" "$out"
rm -rf -- "$TMP/vnotpl"

echo "demo and viewer logic"
out="$(bash "$ROOT/examples/demo.sh" "$TMP/demo" 2>&1)"; rc=$?
expect_rc "the demo builds a project and its page" 0 $rc
dd="$(grep -F '<script id="flow-data"' "$TMP/demo/.git/flow-demo.html" | sed 's/^<script id="flow-data" type="application\/json">//; s/<\/script>$//')"
[ "$(printf '%s' "$dd" | jq -r '"\(.counts.total) \(.counts.resolved) \(.counts.claimed) \(.counts.ready)"')" = "10 5 1 2" ] && ok "the demo shows 10 tickets: 5 resolved, 1 in progress, 2 ready" || bad "the demo shows 10 tickets: 5 resolved, 1 in progress, 2 ready"
[ "$(printf '%s' "$dd" | jq -r '.details["02"].history | length')" = "4" ] && ok "the demo has a ticket that was sent back and recovered" || bad "the demo has a ticket that was sent back and recovered"
if command -v node > /dev/null 2>&1; then
  while IFS= read -r line; do
    case "$line" in
      "ok   "*) ok "viewer: ${line#ok   }" ;;
      "FAIL "*) bad "viewer: ${line#FAIL }" ;;
    esac
  done < <(node "$ROOT/tests/viewer-logic.test.js" "$ROOT/scripts/flow-view.html" 2>&1)
else
  echo "  skip  node is not installed, so the layout and replay unit tests were not run"
fi

echo "flow.py, unit tests"
out="$(cd "$ROOT" && python3 -m unittest discover -s tests/py 2>&1)"; rc=$?
expect_rc "python3 -m unittest discover -s tests/py passes" 0 $rc
[ "$rc" = 0 ] || printf '%s\n' "$out" | tail -20
out="$(cd "$ROOT" && python3 -c 'import ast,sys; [ast.parse(open(f).read(), f, feature_version=(3, 9)) for f in sys.argv[1:]]' feature_flow/*.py scripts/flow.py 2>&1)"
expect_rc "the conductor parses as Python 3.9" 0 $?
out="$(cd "$ROOT" && grep -rlE '^(import|from) ' feature_flow | xargs grep -hE '^(import|from) ' | grep -vE '^(import|from) (feature_flow|\.|os|sys|re|subprocess|pathlib|argparse|secrets|time|datetime|shlex|typing|dataclasses|__future__|json|textwrap|tempfile|shutil|enum|difflib)\b')"
if [ -z "$out" ]; then ok "the conductor imports only the standard library"; else bad "the conductor imports only the standard library" "$out"; fi

flowrepo() { # name -> prints a newrepo dir that also has scripts/flow.py and feature_flow/
  local d
  d="$(newrepo "$1")"
  cp "$ROOT/scripts/flow.py" "$d/scripts/"
  mkdir -p "$d/feature_flow"
  cp "$ROOT"/feature_flow/*.py "$d/feature_flow/"
  (cd "$d" && git add -A && git commit -qm "add flow.py")
  echo "$d"
}
pyflow() { # args... -> sets OUT and RC, run in the current directory
  OUT="$(python3 scripts/flow.py "$@" 2> /dev/null)"
  RC=$?
}
setst() { awk -v s="$1" 'FNR<=20 && !d && /^Status:/ {print "Status: " s; d=1; next} {print}' "$2" > "$2.tmp" && mv "$2.tmp" "$2"; }
resolve() { echo "work" > "work-$RANDOM.txt"; setst resolved "$1"; git add -A; git commit -qm "${2:-feat: work}"; }

echo "flow.py, build and checks"
D="$(flowrepo pyflow_build)"
cd "$D" || exit 1
SHA="$(git rev-parse HEAD)"
pyflow f next
expect_rc "the first next exits 0" 0 "$RC"
expect_has "and hands out the first ticket at HEAD" "BUILD plans/f/tasks/01-a.md 01 $SHA" "$OUT"
if [ -f .feature-flow/state/flow-f.state ]; then ok "it creates .feature-flow/state/flow-f.state"; else bad "it creates .feature-flow/state/flow-f.state"; fi
expect_has "it logs the BUILD" ",01,BUILD" "$(cat .feature-flow/state/flow-f.log)"
expect_rc "and leaves the tree clean" 0 "$(git status --porcelain | wc -l | tr -d ' ')"
resolve plans/f/tasks/01-a.md
pyflow f next
expect_has "a resolved ticket goes to review with the same base" "REVIEW plans/f/tasks/01-a.md 01 $SHA" "$OUT"
expect_has "the state records HEAD as the review sha" "review_sha=$(git rev-parse HEAD)" "$(cat .feature-flow/state/flow-f.state)"
expect_has "the log has the gate" "GATE-PASS" "$(cat .feature-flow/state/flow-f.log)"
expect_has "and the floor guard" "GUARD-PASS" "$(cat .feature-flow/state/flow-f.log)"

D="$(flowrepo pyflow_retry)"
cd "$D" || exit 1
pyflow f next
setst claimed plans/f/tasks/01-a.md
pyflow f next
expect_has "a ticket left claimed is built again" "BUILD plans/f/tasks/01-a.md 01" "$OUT"
expect_has "and reset to open" "Status: open" "$(cat plans/f/tasks/01-a.md)"
pyflow f next
expect_rc "after FLOW_MAX_RETRIES attempts next exits 1" 1 "$RC"
expect_has "and says the ticket is unresolved" "STOP 01-a is still unresolved after 2 attempt(s)" "$OUT"

D="$(flowrepo pyflow_gate)"
cd "$D" || exit 1
printf 'Test: `test ! -e FAILING`\n' >> plans/f/commands.md; touch FAILING; git add -A; git commit -qm "failing test"
pyflow f next
resolve plans/f/tasks/01-a.md
pyflow f next
expect_has "a failing gate builds the ticket again" "BUILD plans/f/tasks/01-a.md 01" "$OUT"
expect_has "with the gate's findings in the ticket" "## Review findings (round 1, gate)" "$(cat plans/f/tasks/01-a.md)"
expect_has "committed" "chore(f): 01 review findings, round 1" "$(git log -1 --format=%s)"
for r in 2 3 4; do resolve plans/f/tasks/01-a.md; pyflow f next; done
expect_rc "the 4th gate failure exits 1" 1 "$RC"
expect_has "and stops after 3 rounds" "STOP 01-a still fails the gate after 3 round(s)" "$OUT"

D="$(flowrepo pyflow_dirty)"
cd "$D" || exit 1
pyflow f next
setst resolved plans/f/tasks/01-a.md; git add -A; git commit -qm "feat: 01"; touch stray.txt
pyflow f next
expect_has "a resolved ticket with a dirty tree stops" "STOP working tree is dirty after 01-a, it should have been committed" "$OUT"
cd "$ROOT" || exit 1

echo "flow.py, review verdict and finish"
reply() { printf 'SPEC\n- checked\n%s\n' "$1" > .git/reply.txt; }
D="$(flowrepo pyflow_review)"
cd "$D" || exit 1
pyflow f verdict .git/reply.txt
expect_rc "verdict with no review pending exits 2" 2 "$RC"
pyflow f next; resolve plans/f/tasks/01-a.md; pyflow f next
before="$(cat .feature-flow/state/flow-f.state; git rev-parse HEAD; git status --porcelain)"
reply "REVIEW: PASS"
pyflow f verdict .git/reply.txt
expect_has "a PASS reply is recorded" "OK" "$OUT"
expect_has "and logged" "VERDICT-PASS" "$(cat .feature-flow/state/flow-f.log)"
pyflow f next
expect_has "after PASS next hands out the next ticket" "BUILD plans/f/tasks/02-b.md 02" "$OUT"
pyflow f verdict .git/reply.txt
expect_rc "verdict after the review was judged exits 2" 2 "$RC"
for t in 02-b 03-c 04-d; do
  resolve "plans/f/tasks/$t.md"; pyflow f next; pyflow f verdict .git/reply.txt; pyflow f next
done
expect_rc "on the last ticket next exits 0" 0 "$RC"
expect_has "and prints DONE" "DONE f is complete" "$OUT"

D="$(flowrepo pyflow_reviewfail)"
cd "$D" || exit 1
pyflow f next
for r in 1 2 3 4; do
  resolve plans/f/tasks/01-a.md; pyflow f next
  reply "1. major x.py: a bug round $r
REVIEW: FAIL"
  pyflow f verdict .git/reply.txt; pyflow f next
  if [ "$r" = 1 ]; then
    expect_has "a FAIL reply builds the ticket again" "BUILD plans/f/tasks/01-a.md 01" "$OUT"
    expect_has "with the reply under its findings heading" "## Review findings (round 1, independent review)" "$(cat plans/f/tasks/01-a.md)"
    expect_has "and the reviewer's text" "major x.py: a bug round 1" "$(cat plans/f/tasks/01-a.md)"
    expect_has "committed" "chore(f): 01 review findings, round 1" "$(git log -1 --format=%s)"
    expect_has "and logged" "VERDICT-FAIL" "$(cat .feature-flow/state/flow-f.log)"
  fi
done
expect_rc "the 4th review failure exits 1" 1 "$RC"
expect_has "and stops after 3 rounds" "STOP 01-a still fails the independent review after 3 round(s)" "$OUT"

D="$(flowrepo pyflow_noverdict)"
cd "$D" || exit 1
pyflow f next; resolve plans/f/tasks/01-a.md; pyflow f next
reply "I am not sure"
pyflow f verdict .git/reply.txt
expect_has "a reply with no verdict asks for another" "RETRY no review verdict" "$OUT"
expect_has "and is logged" "VERDICT-NONE" "$(cat .feature-flow/state/flow-f.log)"
pyflow f next
expect_has "the review is handed out again" "REVIEW plans/f/tasks/01-a.md 01" "$OUT"
pyflow f verdict .git/reply.txt; pyflow f next
expect_rc "a second reply with no verdict exits 1" 1 "$RC"
expect_has "and stops" "STOP no review verdict for 01-a after 2 attempt(s)" "$OUT"

D="$(flowrepo pyflow_reviewedit)"
cd "$D" || exit 1
pyflow f next; resolve plans/f/tasks/01-a.md; pyflow f next
echo tampered >> README.md; reply "REVIEW: PASS"; pyflow f verdict .git/reply.txt; pyflow f next
expect_rc "a reviewer's uncommitted edit exits 1" 1 "$RC"
expect_has "and stops" "STOP the reviewer changed tracked files, which a reviewer must never do" "$OUT"
D="$(flowrepo pyflow_reviewcommit)"
cd "$D" || exit 1
pyflow f next; resolve plans/f/tasks/01-a.md; pyflow f next
echo tampered >> README.md; git commit -qam "reviewer commit"; pyflow f verdict .git/reply.txt; pyflow f next
expect_rc "a reviewer's commit with a clean tree exits 1" 1 "$RC"
expect_has "and stops" "STOP the reviewer changed tracked files, which a reviewer must never do" "$OUT"

D="$(flowrepo pyflow_runlimit)"
cd "$D" || exit 1
pyflow f next; resolve plans/f/tasks/01-a.md
sed 's/^runs=.*/runs=65/' .feature-flow/state/flow-f.state > .feature-flow/state/flow-f.state.new && mv .feature-flow/state/flow-f.state.new .feature-flow/state/flow-f.state
pyflow f next
expect_rc "passing the run limit exits 1" 1 "$RC"
expect_has "and stops" "STOP run limit of 65 sessions reached, stopping" "$OUT"

D="$(flowrepo pyflow_noreview)"
cd "$D" || exit 1
pyflow f next; reply "REVIEW: PASS"
before="$(cat .feature-flow/state/flow-f.state; git rev-parse HEAD; git status --porcelain)"
pyflow f verdict .git/reply.txt
expect_rc "verdict while a build is pending exits 2" 2 "$RC"
if [ "$before" = "$(cat .feature-flow/state/flow-f.state; git rev-parse HEAD; git status --porcelain)" ]; then ok "and changes nothing"; else bad "and changes nothing"; fi
cd "$ROOT" || exit 1

echo "flow.py, sessions, handoff and relay"
D="$(flowrepo pyflow_session)"
cd "$D" || exit 1
pyflow nope start
expect_has "start with no plan folder prints PLAN" "PLAN" "$OUT"
pyflow f next; setst claimed plans/f/tasks/01-a.md
before="$(grep -E '^(ticket|round|attempt)=' .feature-flow/state/flow-f.state)"
pyflow f start
expect_rc "start exits 0" 0 "$RC"
TOK="${OUT#OK }"
if [ -n "$TOK" ] && [ "OK $TOK" = "$OUT" ]; then ok "start prints OK and a token"; else bad "start prints OK and a token" "$OUT"; fi
if [ "$before" = "$(grep -E '^(ticket|round|attempt)=' .feature-flow/state/flow-f.state)" ]; then ok "start leaves the ticket, round and attempt alone"; else bad "start leaves the ticket, round and attempt alone"; fi
snap="$(cat .feature-flow/state/flow-f.state; git status --porcelain)"
pyflow f next
expect_rc "next without the token exits 1" 1 "$RC"
expect_has "and names the owner" "owned by another session ($TOK)" "$OUT"
OUT="$(FLOW_SESSION=wrong python3 scripts/flow.py f next 2> /dev/null)"
expect_has "next with a different token stops too" "STOP f is owned by another session" "$OUT"
if [ "$snap" = "$(cat .feature-flow/state/flow-f.state; git status --porcelain)" ]; then ok "and neither changes the state or the tree"; else bad "and neither changes the state or the tree"; fi
pyflow f start
expect_rc "a second session's start exits 1" 1 "$RC"
expect_has "and names the owner" "STOP f is owned by session $TOK" "$OUT"
OUT="$(FLOW_TAKEOVER=1 python3 scripts/flow.py f start 2> /dev/null)"
TOK2="${OUT#OK }"
if [ -n "$TOK2" ] && [ "$TOK2" != "$TOK" ] && [ "OK $TOK2" = "$OUT" ]; then ok "FLOW_TAKEOVER=1 start returns a new token"; else bad "FLOW_TAKEOVER=1 start returns a new token" "$OUT"; fi
if [ "$before" = "$(grep -E '^(ticket|round|attempt)=' .feature-flow/state/flow-f.state)" ]; then ok "and keeps the outstanding phase and counters"; else bad "and keeps the outstanding phase and counters"; fi
OUT="$(FLOW_SESSION="$TOK" python3 scripts/flow.py f next 2> /dev/null)"
expect_has "the old token can no longer drive the flow" "STOP f is owned by another session" "$OUT"
OUT="$(FLOW_SESSION="$TOK2" python3 scripts/flow.py f next 2> /dev/null)"
expect_has "after the takeover a claimed ticket is built again" "BUILD plans/f/tasks/01-a.md 01" "$OUT"
expect_has "and reset to open" "Status: open" "$(cat plans/f/tasks/01-a.md)"
expect_has "and the attempt counts" "attempt=2" "$(cat .feature-flow/state/flow-f.state)"

D="$(flowrepo pyflow_handoff)"
cd "$D" || exit 1
git rm -q plans/f/tasks/03-c.md plans/f/tasks/04-d.md; git commit -qm "two tickets"
export FLOW_TICKETS_PER_SESSION=1
pyflow f start; export FLOW_SESSION="${OUT#OK }"
pyflow f next; resolve plans/f/tasks/01-a.md; pyflow f next
printf 'REVIEW: PASS\n' > .git/reply.txt; pyflow f verdict .git/reply.txt
pyflow f next
expect_rc "after FLOW_TICKETS_PER_SESSION tickets next exits 0" 0 "$RC"
expect_has "and hands off" "HANDOFF /feature-flow f" "$OUT"
expect_has "and logs it" ",HANDOFF" "$(cat .feature-flow/state/flow-f.log)"
expect_rc "the owner is cleared" 1 "$(grep -cx "owner=" .feature-flow/state/flow-f.state)"
pyflow f start; export FLOW_SESSION="${OUT#OK }"
pyflow f next
expect_has "the next session gets the held-back BUILD" "BUILD plans/f/tasks/02-b.md 02 $(git rev-parse HEAD)" "$OUT"
resolve plans/f/tasks/02-b.md; pyflow f next; pyflow f verdict .git/reply.txt; pyflow f next
expect_has "on the last ticket it is DONE, not HANDOFF" "DONE f is complete" "$OUT"
expect_rc "and DONE clears the owner" 1 "$(grep -cx "owner=" .feature-flow/state/flow-f.state)"
unset FLOW_SESSION FLOW_TICKETS_PER_SESSION

D="$(flowrepo pyflow_invoke)"
cd "$D" || exit 1
pyflow f next; resolve plans/f/tasks/01-a.md; pyflow f next
printf 'REVIEW: PASS\n' > .git/reply.txt; pyflow f verdict .git/reply.txt
OUT="$(FLOW_TICKETS_PER_SESSION=1 FLOW_INVOKE='$feature-flow' python3 scripts/flow.py f next 2> /dev/null)"
expect_has "FLOW_INVOKE sets the line to type" 'HANDOFF $feature-flow f' "$OUT"

D="$(flowrepo pyflow_relay)"
cd "$D" || exit 1
export FLOW_RELAY=1
pyflow f start; export FLOW_SESSION="${OUT#OK }"
pyflow f next
expect_has "relay: the first session gets BUILD" "BUILD plans/f/tasks/01-a.md 01" "$OUT"
resolve plans/f/tasks/01-a.md
pyflow f next
expect_has "relay: after the BUILD it hands off" "HANDOFF /feature-flow f" "$OUT"
pyflow f start; export FLOW_SESSION="${OUT#OK }"
pyflow f next
expect_has "relay: the next session gets REVIEW" "REVIEW plans/f/tasks/01-a.md 01" "$OUT"
printf 'REVIEW: PASS\n' > .git/reply.txt; pyflow f verdict .git/reply.txt
pyflow f next
expect_has "relay: after the REVIEW it hands off" "HANDOFF /feature-flow f" "$OUT"
seq="$(cut -d, -f3 .feature-flow/state/flow-f.log | grep -E '^(BUILD|REVIEW|HANDOFF)$' | tr '\n' ' ')"
expect_has "relay: the log shows BUILD, HANDOFF, REVIEW, HANDOFF" "BUILD HANDOFF REVIEW HANDOFF " "$seq"
pyflow f start; export FLOW_SESSION="${OUT#OK }"
pyflow f next
expect_has "relay: the third session gets the next ticket" "BUILD plans/f/tasks/02-b.md 02" "$OUT"
unset FLOW_SESSION FLOW_RELAY
cd "$ROOT" || exit 1

echo "flow.py, guides and prompt"
for g in build review plan show brief plan-review; do
  if [ -f "$ROOT/guides/$g.md" ]; then ok "guides/$g.md exists"; else bad "guides/$g.md exists"; fi
  n="$(grep -cE '\$ARGUMENTS|(^|[^$])/feature-flow|\$feature-flow' "$ROOT/guides/$g.md")"
  expect_rc "guides/$g.md names no runtime's skill invocation" 0 "$n"
done
expect_has "the plan guide ends with a plan verdict" "PLAN: READY" "$(cat "$ROOT/guides/plan.md")"
expect_has "the plan review guide ends with a review verdict" "PLAN-REVIEW: PASS" "$(cat "$ROOT/guides/plan-review.md")"
expect_has "the plan guide writes into the draft folder" ".feature-flow/state/draft/" "$(cat "$ROOT/guides/plan.md")"
if [ -f "$ROOT/guides/templates/ticket.md" ]; then ok "guides/templates/ticket.md exists"; else bad "guides/templates/ticket.md exists"; fi
D="$(flowrepo pyflow_prompt)"
cd "$D" || exit 1
mkdir -p .feature-flow
cp -R "$ROOT/guides" "$ROOT/agents" .feature-flow/
git add -A; git commit -qm "install guides"
pyflow f prompt
expect_rc "prompt with nothing pending exits 2" 2 "$RC"
SHA="$(git rev-parse HEAD)"
pyflow f next
pyflow f prompt
expect_rc "prompt after BUILD exits 0" 0 "$RC"
expect_has "the build prompt has the builder role" "You are the builder. You build one ticket, then stop." "$OUT"
expect_has "and the build guide" "Lazy about the solution, never about reading." "$OUT"
expect_has "and the ticket" "plans/f/tasks/01-a.md" "$OUT"
expect_lacks "and no frontmatter" "name: ticket-builder" "$OUT"
for ph in '<ticket>' '<NN>' '<sha>' '<feature>'; do expect_lacks "no $ph placeholder is left" "$ph" "$OUT"; done
resolve plans/f/tasks/01-a.md
pyflow f next
pyflow f prompt
expect_has "the review prompt has the reviewer role" "You are the reviewer, not the author." "$OUT"
expect_has "and the review guide" "Verdict 1: does it meet the ticket?" "$OUT"
expect_has "and the base sha" "$SHA" "$OUT"
for ph in '<ticket>' '<NN>' '<sha>'; do expect_lacks "no $ph placeholder is left in the review prompt" "$ph" "$OUT"; done
printf 'REVIEW: PASS\n' > .git/reply.txt; pyflow f verdict .git/reply.txt
for t in 02-b 03-c 04-d; do pyflow f next; resolve "plans/f/tasks/$t.md"; pyflow f next; pyflow f verdict .git/reply.txt; done
pyflow f next
expect_has "the run finishes" "DONE" "$OUT"
pyflow f prompt
expect_rc "prompt after DONE exits 2" 2 "$RC"
D="$(flowrepo pyflow_prompt_root)"; cd "$D" || exit 1
cp -R "$ROOT/guides" "$ROOT/agents" .; git add -A; git commit -qm "guides beside scripts"
pyflow f next; pyflow f prompt
expect_has "guides and agents beside scripts/ are found too" "You are the builder." "$OUT"
D="$(flowrepo pyflow_prompt_other)"; cd "$D" || exit 1
mkdir -p guides agents .feature-flow; echo "the user's own notes" > guides/notes.md; echo "x" > agents/mine.md
cp -R "$ROOT/guides" "$ROOT/agents" .feature-flow/; git add -A; git commit -qm "own guides/ and agents/ folders"
pyflow f next; pyflow f prompt
expect_rc "an unrelated guides/ or agents/ folder does not hide .feature-flow/" 0 "$RC"
expect_has "and the installed role is used" "You are the builder." "$OUT"
cd "$ROOT" || exit 1

echo "feature-flow skills"
CS_SKILL="$ROOT/skills/feature-flow/SKILL.md"
head6="$(sed -n 1,6p "$CS_SKILL")"
expect_has "the Claude skill is named feature-flow" "name: feature-flow" "$head6"
expect_has "it has an argument hint" "argument-hint:" "$head6"
expect_has "and runs only when named" "disable-model-invocation: true" "$head6"
for a in PLAN BUILD REVIEW DONE STOP HANDOFF prompt; do
  if grep -q "$a" "$CS_SKILL"; then ok "the Claude skill handles $a"; else bad "the Claude skill handles $a"; fi
done
expect_rc "it never runs the gate or the floor guard itself" 0 "$(grep -cE 'python3 scripts/(gate|floor-guard)\.py' "$CS_SKILL")"
if [ "$(grep -c 'Done when' "$CS_SKILL")" -le 2 ]; then ok "it holds no copy of the build or review protocol"; else bad "it holds no copy of the build or review protocol"; fi
if [ "$(wc -l < "$CS_SKILL")" -lt 90 ]; then ok "it is under 90 lines"; else bad "it is under 90 lines"; fi
CX_SKILL="$ROOT/adapters/codex/feature-flow/SKILL.md"
head4="$(sed -n 1,4p "$CX_SKILL")"
expect_has "the Codex skill is named feature-flow" "name: feature-flow" "$head4"
expect_has "with a quoted description" 'description: "' "$head4"
expect_lacks "and no Claude-only header" "disable-model-invocation" "$head4"
expect_lacks "and no argument hint" "argument-hint" "$head4"
expect_rc "its openai.yaml makes it explicit only" 1 "$(grep -c 'allow_implicit_invocation: false' "$ROOT/adapters/codex/feature-flow/agents/openai.yaml")"
if grep -q "FLOW_INVOKE='\$feature-flow'" "$CX_SKILL"; then ok "it hands off with \$feature-flow"; else bad "it hands off with \$feature-flow"; fi
expect_rc "it never says /feature-flow or \$ARGUMENTS" 0 "$(grep -cE '(^|[^$])/feature-flow|\$ARGUMENTS' "$CX_SKILL")"
mode="$(grep -E '^Codex mode: (subagents|relay)$' "$ROOT/plans/interactive-flow/tasks/02-probe-codex-sessions.md" | sed 's/^Codex mode: //')"
relay="$(grep -c 'FLOW_RELAY=1' "$CX_SKILL")"
if { [ "$mode" = subagents ] && [ "$relay" = 0 ]; } || { [ "$mode" = relay ] && [ "$relay" -ge 1 ]; }; then ok "its mode matches ticket 02 ($mode)"; else bad "its mode matches ticket 02 ($mode)"; fi
for n in Claude Codex; do
  s="$CS_SKILL"; [ "$n" = Claude ] || s="$CX_SKILL"
  for w in plan-prompt plan-review-prompt plan-accept feature-planner plan-reviewer guides/brief.md; do
    if grep -q -- "$w" "$s"; then ok "the $n skill plans with $w"; else bad "the $n skill plans with $w"; fi
  done
done
expect_has "the Codex planner never sees the conversation" 'task_name="feature_planner", fork_turns="none"' "$(cat "$CX_SKILL")"
for n in Claude Codex; do
  s="$CS_SKILL"; [ "$n" = Claude ] || s="$CX_SKILL"
  expect_rc "the $n skill writes nothing under .git" 0 "$(grep -cE '(>|-o) *\.git/' "$s")"
  if grep -q 'verdict \.feature-flow/state/flow-review-<feature>\.txt' "$s"; then ok "the $n skill saves the review reply in .feature-flow/state/"; else bad "the $n skill saves the review reply in .feature-flow/state/"; fi
done

echo "smoke-real.sh, prepare only"
SM="$ROOT/tests/smoke-real.sh"
mkdir -p "$TMP/nobin"
P="$TMP/prep_codex"
out="$(env PATH="$TMP/nobin:/usr/bin:/bin" FLOW_AGENT=codex bash "$SM" --prepare "$P" 2>&1)"; rc=$?
expect_rc "--prepare builds the project without any model installed" 0 $rc
expect_has "it says no model was called" "no model was called" "$out"
expect_has "and tells a codex user what to type" 'then type:  $feature-flow hello' "$out"
if [ -f "$P/.agents/skills/feature-flow/SKILL.md" ] && [ -f "$P/.agents/flow-roles/ticket-reviewer.md" ] && [ ! -e "$P/.claude" ]; then ok "the project is installed for codex only"; else bad "the project is installed for codex only"; fi
expect_has "the plan passes the ticket check" "OK: 2 tickets" "$(cd "$P" && python3 scripts/flow-status.py hello --check 2>&1)"
expect_has "and the first ticket is the one that is ready" "01-greet-function.md" "$(cd "$P" && python3 scripts/flow-status.py hello --next 2>&1)"
if [ -z "$(cd "$P" && git status --porcelain)" ] && [ "$(cd "$P" && git rev-list --count HEAD)" = 1 ]; then ok "it is one clean commit"; else bad "it is one clean commit"; fi
env FLOW_AGENT=codex bash "$SM" --prepare "$P" > /dev/null 2>&1; expect_rc "a folder that is not empty is refused" 2 $?
P2="$TMP/prep_claude"
out="$(env PATH="$TMP/nobin:/usr/bin:/bin" bash "$SM" --prepare "$P2" 2>&1)"; rc=$?
expect_rc "--prepare defaults to claude" 0 $rc
expect_has "and tells a claude user what to type" "then type:  /feature-flow hello" "$out"
if [ -f "$P2/.claude/skills/feature-flow/SKILL.md" ] && [ ! -e "$P2/.agents" ]; then ok "the project is installed for claude only"; else bad "the project is installed for claude only"; fi
env RUN_REAL=0 bash "$SM" > /dev/null 2>&1; expect_rc "without RUN_REAL or --prepare nothing runs" 2 $?
env RUN_REAL=1 PATH="$TMP/nobin:/usr/bin:/bin" bash "$SM" > /dev/null 2>&1; expect_rc "RUN_REAL=1 without --interactive runs nothing either" 2 $?
out="$(env FLOW_AGENT=bogus bash "$SM" --prepare "$TMP/prep_bogus" 2>&1)"; rc=$?
expect_rc "an unknown FLOW_AGENT is refused" 2 $rc
expect_has "and the script itself says what is allowed" "FLOW_AGENT must be claude or codex, not bogus" "$out"
if [ ! -e "$TMP/prep_bogus" ]; then ok "and it creates nothing"; else bad "and it creates nothing"; fi
bash "$SM" --prepare > /dev/null 2>&1; expect_rc "--prepare without a folder is refused" 2 $?
env RUN_REAL=0 bash "$SM" --interactive > /dev/null 2>&1; expect_rc "--interactive without RUN_REAL is refused" 2 $?
bash "$SM" --bogus > /dev/null 2>&1; expect_rc "an unknown option is refused" 2 $?
mkdir -p "$TMP/silentbin"
printf '#!/bin/bash\necho "$*" >> "$FAKE_CALLS"\nexit 0\n' > "$TMP/silentbin/claude"; chmod +x "$TMP/silentbin/claude"
out="$(env TMPDIR="$TMP" PATH="$TMP/silentbin:$PATH" FAKE_CALLS="$TMP/silent.calls" RUN_REAL=1 bash "$SM" --interactive 2>&1)"; rc=$?
expect_rc "--interactive: a session that ends without HANDOFF, DONE or STOP exits 1" 1 $rc
expect_has "and says so" "  FAIL  session 1 ended without HANDOFF, DONE or STOP" "$out"
expect_has "and prints the recovery command" "FLOW_TAKEOVER=1 FLOW_TICKETS_PER_SESSION=1 claude " "$out"
expect_rc "and starts no second session" 1 "$(wc -l < "$TMP/silent.calls" | tr -d ' ')"
expect_has "the session is started as a user would type it" '-p /feature-flow hello auto --allowedTools' "$(cat "$TMP/silent.calls")"

echo
echo "$PASS passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
