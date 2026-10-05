#!/bin/bash
# offline tests for the scripts. no network and no real claude: a fake claude stands in.
# usage: bash tests/run.sh
# exit code is the number of failed checks, capped at 1.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP:?}"' EXIT

PASS=0
FAILS=0

ok() { PASS=$((PASS + 1)); echo "  ok    $1"; }
bad() { FAILS=$((FAILS + 1)); echo "  FAIL  $1${2:+ ($2)}"; }
expect_rc() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "exit $3, wanted $2"; fi; }
expect_has() { if printf '%s' "$3" | grep -qF -- "$2"; then ok "$1"; else bad "$1" "missing: $2"; fi; }
expect_lacks() { if printf '%s' "$3" | grep -qF -- "$2"; then bad "$1" "unexpected: $2"; else ok "$1"; fi; }

mkdir -p "$TMP/bin"
cat > "$TMP/bin/claude" << 'FAKE'
#!/bin/bash
prompt="$2"
json=0
prev=""
for a in "$@"; do
  if [ "$prev" = "--output-format" ] && [ "$a" = "json" ]; then json=1; fi
  prev="$a"
done
if [ "$json" = 1 ] && [ -z "${FAKE_INNER:-}" ]; then
  out="$(FAKE_INNER=1 "$0" "$@" 2> /dev/null)"; rc=$?
  jq -n --arg r "$out" --arg c "${FAKE_COST:-0.10}" --argjson e "$([ "$rc" -ne 0 ] && echo true || echo false)" \
    '{type:"result",subtype:"success",is_error:$e,num_turns:3,total_cost_usd:($c|tonumber),result:$r,session_id:"fake"}'
  exit "$rc"
fi
mkdir -p .fake
echo "$*" >> .fake/calls.log
setst() { awk -v s="$1" 'FNR<=20 && !d && /^Status:/ {print "Status: " s; d=1; next} {print}' "$2" > "$2.tmp" && mv "$2.tmp" "$2"; }
commit() { git add -A > /dev/null 2>&1; git commit -qm "$1"; }
case "$prompt" in
  /next-phase*)
    feature="$(echo "$prompt" | awk '{print $2}')"
    t="$(bash scripts/flow-status.sh "$feature" --next 2> /dev/null)" || exit 0
    n="$(basename "$t" .md)"; num="${n%%-*}"
    findings=0; grep -q '^## Review findings' "$t" && findings=1
    case "$FAKE_IMPL" in
      ok) echo "work $num" > "work-$num.txt"; setst resolved "$t"; commit "feat: $num" ;;
      noop) exit 0 ;;
      die_once)
        if [ ! -e .fake/died ]; then touch .fake/died; setst claimed "$t"; exit 1; fi
        echo "work $num" > "work-$num.txt"; setst resolved "$t"; commit "feat: $num" ;;
      tamper_then_fix)
        if [ "$findings" = 0 ]; then sed -i.bak 's/^- x$/- y/' "$t"; else sed -i.bak 's/^- y$/- x/' "$t"; fi
        rm -f "$t.bak"; setst resolved "$t"; commit "feat: $num" ;;
      learn)
        echo "work $num" > "work-$num.txt"
        printf -- '- (%s) a lesson\n' "$num" >> "plans/$feature/learnings.md"
        printf '%s - decided something\n' "$num" >> "plans/$feature/map.md"
        setst resolved "$t"; commit "feat: $num" ;;
      break_smoke) touch BROKEN; setst resolved "$t"; commit "feat: $num" ;;
      fail_test_then_fix)
        if [ "$findings" = 0 ]; then touch FAILING; else rm -f FAILING; fi
        echo "work $num" > "work-$num.txt"; setst resolved "$t"; commit "feat: $num" ;;
      skip_then_fix)
        mkdir -p tests
        if [ "$findings" = 0 ]; then
          printf '@pytest.mark.skip\ndef test_%s():\n    assert True\n' "$num" > "tests/test_$num.py"
        else
          printf 'def test_%s():\n    assert True\n' "$num" > "tests/test_$num.py"
        fi
        setst resolved "$t"; commit "feat: $num" ;;
    esac ;;
  /review-ticket*)
    num="$(echo "$prompt" | awk '{print $3}')"
    echo "SPEC"; echo "- checked"
    case "$FAKE_REVIEW" in
      pass) echo "REVIEW: PASS" ;;
      fail_once)
        if [ ! -e ".fake/reviewed-$num" ]; then
          touch ".fake/reviewed-$num"; echo "1. major x.py: a bug"; echo "REVIEW: FAIL"
        else
          echo "REVIEW: PASS"
        fi ;;
      fail_always) echo "1. major x.py: still a bug"; echo "REVIEW: FAIL" ;;
      noverdict) echo "I am not sure" ;;
      edits) echo "tampered" >> README.md; echo "REVIEW: PASS" ;;
    esac ;;
esac
exit 0
FAKE
chmod +x "$TMP/bin/claude"

ticket() { # dir name status blocked-by [extra header line]
  printf '# %s\n\nType: task\nStatus: %s\nBlocked by: %s\nTest first: no\n%s\n\nbody\n\n## Done when\n\n- x\n\n## Answer\n' \
    "$2" "$3" "$4" "${5:-}" > "$1"
}

newrepo() { # name -> prints the repo dir
  local d="$TMP/$1"
  mkdir -p "$d/scripts" "$d/plans/f/tasks"
  cp "$ROOT"/scripts/*.sh "$d/scripts/"
  (
    cd "$d" || exit 1
    git init -q
    git config user.email t@t
    git config user.name t
    echo ".fake/" >> .git/info/exclude
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

flow() { # repo impl review [extra env...] -> sets OUT and RC
  local d="$1" impl="$2" review="$3"
  shift 3
  mkdir -p "$TMP/home"
  OUT="$(cd "$d" && env PATH="$TMP/bin:$PATH" HOME="$TMP/home" FAKE_IMPL="$impl" FAKE_REVIEW="$review" FLOW_SLEEP=0 "$@" bash scripts/auto-flow.sh f 2>&1)"
  RC=$?
}

echo "flow-status.sh"
D="$(newrepo status)"
S="$D/scripts/flow-status.sh"
cd "$D" || exit 1
out="$(bash "$S" f)"; expect_has "table marks the first ticket READY" "01  open      READY" "$out"
expect_has "table shows blockers" "after 02,03" "$out"
out="$(bash "$S" f --next)"; expect_has "--next prints the lowest ready ticket" "plans/f/tasks/01-a.md" "$out"
out="$(bash "$S" f --counts)"; expect_has "--counts" "total=4 resolved=0 open=4" "$out"
out="$(bash "$S" f --check)"; expect_has "--check passes on a good graph" "OK: 4 tickets" "$out"
out="$(bash "$S" f --mermaid)"; expect_has "--mermaid has nodes" 'T01["01 A"]:::ready' "$out"
expect_has "--mermaid has edges" "T02 --> T04" "$out"
out="$(bash "$S" f --mermaid plain)"; expect_lacks "--mermaid plain has no colours" "classDef" "$out"
bash "$S" f --next > /dev/null; expect_rc "--next exits 0 when something is ready" 0 $?

mkdir -p plans/stuck/tasks plans/done/tasks plans/bad/tasks plans/aws/tasks
ticket plans/stuck/tasks/01-a.md A claimed "—"; ticket plans/stuck/tasks/02-b.md B open "01"
bash "$S" stuck --next > /dev/null 2>&1; expect_rc "--next exits 11 when stuck" 11 $?
ticket plans/done/tasks/01-a.md A resolved "—"; ticket plans/done/tasks/02-b.md B parked "01"
bash "$S" done --next > /dev/null 2>&1; expect_rc "--next exits 10 when complete" 10 $?
ticket plans/aws/tasks/01-a.md A done "—"; ticket plans/aws/tasks/02-b.md B ready-for-agent "01"; ticket plans/aws/tasks/03-c.md C ready-for-human "—"
out="$(bash "$S" aws)"; expect_has "aws status words: done counts as resolved" "01  resolved" "$out"
expect_has "aws status words: ready-for-agent is open and ready" "02  open      READY" "$out"
expect_has "aws status words: ready-for-human waits" "03  waiting" "$out"
ticket plans/bad/tasks/01-a.md A open "03"; ticket plans/bad/tasks/02-b.md B open "01"; ticket plans/bad/tasks/03-c.md C open "02"
ticket plans/bad/tasks/04-d.md D banana "99"; printf '# E\n\nStatus: open\nBlocked by: —\nTest first: maybe\n' > plans/bad/tasks/05-e.md
out="$(bash "$S" bad --check 2>&1)"; rc=$?
expect_rc "--check exits 1 on a bad graph" 1 $rc
expect_has "--check finds the cycle" "part of a dependency cycle" "$out"
expect_has "--check finds a missing blocker" "blocked by 99, which does not exist" "$out"
expect_has "--check finds an unknown status" "unrecognised Status value" "$out"
expect_has "--check finds a missing Done when" "no ## Done when section" "$out"
expect_has "--check finds a bad Test first" "Test first must be yes or no" "$out"
bash "$S" nope --next > /dev/null 2>&1; expect_rc "a missing feature exits 2" 2 $?
mkdir -p .scratch/x/issues; ticket .scratch/x/issues/01-a.md A ready-for-agent "—"
FLOW_DIR=.scratch FLOW_TICKETS=issues bash "$S" x --next > /dev/null; expect_rc "FLOW_DIR and FLOW_TICKETS relocate the tickets" 0 $?

echo "floor-guard.sh"
D="$(newrepo guard)"
cd "$D" || exit 1
G="$D/scripts/floor-guard.sh"
mkdir -p tests src
printf 'def test_a():\n    assert 1 == 1\n' > tests/test_a.py; printf 'x = 1\n' > src/app.py
printf 'fail_under = 80\n' > setup.cfg; printf '{}\n' > .eslintrc.json; printf 'def test_gone():\n    assert True\n' > tests/test_gone.py
ticket plans/f/tasks/02-b.md B open "01" "Floor: allow skip, suppress, empty-catch, threshold, config, test-delete"
git add -A; git commit -qm base; B0="$(git rev-parse HEAD)"
printf 'x = 2\ny = 3\n' > src/app.py; git add -A; git commit -qm clean
bash "$G" f 01 "$B0" > /dev/null; expect_rc "a clean diff passes" 0 $?
B1="$(git rev-parse HEAD)"
printf '@pytest.mark.skip\ndef test_a():\n    assert 1 == 1\n' > tests/test_a.py
printf 'x = 2  # noqa\ntry:\n    y = 1\nexcept Exception: pass\n' > src/app.py
printf 'fail_under = 10\n' > setup.cfg; printf '{"rules": {}}\n' > .eslintrc.json
git add -A; git commit -qm weaken
git rm -q tests/test_gone.py; git commit -qm delete
out="$(bash "$G" f 01 "$B1" 2>&1)"; rc=$?
expect_rc "a weakening diff fails" 1 $rc
expect_has "finds a skipped test" "skip: tests/test_a.py" "$out"
expect_has "finds a silenced check" "suppress: src/app.py" "$out"
expect_has "finds an empty catch" "empty-catch: src/app.py" "$out"
expect_has "finds a lowered threshold" "threshold: setup.cfg" "$out"
expect_has "finds edited lint config" "config: .eslintrc.json" "$out"
expect_has "finds a deleted test" "test-delete: tests/test_gone.py" "$out"
expect_has "warns about fewer assertions" "assertion line(s) removed" "$out"
bash "$G" f 02 "$B1" > /dev/null 2>&1; expect_rc "Floor: allow in the ticket at base lets the diff through" 0 $?
ticket plans/f/tasks/01-a.md A open "—" "Floor: allow skip, suppress, empty-catch, threshold, config, test-delete, ticket-edit"
git add -A; git commit -qm selfallow
out="$(bash "$G" f 01 "$B1" 2>&1)"; rc=$?
expect_rc "a worker cannot excuse itself by adding Floor: allow" 1 $rc
expect_has "and the edit to its own header is reported" "ticket-edit: plans/f/tasks/01-a.md" "$out"
bash "$G" f 99 "$B1" > /dev/null 2>&1; expect_rc "a missing ticket exits 2" 2 $?

echo "floor-guard.sh, protecting the plan"
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
    bash scripts/floor-guard.sh f 01 "$base" > .guard.out 2>&1
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

echo "flow-status.sh, ordering hints"
cd "$TMP" || exit 1
mkdir -p ord/plans/g/tasks
cd ord || exit 1
S="$ROOT/scripts/flow-status.sh"
printf '# A\n\nType: task\nStatus: open\nBlocked by: —\nTest first: no\n\nTicket 02 builds on this.\n\n## Not in this ticket\n\n- ticket 03 is separate\n\n## Done when\n\n- x\n' > plans/g/tasks/01-a.md
printf '# B\n\nType: task\nStatus: open\nBlocked by: 01\nTest first: no\n\nbody\n\n## Done when\n\n- x\n' > plans/g/tasks/02-b.md
printf '# C\n\nType: task\nStatus: open\nBlocked by: 01\nTest first: no\n\nUses the output of ticket 02 directly.\n\n## Done when\n\n- x\n' > plans/g/tasks/03-c.md
printf '# D\n\nType: task\nStatus: open\nBlocked by: 03\nTest first: no\n\nNeeds what tickets 01 and 02 leave behind.\n\n## Done when\n\n- x\n' > plans/g/tasks/04-d.md
out="$(bash "$S" g --check)"; rc=$?
expect_rc "ordering warnings do not fail --check" 0 $rc
expect_has "a ticket that uses another without ordering is warned" "03: mentions ticket 02 but is not ordered against it" "$out"
expect_lacks "mentioning a later ticket that builds on this one is fine" "01: mentions" "$out"
expect_lacks "mentioning an ancestor through the chain is fine" "04: mentions ticket 01" "$out"
expect_has "an ancestor not on any chain is warned" "04: mentions ticket 02 but is not ordered against it" "$out"
mkdir -p plans/h/tasks; cp plans/g/tasks/01-a.md plans/h/tasks/01-a.md
i=0; : > plans/h/learnings.md; while [ "$i" -lt 45 ]; do echo "- (01) lesson $i" >> plans/h/learnings.md; i=$((i + 1)); done
out="$(bash "$S" h --check)"; expect_has "a long learnings.md is flagged" "warning: learnings.md has 45 lines" "$out"

echo "auto-flow.sh"
D="$(newrepo ok)"; flow "$D" ok pass
expect_rc "all tickets resolve" 0 $RC
expect_has "reports completion" "f is complete: 4 ticket(s)" "$OUT"
calls="$(cat "$D/.fake/calls.log")"
expect_has "each ticket gets a review" "/review-ticket f 04" "$calls"
first="$(grep -n 'next-phase' "$D/.fake/calls.log" | head -1)"; expect_has "first session is an implementation" "next-phase f auto" "$first"
order="$(cd "$D" && git log --reverse --format=%s | grep '^feat' | tr '\n' ' ')"
expect_has "tickets land in dependency order" "feat: 01 feat: 02 feat: 03 feat: 04" "$order"

D="$(newrepo review_off)"; flow "$D" ok pass FLOW_REVIEW=off
expect_rc "FLOW_REVIEW=off still completes" 0 $RC
expect_lacks "FLOW_REVIEW=off starts no review" "review-ticket" "$(cat "$D/.fake/calls.log")"

D="$(newrepo noop)"; flow "$D" noop pass
expect_rc "a session that resolves nothing stops the run" 1 $RC
expect_has "says which ticket is unresolved" "01-a is still unresolved after 2 attempt(s)" "$OUT"
n="$(grep -c 'next-phase' "$D/.fake/calls.log")"; expect_rc "and stops after exactly 2 attempts" 2 "$n"

D="$(newrepo die)"; flow "$D" die_once pass
expect_rc "a session that dies after claiming is retried" 0 $RC
expect_has "the stale claim was reset and the run finished" "f is complete" "$OUT"

D="$(newrepo guard_loop)"; flow "$D" skip_then_fix pass
expect_rc "the floor guard sends a ticket back and it recovers" 0 $RC
expect_has "the guard objected" "floor guard sent 01-a back (round 1)" "$OUT"
expect_has "findings were written into the ticket" "## Review findings (round 1, floor guard)" "$(cat "$D/plans/f/tasks/01-a.md")"

D="$(newrepo review_once)"; flow "$D" ok fail_once
expect_rc "a failed review sends the ticket back and it recovers" 0 $RC
expect_has "the reviewer objected" "independent review sent 01-a back (round 1)" "$OUT"
expect_has "review findings were written into the ticket" "a bug" "$(cat "$D/plans/f/tasks/01-a.md")"

D="$(newrepo review_always)"; flow "$D" ok fail_always
expect_rc "a ticket that never passes review stops the run" 1 $RC
expect_has "after the round limit" "still fails the independent review after 3 round(s)" "$OUT"

D="$(newrepo noverdict)"; flow "$D" ok noverdict
expect_rc "a review without a verdict stops the run" 1 $RC
expect_has "says there was no verdict" "no review verdict for 01-a" "$OUT"

D="$(newrepo edits)"; flow "$D" ok edits
expect_rc "a reviewer that edits files stops the run" 1 $RC
expect_has "says what the reviewer did wrong" "the reviewer changed tracked files" "$OUT"

D="$(newrepo dirty)"; echo "stray" >> "$D/README.md"; flow "$D" ok pass
expect_rc "a dirty tree is refused up front" 1 $RC
expect_has "says why" "working tree is not clean" "$OUT"

echo "auto-flow.sh, cost, limits and smoke"
D="$(newrepo cost)"; flow "$D" ok pass FAKE_COST=0.25
expect_rc "a run with cost logging completes" 0 $RC
expect_has "prints the cost of the run" 'cost this run: $2.0000 over 8 session(s)' "$OUT"
log="$(cat "$D/.git/flow-cost-f.log")"
expect_has "the cost log names the ticket and role" "01-a,build" "$log"
expect_has "the cost log records review sessions" "04-d,review" "$log"

D="$(newrepo cost_off)"; flow "$D" ok pass FLOW_COST=off
expect_rc "FLOW_COST=off still completes" 0 $RC
expect_lacks "FLOW_COST=off prints no cost" "cost this run" "$OUT"
if [ ! -e "$D/.git/flow-cost-f.log" ]; then ok "FLOW_COST=off writes no log"; else bad "FLOW_COST=off writes no log"; fi

D="$(newrepo cap)"; flow "$D" ok pass FAKE_COST=0.25 FLOW_MAX_TOTAL_USD=0.5
expect_rc "a total cost cap stops the run" 1 $RC
expect_has "and says why" "total cost cap reached" "$OUT"

D="$(newrepo flags)"
flow "$D" ok pass FLOW_MAX_TURNS=7 FLOW_MODEL=builder-m FLOW_REVIEW_MODEL=review-m "FLOW_CLAUDE_ARGS=--setting-sources project,local"
calls="$(cat "$D/.fake/calls.log")"
build_line="$(grep -- '-p /next-phase' <<< "$calls" | head -1)"
review_line="$(grep -- '-p /review-ticket' <<< "$calls" | head -1)"
expect_has "the turn limit reaches builders" "--max-turns 7" "$build_line"
expect_has "the turn limit reaches reviewers" "--max-turns 7" "$review_line"
expect_has "the builder model is used for building" "--model builder-m" "$build_line"
expect_lacks "and not for reviewing" "builder-m" "$review_line"
expect_has "the review model is used for reviewing" "--model review-m" "$review_line"
expect_has "extra flags are passed through" "--setting-sources project,local" "$build_line"

D="$(newrepo smoke_start)"; flow "$D" ok pass FLOW_SMOKE=false
expect_rc "a failing smoke test refuses to start" 1 $RC
expect_has "and says the base is broken" "smoke test failed before 01-a: the base is already broken" "$OUT"
if [ ! -e "$D/.fake/calls.log" ]; then ok "and spends no session"; else bad "and spends no session"; fi

D="$(newrepo smoke_mid)"
printf '# Commands: f\n\nSmoke: `[ ! -e BROKEN ]`\n' > "$D/plans/f/commands.md"
(cd "$D" && git add -A && git commit -qm smoke)
flow "$D" break_smoke pass
expect_rc "a ticket that breaks the base stops the next ticket" 1 $RC
expect_has "and the smoke test names the ticket that cannot start" "smoke test failed before 02-b" "$OUT"

echo "auto-flow.sh, protecting the plan"
D="$(newrepo loop_tamper)"; flow "$D" tamper_then_fix pass
expect_rc "a worker that weakens its own Done when is sent back and recovers" 0 $RC
expect_has "the guard objected" "floor guard sent 01-a back (round 1)" "$OUT"
expect_has "the findings name the ticket edit" "ticket-edit" "$(cat "$D/plans/f/tasks/01-a.md")"

D="$(newrepo loop_learn)"; flow "$D" learn pass
expect_rc "legitimate edits to map.md and learnings.md pass the guard" 0 $RC
expect_lacks "and nothing is sent back" "back (round" "$OUT"

echo "gate.sh"
D="$(newrepo gate_unit)"
cd "$D" || exit 1
G="$D/scripts/gate.sh"
printf '# Commands: f\n\nBuild: `echo building`\nTest: `echo testing`\nLint: `echo linting`\n' > plans/f/commands.md
out="$(bash "$G" f 2>&1)"; rc=$?
expect_rc "all three commands passing exits 0" 0 $rc
expect_has "it reports the count" "gate: 3 command(s) passed" "$out"
order="$(printf '%s' "$out" | grep -oE 'gate: (Build|Test|Lint):' | tr '\n' ' ')"
expect_has "it runs build, then test, then lint" "gate: Build: gate: Test: gate: Lint:" "$order"
printf '# Commands: f\n\nBuild: `echo building`\nTest: `echo it broke; exit 3`\nLint: `echo linting`\n' > plans/f/commands.md
out="$(bash "$G" f 2>&1)"; rc=$?
expect_rc "a failing command exits 1" 1 $rc
expect_has "it names the failing step" "gate: Test failed" "$out"
expect_has "it shows what the command printed" "it broke" "$out"
expect_lacks "it stops before the later steps" "gate: Lint:" "$out"
printf '# Commands: f\n\nBuild: `<command>`\nTest:\nSmoke: `<x>`\n' > plans/f/commands.md
out="$(bash "$G" f 2>&1)"; rc=$?
expect_rc "placeholders and empty values are skipped" 0 $rc
expect_has "and it says nothing ran" "no commands defined" "$out"
out="$(bash "$G" nofeature 2>&1)"; rc=$?
expect_rc "a feature without commands.md is not an error" 0 $rc
bash "$G" > /dev/null 2>&1; expect_rc "no feature is a usage error" 2 $?

echo "auto-flow.sh, gate and agents"
D="$(newrepo gate_loop)"
printf '# Commands: f\n\nTest: `[ ! -e FAILING ]`\n' > "$D/plans/f/commands.md"
(cd "$D" && git add -A && git commit -qm cmds)
flow "$D" fail_test_then_fix pass
expect_rc "a failing gate sends the ticket back and it recovers" 0 $RC
expect_has "the gate objected" "gate sent 01-a back (round 1)" "$OUT"
expect_has "the findings name the failing command" "gate: Test failed" "$(cat "$D/plans/f/tasks/01-a.md")"

D="$(newrepo gate_off)"
printf '# Commands: f\n\nTest: `[ ! -e FAILING ]`\n' > "$D/plans/f/commands.md"
(cd "$D" && git add -A && git commit -qm cmds)
flow "$D" fail_test_then_fix pass FLOW_GATE=off
expect_rc "FLOW_GATE=off skips the gate" 0 $RC
expect_lacks "and nothing is sent back" "back (round" "$OUT"

agents_installed() { # repo
  mkdir -p "$1/.claude/agents"
  printf -- '---\nname: ticket-builder\n---\n' > "$1/.claude/agents/ticket-builder.md"
  printf -- '---\nname: ticket-reviewer\n---\n' > "$1/.claude/agents/ticket-reviewer.md"
  (cd "$1" && git add -A && git commit -qm agents)
}
D="$(newrepo agents_on)"; agents_installed "$D"; flow "$D" ok pass
calls="$(cat "$D/.fake/calls.log")"
build_line="$(grep -- '-p /next-phase' <<< "$calls" | head -1)"
review_line="$(grep -- '-p /review-ticket' <<< "$calls" | head -1)"
expect_rc "a run with the agents installed completes" 0 $RC
expect_has "an installed builder agent is used for building" "--agent ticket-builder" "$build_line"
expect_has "an installed reviewer agent is used for reviewing" "--agent ticket-reviewer" "$review_line"
expect_lacks "and the reviewer never gets the builder agent" "ticket-builder" "$review_line"
expect_has "the banner says so" "builder agent ticket-builder, reviewer agent ticket-reviewer" "$OUT"

D="$(newrepo agents_absent)"; flow "$D" ok pass
expect_lacks "without agent files no agent flag is passed" "--agent" "$(cat "$D/.fake/calls.log")"

D="$(newrepo agents_off)"; agents_installed "$D"; flow "$D" ok pass FLOW_AGENTS=off
expect_lacks "FLOW_AGENTS=off ignores installed agents" "--agent" "$(cat "$D/.fake/calls.log")"

D="$(newrepo agents_missing)"; flow "$D" ok pass FLOW_AGENTS=on
expect_rc "FLOW_AGENTS=on without the files stops the run" 1 $RC
expect_has "and says which agent is missing" "agent ticket-builder is not installed" "$OUT"

expect_has "every claude session reads stdin from /dev/null" "2" "$(grep -c '< /dev/null' "$ROOT/scripts/auto-flow.sh")"

echo "install.sh"
cd "$TMP" || exit 1
I="$TMP/inst"; mkdir -p "$I/repo" "$I/fresh"
out="$(bash "$ROOT/install.sh" "$I/repo" 2>&1)"; rc=$?
expect_rc "installs into a repo" 0 $rc
for f in .claude/skills/next-phase/SKILL.md .claude/skills/review-ticket/SKILL.md .claude/skills/plan-feature/templates/ticket.md .claude/agents/ticket-builder.md .claude/agents/ticket-reviewer.md scripts/gate.sh scripts/auto-flow.sh scripts/floor-guard.sh scripts/flow-status.sh; do
  if [ -f "$I/repo/$f" ]; then ok "installed $f"; else bad "installed $f"; fi
done
out="$(bash "$ROOT/install.sh" "$I/repo" 2>&1)"
expect_has "a second run adds nothing" "added 0, updated 0" "$out"
echo "my own edit" >> "$I/repo/.claude/skills/run-flow/SKILL.md"
out="$(bash "$ROOT/install.sh" "$I/repo" 2>&1)"
expect_has "a changed file is kept and reported" "kept" "$out"
expect_has "and it still has the user's edit" "my own edit" "$(cat "$I/repo/.claude/skills/run-flow/SKILL.md")"
out="$(bash "$ROOT/install.sh" "$I/repo" --force 2>&1)"
expect_has "--force replaces it" "update" "$out"
expect_lacks "and the edit is gone" "my own edit" "$(cat "$I/repo/.claude/skills/run-flow/SKILL.md")"
bash "$ROOT/install.sh" "$I/fresh" --dry-run > /dev/null 2>&1
if [ -z "$(ls -A "$I/fresh")" ]; then ok "--dry-run writes nothing"; else bad "--dry-run writes nothing"; fi
mkdir -p "$I/repo2"
CLAUDE_HOME="$I/home/.claude" bash "$ROOT/install.sh" "$I/repo2" --user > /dev/null 2>&1
if [ -f "$I/home/.claude/skills/next-phase/SKILL.md" ] && [ -f "$I/home/.claude/agents/ticket-reviewer.md" ]; then ok "--user puts skills and agents in the user folder"; else bad "--user puts skills and agents in the user folder"; fi
if [ -f "$I/repo2/scripts/gate.sh" ] && [ ! -e "$I/repo2/.claude" ]; then ok "--user still puts scripts in the repo and no .claude"; else bad "--user still puts scripts in the repo and no .claude"; fi
bash "$ROOT/install.sh" --nonsense > /dev/null 2>&1; expect_rc "an unknown option is a usage error" 2 $?

echo
echo "$PASS passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
