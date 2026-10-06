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
cat > "$TMP/bin/codex" << 'FAKE'
#!/bin/bash
# stands in for `codex exec`. like the real sandbox it cannot write .git, so it never commits
# (unless FAKE_CODEX_GIT=ok). the final message goes to the -o file; --json prints events as the real one does.
[ "$1" = exec ] || { echo "fake codex: expected exec, got $1" >&2; exit 64; }
shift
prompt="" last="" json=0 sandbox="" model=""
raw="$*"
while [ $# -gt 0 ]; do
  case "$1" in
    --sandbox) sandbox="$2"; shift ;;
    -o) last="$2"; shift ;;
    -m) model="$2"; shift ;;
    -c | -C) shift ;;
    --json) json=1 ;;
    -*) ;;
    *) prompt="$1" ;;
  esac
  shift
done
mkdir -p .fake
n=$(( $(ls .fake/codex-prompt-*.txt 2> /dev/null | wc -l) + 1 ))
printf '%s' "$prompt" > ".fake/codex-prompt-$n.txt"
role=other
case "$prompt" in
  *'$next-phase'*) role=build ;;
  *'$review-ticket'*) role=review ;;
esac
echo "role=$role sandbox=$sandbox model=$model json=$json o=$([ -n "$last" ] && echo y || echo n) args=$(printf '%s' "$raw" | tr '\n' ' ' | cut -c1-200)" >> .fake/codex-calls.log
setst() { awk -v s="$1" 'FNR<=20 && !d && /^Status:/ {print "Status: " s; d=1; next} {print}' "$2" > "$2.tmp" && mv "$2.tmp" "$2"; }
agent_commit() { [ "${FAKE_CODEX_GIT:-}" = ok ] || return 0; git add -A > /dev/null 2>&1; git commit -qm "agent: $1"; }
final="done"
case "$role" in
  build)
    feature="$(printf '%s' "$prompt" | grep -o '\$next-phase [^ ]*' | tail -1 | awk '{print $2}')"
    t="$(bash scripts/flow-status.sh "$feature" --next 2> /dev/null)" || exit 0
    num="$(basename "$t" .md)"; num="${num%%-*}"
    findings=0; grep -q '^## Review findings' "$t" && findings=1
    case "${FAKE_IMPL:-ok}" in
      ok) echo "work $num" > "work-$num.txt"; setst resolved "$t"; agent_commit "$num" ;;
      noop) final="nothing done" ;;
      half) echo "work $num" > "work-$num.txt"; final="stopped halfway" ;;
      skip_then_fix)
        mkdir -p tests
        if [ "$findings" = 0 ]; then
          printf '@pytest.mark.skip\ndef test_%s():\n    assert True\n' "$num" > "tests/test_$num.py"
        else
          printf 'def test_%s():\n    assert True\n' "$num" > "tests/test_$num.py"
        fi
        setst resolved "$t"; agent_commit "$num" ;;
    esac ;;
  review)
    num="$(printf '%s' "$prompt" | grep -o '\$review-ticket [^ ]* [^ ]*' | tail -1 | awk '{print $3}')"
    final="SPEC
- checked"
    case "${FAKE_REVIEW:-pass}" in
      pass) final="$final
REVIEW: PASS" ;;
      fail_once)
        if [ ! -e ".fake/reviewed-$num" ]; then touch ".fake/reviewed-$num"; final="$final
1. major x.py: a bug
REVIEW: FAIL"; else final="$final
REVIEW: PASS"; fi ;;
      fail_always) final="$final
1. major x.py: still a bug
REVIEW: FAIL" ;;
      noverdict) final="I am not sure" ;;
    esac ;;
esac
[ -z "$last" ] || printf '%s\n' "$final" > "$last"
if [ "$json" = 1 ]; then
  [ -z "${FAKE_CODEX_JUNK:-}" ] || printf '%s\n' 'Reading additional input from stdin...'
  printf '%s\n' '{"type":"thread.started","thread_id":"fake"}'
  printf '%s\n' '{"type":"item.completed","item":{"id":"item_0","type":"error","message":"loading hooks from both a and b"}}'
  printf '%s\n' '{"type":"turn.started"}'
  printf '%s\n' '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"decoy: REVIEW: FAIL"}}'
  printf '{"type":"turn.completed","usage":{"input_tokens":%s,"cached_input_tokens":500,"cache_write_input_tokens":0,"output_tokens":%s,"reasoning_output_tokens":10}}\n' "${FAKE_TOKENS_IN:-1000}" "${FAKE_TOKENS_OUT:-100}"
else
  printf '%s\n' "$final"
fi
exit "${FAKE_CODEX_RC:-0}"
FAKE
chmod +x "$TMP/bin/codex"

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
expect_lacks "a claude run prints no codex notes" "does not apply to codex" "$OUT"

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

n="$(grep -F 'claude "${args[@]}"' "$ROOT/scripts/auto-flow.sh" | grep -c -F '< /dev/null')"; expect_rc "every claude session reads stdin from /dev/null" 2 "$n"

echo "auto-flow.sh, codex"
n="$(grep -F 'codex "${args[@]}"' "$ROOT/scripts/auto-flow.sh" | grep -c -F '< /dev/null')"; expect_rc "every codex session reads stdin from /dev/null" 2 "$n"
D="$(newrepo codex_ok)"; flow "$D" ok pass FLOW_AGENT=codex
expect_rc "a codex run resolves every ticket" 0 $RC
expect_has "and reports completion" "f is complete: 4 ticket(s)" "$OUT"
expect_has "the banner says codex" "codex, builder role none, reviewer role none" "$OUT"
expect_has "a codex run says what stops a runaway" "only the run limit, the retries and the review rounds stop" "$OUT"
order="$(cd "$D" && git log --reverse --format=%s | grep -v '^init' | tr '\n' '|')"
expect_has "the loop commits each resolved ticket in dependency order with its title" "feat(f): 01 A|feat(f): 02 B|feat(f): 03 C|feat(f): 04 D|" "$order"
expect_lacks "and the agent committed nothing itself" "agent:" "$order"
if [ -z "$(cd "$D" && git status --porcelain)" ]; then ok "the tree is clean at the end"; else bad "the tree is clean at the end"; fi
if [ ! -e "$D/.fake/calls.log" ]; then ok "no claude session was started"; else bad "no claude session was started"; fi
calls="$(cat "$D/.fake/codex-calls.log")"
prompts="$(cat "$D"/.fake/codex-prompt-*.txt)"
build_line="$(grep 'role=build' <<< "$calls" | head -1)"
review_line="$(grep 'role=review' <<< "$calls" | head -1)"
expect_has "builders run in a workspace-write sandbox" "sandbox=workspace-write" "$build_line"
expect_has "reviewers run in a read-only sandbox" "sandbox=read-only" "$review_line"
expect_has "the last message is written to a file" "o=y" "$review_line"
expect_has "the builder is started with a dollar mention and the feature" '$next-phase f auto' "$prompts"
expect_has "the reviewer gets the feature, the ticket and the base" '$review-ticket f 01 ' "$prompts"
expect_lacks "no slash command is sent to codex" "/next-phase" "$prompts"
n="$(grep -c 'role=build' <<< "$calls")"; expect_rc "one builder session per ticket" 4 "$n"
n="$(grep -c 'role=review' <<< "$calls")"; expect_rc "one review per ticket" 4 "$n"
expect_lacks "the output is the last message, not the event stream" "decoy" "$OUT"
log="$(cat "$D/.git/flow-cost-f.log")"
expect_has "the log has tokens and 0 dollars for a build" '01-a,build,1,0,false,"completed",1000,100' "$log"
expect_has "and for a review" '04-d,review,1,0,false,"completed",1000,100' "$log"
expect_has "the run prints its tokens" "tokens this run: 8000 in, 800 out over 8 session(s)" "$OUT"
expect_lacks "and no dollar figure" "cost this run" "$OUT"
expect_has "the viewer's cost column stays readable: dollars are column 5" "0" "$(awk -F, 'NR == 1 { print $5 }' "$D/.git/flow-cost-f.log")"
n="$(awk -F, '$5 != 0' "$D/.git/flow-cost-f.log" | wc -l | tr -d ' ')"; expect_rc "and every dollar figure is 0" 0 "$n"
expect_has "json events are requested when jq is there" "json=1" "$calls"

D="$(newrepo codex_cost_off)"; flow "$D" ok pass FLOW_AGENT=codex FLOW_COST=off
calls="$(cat "$D/.fake/codex-calls.log")"
expect_rc "FLOW_COST=off still completes under codex" 0 $RC
expect_has "and asks for no event stream" "json=0" "$calls"
expect_lacks "nor for any" "json=1" "$calls"
if [ ! -e "$D/.git/flow-cost-f.log" ]; then ok "and writes no log"; else bad "and writes no log"; fi
expect_lacks "and prints no token total" "tokens this run" "$OUT"

D="$(newrepo codex_flags)"
flow "$D" ok pass FLOW_AGENT=codex FLOW_MODEL=builder-m FLOW_REVIEW_MODEL=review-m "FLOW_CODEX_ARGS=-c foo=bar" FLOW_MAX_TURNS=7 FLOW_MAX_BUDGET_USD=1 FLOW_MAX_TOTAL_USD=0.001 FLOW_ALLOWED_TOOLS=Read
calls="$(cat "$D/.fake/codex-calls.log")"
build_line="$(grep 'role=build' <<< "$calls" | head -1)"
review_line="$(grep 'role=review' <<< "$calls" | head -1)"
expect_has "the builder model reaches codex" "model=builder-m" "$build_line"
expect_lacks "and not the reviewer" "builder-m" "$review_line"
expect_has "the review model reaches codex" "model=review-m" "$review_line"
expect_has "extra flags are passed through" "-c foo=bar" "$build_line"
for f in max-turns max-budget allowedTools; do expect_lacks "claude's --$f is never sent to codex" "$f" "$calls"; done
expect_rc "a dollar cap that codex cannot report does not stop the run" 0 $RC
expect_has "and the run says the total cap does not apply" "FLOW_MAX_TOTAL_USD does not apply to codex" "$OUT"
expect_has "that the turn limit is ignored" "FLOW_MAX_TURNS is ignored" "$OUT"
expect_has "that the budget limit is ignored" "FLOW_MAX_BUDGET_USD is ignored" "$OUT"
expect_has "that the tool list is ignored" "FLOW_ALLOWED_TOOLS is ignored" "$OUT"

D="$(newrepo codex_roles)"; mkdir -p "$D/.agents/flow-roles"
printf 'You are the BUILDER role text.\n' > "$D/.agents/flow-roles/ticket-builder.md"
printf 'You are the REVIEWER role text.\n' > "$D/.agents/flow-roles/ticket-reviewer.md"
(cd "$D" && git add -A && git commit -qm roles)
flow "$D" ok pass FLOW_AGENT=codex
expect_rc "a codex run with the role files completes" 0 $RC
expect_has "the banner names the roles" "codex, builder role ticket-builder, reviewer role ticket-reviewer" "$OUT"
b="$(cat "$D/.fake/codex-prompt-1.txt")"; r="$(cat "$D/.fake/codex-prompt-2.txt")"
[ "$(head -1 <<< "$b")" = "You are the BUILDER role text." ] && ok "the builder prompt starts with the builder role" || bad "the builder prompt starts with the builder role"
[ "$(tail -1 <<< "$b")" = '$next-phase f auto' ] && ok "and ends with the skill mention" || bad "and ends with the skill mention"
[ "$(head -1 <<< "$r")" = "You are the REVIEWER role text." ] && ok "the reviewer prompt starts with the reviewer role" || bad "the reviewer prompt starts with the reviewer role"
expect_lacks "and never carries the builder's" "BUILDER" "$r"
D="$(newrepo codex_roles_off)"; mkdir -p "$D/.agents/flow-roles"
printf 'You are the BUILDER role text.\n' > "$D/.agents/flow-roles/ticket-builder.md"
printf 'You are the REVIEWER role text.\n' > "$D/.agents/flow-roles/ticket-reviewer.md"
(cd "$D" && git add -A && git commit -qm roles)
flow "$D" ok pass FLOW_AGENT=codex FLOW_AGENTS=off
[ "$(cat "$D/.fake/codex-prompt-1.txt")" = '$next-phase f auto' ] && ok "FLOW_AGENTS=off sends the bare prompt" || bad "FLOW_AGENTS=off sends the bare prompt"
expect_has "and the banner shows no roles" "builder role none, reviewer role none" "$OUT"
D="$(newrepo codex_roles_missing)"; flow "$D" ok pass FLOW_AGENT=codex FLOW_AGENTS=on
expect_rc "FLOW_AGENTS=on without the role files stops the run" 1 $RC
expect_has "and says which one is missing" "agent ticket-builder is not installed" "$OUT"
D="$(newrepo codex_no_roles)"; flow "$D" ok pass FLOW_AGENT=codex
[ "$(cat "$D/.fake/codex-prompt-1.txt")" = '$next-phase f auto' ] && ok "without role files the prompt is bare" || bad "without role files the prompt is bare"

D="$(newrepo codex_review_once)"; flow "$D" ok fail_once FLOW_AGENT=codex
expect_rc "a failed codex review sends the ticket back and it recovers" 0 $RC
expect_has "the reviewer objected" "independent review sent 01-a back (round 1)" "$OUT"
expect_has "the findings from the last message reach the ticket" "a bug" "$(cat "$D/plans/f/tasks/01-a.md")"
order="$(cd "$D" && git log --reverse --format=%s | tr '\n' '|')"
expect_has "the fix is committed by the loop again" "feat(f): 01 A|chore(f): 01 review findings, round 1|feat(f): 01 A|" "$order"
D="$(newrepo codex_review_always)"; flow "$D" ok fail_always FLOW_AGENT=codex
expect_rc "a ticket that never passes a codex review stops the run" 1 $RC
expect_has "after the round limit" "still fails the independent review after 3 round(s)" "$OUT"
D="$(newrepo codex_noverdict)"; flow "$D" ok noverdict FLOW_AGENT=codex
expect_rc "a codex review without a verdict stops the run" 1 $RC
expect_has "and says so" "no review verdict for 01-a" "$OUT"
D="$(newrepo codex_guard)"; flow "$D" skip_then_fix pass FLOW_AGENT=codex
expect_rc "the floor guard still catches a weakened test under codex and the ticket recovers" 0 $RC
expect_has "the guard objected" "floor guard sent 01-a back (round 1)" "$OUT"

D="$(newrepo codex_noop)"; flow "$D" noop pass FLOW_AGENT=codex
expect_rc "a codex session that resolves nothing stops the run" 1 $RC
expect_has "after the attempt limit" "01-a is still unresolved after 2 attempt(s)" "$OUT"
expect_has "naming codex when it exits" "unresolved" "$OUT"
expect_rc "and nothing was committed" 1 "$(cd "$D" && git log --oneline | wc -l | tr -d ' ')"
D="$(newrepo codex_half)"; flow "$D" half pass FLOW_AGENT=codex
expect_rc "a session that leaves its ticket open stops the run" 1 $RC
expect_lacks "and its half done work is never committed" "feat(f)" "$(cd "$D" && git log --format=%s)"
D="$(newrepo codex_selfcommit)"; flow "$D" ok pass FLOW_AGENT=codex FAKE_CODEX_GIT=ok
expect_rc "an agent that can commit itself works too" 0 $RC
order="$(cd "$D" && git log --reverse --format=%s | tr '\n' '|')"
expect_has "its commits are kept" "agent: 01|agent: 02|agent: 03|agent: 04|" "$order"
expect_lacks "and the loop adds none" "feat(f)" "$order"
D="$(newrepo codex_hook)"; printf '#!/bin/sh\nexit 1\n' > "$D/.git/hooks/pre-commit"; chmod +x "$D/.git/hooks/pre-commit"
flow "$D" ok pass FLOW_AGENT=codex
expect_rc "a commit the loop cannot make stops the run" 1 $RC
expect_has "and says why" "could not commit 01-a for codex" "$OUT"

D="$(newrepo codex_nonzero)"; flow "$D" ok pass FLOW_AGENT=codex FAKE_CODEX_RC=3
expect_has "a non zero exit is reported by agent name" "codex exited non zero on attempt 1" "$OUT"
expect_rc "but the ticket file still decides, so the run completes" 0 $RC
expect_has "and the log marks the session as an error" ',true,"completed"' "$(cat "$D/.git/flow-cost-f.log")"

D="$(newrepo codex_junk)"; flow "$D" ok pass FLOW_AGENT=codex FAKE_CODEX_JUNK=1
expect_rc "lines in the event stream that are not json are ignored" 0 $RC
expect_has "and the tokens are still counted" "tokens this run: 8000 in, 800 out over 8 session(s)" "$OUT"
D="$(newrepo codex_claude_files)"; agents_installed "$D"; flow "$D" ok pass FLOW_AGENT=codex
expect_has "a codex run never takes claude's agent files as its roles" "builder role none, reviewer role none" "$OUT"
[ "$(cat "$D/.fake/codex-prompt-1.txt")" = '$next-phase f auto' ] && ok "and sends the bare prompt" || bad "and sends the bare prompt"
D="$(newrepo claude_codex_files)"; mkdir -p "$D/.agents/flow-roles"
printf 'You are the BUILDER role text.\n' > "$D/.agents/flow-roles/ticket-builder.md"; printf 'You are the REVIEWER role text.\n' > "$D/.agents/flow-roles/ticket-reviewer.md"
(cd "$D" && git add -A && git commit -qm roles); flow "$D" ok pass
expect_has "a claude run never takes codex's role files as its agents" "builder agent none, reviewer agent none" "$OUT"
D="$(newrepo agent_bogus)"; flow "$D" ok pass FLOW_AGENT=bogus
expect_rc "an unknown FLOW_AGENT stops the run" 1 $RC
expect_has "and says what is allowed" "FLOW_AGENT must be claude or codex, not bogus" "$OUT"
mkdir -p "$TMP/nobin"; D="$(newrepo codex_missing)"
OUT="$(cd "$D" && env PATH="$TMP/nobin:/usr/bin:/bin" HOME="$TMP/home" FLOW_AGENT=codex bash scripts/auto-flow.sh f 2>&1)"; RC=$?
expect_rc "codex missing from PATH stops the run" 1 $RC
expect_has "and says so" "codex CLI not found" "$OUT"
mkdir -p "$TMP/onlyclaude" "$TMP/onlycodex"
cp "$TMP/bin/claude" "$TMP/onlyclaude/claude"; cp "$TMP/bin/codex" "$TMP/onlycodex/codex"
D="$(newrepo codex_with_claude_only)"
OUT="$(cd "$D" && env PATH="$TMP/onlyclaude:/usr/bin:/bin" HOME="$TMP/home" FLOW_AGENT=codex bash scripts/auto-flow.sh f 2>&1)"; RC=$?
expect_rc "FLOW_AGENT=codex with only claude installed stops the run" 1 $RC
expect_has "and names codex as the missing one" "codex CLI not found" "$OUT"
D="$(newrepo claude_with_codex_only)"
OUT="$(cd "$D" && env PATH="$TMP/onlycodex:/usr/bin:/bin" HOME="$TMP/home" bash scripts/auto-flow.sh f 2>&1)"; RC=$?
expect_rc "the default agent with only codex installed stops the run" 1 $RC
expect_has "and names claude as the missing one" "claude CLI not found" "$OUT"
D="$(newrepo claude_explicit)"; flow "$D" ok pass FLOW_AGENT=claude
expect_rc "FLOW_AGENT=claude is the default made explicit" 0 $RC
if [ -e "$D/.fake/calls.log" ] && [ ! -e "$D/.fake/codex-calls.log" ]; then ok "and starts claude, not codex"; else bad "and starts claude, not codex"; fi
expect_lacks "a claude run prints no codex notes" "codex" "$OUT"

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
for f in .claude/skills/show-flow/SKILL.md scripts/flow-view.sh scripts/flow-view.html; do
  if [ -f "$I/repo/$f" ]; then ok "installed $f"; else bad "installed $f"; fi
done

echo "adapters/codex/skill.awk, one rule at a time"
XF="$ROOT/adapters/codex/skill.awk"
SKILLS="next-phase review-ticket plan-feature"
xf() { awk -v emit="$1" -v skills="$SKILLS" -f "$XF" "$2"; }
U="$TMP/xf"; mkdir -p "$U"
printf -- '---\nname: demo\ndescription: Does a thing: with a colon and "quotes". Second sentence.\nargument-hint: "[a] [b]"\nargument-extra: x\n  continued line\ndisable-model-invocation: true\n---\n\nWork on `$ARGUMENTS` in plans/$ARGUMENTS/ now.\n' > "$U/a.md"
out="$(xf skill "$U/a.md")"
expect_has "frontmatter keeps the name" "name: demo" "$out"
expect_has "the description is quoted and its inner quotes are escaped" 'description: "Does a thing: with a colon and \"quotes\". Second sentence."' "$out"
expect_lacks "argument-hint is dropped" "argument-hint" "$out"
expect_lacks "disable-model-invocation is dropped" "disable-model-invocation" "$out"
expect_has "an unknown key is kept" "argument-extra: x" "$out"
expect_has "and its continuation line too" "  continued line" "$out"
expect_has '$ARGUMENTS becomes <arguments>, also inside a path' 'Work on `<arguments>` in plans/<arguments>/ now.' "$out"
expect_has "a skill that uses arguments says what they are" 'stands for the text the user typed after `$demo`' "$out"
expect_lacks 'and no $ARGUMENTS is left' 'ARGUMENTS' "$out"
printf -- '---\nname: plain\ndescription: No arguments here.\n---\n\nJust text.\n' > "$U/b.md"
out="$(xf skill "$U/b.md")"
expect_lacks "a skill without arguments gets no note" "stands for" "$out"
expect_has "and keeps its body" "Just text." "$out"
printf -- '---\nname: m\ndescription: d\n---\n\nrun /next-phase now\nin skills/next-phase/SKILL.md\nnot /next-phase-extra\n(/review-ticket) and `/plan-feature`\nhttps://x.example/plan-feature\nContinue with /clear then /next-phase f\n' > "$U/c.md"
out="$(xf skill "$U/c.md")"
expect_has "a slash mention becomes a dollar mention" 'run $next-phase now' "$out"
expect_has "a path is left alone" "in skills/next-phase/SKILL.md" "$out"
expect_has "a longer word is left alone" "not /next-phase-extra" "$out"
expect_has "a mention in brackets and in code is changed" '($review-ticket) and `$plan-feature`' "$out"
expect_has "a url is left alone" "https://x.example/plan-feature" "$out"
expect_has "/clear becomes a plain phrase" 'Continue with a fresh session then $next-phase f' "$out"
printf -- '---\nname: m\ndescription: d\n---\n\nFollow the conventions (CLAUDE.md, `.claude/rules/`).\nRead CLAUDE.md and also AGENTS.md here.\nAny attribution rule in CLAUDE.md.\n' > "$U/d.md"
out="$(xf skill "$U/d.md")"
expect_has "CLAUDE.md with .claude/rules becomes AGENTS.md" "conventions (AGENTS.md)." "$out"
expect_has "a line that already names AGENTS.md is left alone" "Read CLAUDE.md and also AGENTS.md here." "$out"
expect_has "any other CLAUDE.md becomes AGENTS.md" "attribution rule in AGENTS.md." "$out"
printf -- '---\nname: m\ndescription: d\n---\n\n```\n  claude -p "/review-ticket <feature> NN <base>" --agent ticket-reviewer --allowedTools "Read" < /dev/null\n```\n\n(Leave out `--agent ticket-reviewer` if the agent file is not installed.)\n\nUse the commit you noted in Step 5. Leave out `--agent ticket-reviewer` if not installed.\n- **Auto**: commit the code, the ticket and the map together. Never push.\n' > "$U/e.md"
out="$(xf skill "$U/e.md")"
expect_has "the review command is rewritten and keeps its indent and arguments" "  { cat .agents/flow-roles/ticket-reviewer.md; echo; echo '\$review-ticket <feature> NN <base>'; } | codex exec --sandbox read-only -" "$out"
expect_lacks "no claude command is left" "claude -p" "$out"
expect_lacks "the leave-out sentences are gone" "Leave out" "$out"
expect_has "the sandbox warning follows the commit sentence" "Use the commit you noted in Step 5. This starts a new Codex session" "$out"
expect_has "the auto commit line says what to do when git is refused" "leave the changes uncommitted and say so: the loop commits them for you." "$out"
n="$(printf '%s\n' "$out" | awk '/^$/ { b++; if (b > 1) c++ } !/^$/ { b = 0 } END { print c + 0 }')"; expect_rc "dropping the parenthesis line leaves no double blank line" 0 "$n"
printf -- '---\nname: y\ndescription: Short one. Then more words that follow.\nargument-hint: "[feature] [auto]"\ndisable-model-invocation: true\n---\n\nbody\n' > "$U/f.md"
out="$(xf yaml "$U/f.md")"
expect_has "yaml: display name" 'display_name: "y"' "$out"
expect_has "yaml: short description is the first sentence" 'short_description: "Short one"' "$out"
expect_has "yaml: default prompt carries the argument hint" 'default_prompt: "Use $y [feature] [auto]"' "$out"
expect_has "yaml: explicit only when the skill disables model invocation" "allow_implicit_invocation: false" "$out"
printf -- '---\nname: z\ndescription: %s\n---\n\nbody\n' "$(printf 'word %.0s' $(seq 1 60))" > "$U/g.md"
out="$(xf yaml "$U/g.md")"
n="$(printf '%s\n' "$out" | grep 'short_description' | awk -F'"' '{print length($2)}')"
if [ "$n" -le 120 ] && [ "$n" -gt 100 ]; then ok "yaml: a long description is cut at a word within 120 characters"; else bad "yaml: a long description is cut at a word within 120 characters" "length $n"; fi
printf -- '---\nname: m\ndescription: d\n---\n\nRun it: `bash scripts/auto-flow.sh <feature>` or bash scripts/auto-flow.sh f\nRun the script with the Bash tool in the background so it is not cut off.\n' > "$U/loop.md"
out="$(xf skill "$U/loop.md")"
expect_has "the loop is started with codex as its agent" 'Run it: `FLOW_AGENT=codex bash scripts/auto-flow.sh <feature>` or FLOW_AGENT=codex bash scripts/auto-flow.sh f' "$out"
expect_has "and the sandbox warning follows the run instruction" "so it is not cut off. It starts new Codex sessions, which need the network" "$out"
expect_lacks "a mention of the loop without the run instruction gets no warning" "outside the sandbox" "$(xf skill "$U/c.md")"
expect_lacks "yaml: no policy block without disable-model-invocation" "policy" "$(xf yaml "$U/b.md")"
printf -- '---\nname: v\ndescription: d\ndisable-model-invocation: false\n---\n\nbody\n' > "$U/v.md"
expect_lacks "yaml: no policy block when disable-model-invocation is false" "policy" "$(xf yaml "$U/v.md")"
printf -- '---\nname: r\ndescription: d\ntools:\n- Read\n- Bash\nmodel: inherit\n---\n\nYou are the reviewer.\n\nFollow the `review-ticket` skill.\n' > "$U/h.md"
out="$(xf role "$U/h.md")"
expect_has "role: the body is kept" "You are the reviewer." "$out"
expect_lacks "role: the frontmatter is gone" "tools:" "$out"
expect_lacks "role: nothing before the first line" "---" "$out"
[ "$(printf '%s\n' "$out" | head -1)" = "You are the reviewer." ] && ok "role: starts with the first sentence, no blank line" || bad "role: starts with the first sentence, no blank line"

echo "install.sh, codex"
C="$TMP/codex"; mkdir -p "$C/repo" "$C/fresh" "$C/home"
SKILLS_BEFORE="$(cat "$ROOT"/skills/*/SKILL.md "$ROOT"/agents/*.md | cksum)"
printf 'my own instructions\n' > "$C/repo/AGENTS.md"
out="$(bash "$ROOT/install.sh" "$C/repo" --agent codex 2>&1)"; rc=$?
expect_rc "--agent codex installs" 0 $rc
expect_has "it says which agent" "(codex)" "$out"
expect_has "it points at the Codex invocation" 'next: $plan-feature' "$out"
expect_lacks "and not at the Claude one" "/plan-feature <feature-name> in Claude Code" "$out"
missing=""
for s in architect-review automation-design next-phase plan-feature review-ticket run-flow show-flow; do
  for f in SKILL.md agents/openai.yaml; do [ -f "$C/repo/.agents/skills/$s/$f" ] || missing="$missing $s/$f"; done
done
if [ -z "$missing" ]; then ok "every skill gets a SKILL.md and an agents/openai.yaml"; else bad "every skill gets a SKILL.md and an agents/openai.yaml" "$missing"; fi
if cmp -s "$ROOT/skills/plan-feature/templates/ticket.md" "$C/repo/.agents/skills/plan-feature/templates/ticket.md"; then ok "other skill files are copied as they are"; else bad "other skill files are copied as they are"; fi
for f in .agents/flow-roles/ticket-builder.md .agents/flow-roles/ticket-reviewer.md scripts/gate.sh scripts/auto-flow.sh; do
  if [ -f "$C/repo/$f" ]; then ok "codex installed $f"; else bad "codex installed $f"; fi
done
if [ ! -e "$C/repo/.claude" ]; then ok "--agent codex writes no .claude"; else bad "--agent codex writes no .claude"; fi
[ "$(cat "$C/repo/AGENTS.md")" = "my own instructions" ] && ok "an existing AGENTS.md is never touched" || bad "an existing AGENTS.md is never touched"
[ "$(cat "$ROOT"/skills/*/SKILL.md "$ROOT"/agents/*.md | cksum)" = "$SKILLS_BEFORE" ] && ok "installing never changes the sources" || bad "installing never changes the sources"

CS="$C/repo/.agents/skills"
n="$(grep -rlE '^(argument-hint|disable-model-invocation):' "$CS" | wc -l | tr -d ' ')"; expect_rc "no installed skill keeps a Claude only frontmatter key" 0 "$n"
bad_names=""
for s in "$CS"/*/; do
  s="$(basename "$s")"
  [ "$(sed -n 2p "$CS/$s/SKILL.md")" = "name: $s" ] || bad_names="$bad_names $s"
  sed -n 3p "$CS/$s/SKILL.md" | grep -q '^description: "' || bad_names="$bad_names $s"
done
if [ -z "$bad_names" ]; then ok "frontmatter is the name, then a quoted description, in every skill"; else bad "frontmatter is the name, then a quoted description, in every skill" "$bad_names"; fi
explicit="$(grep -l 'allow_implicit_invocation: false' "$CS"/*/agents/openai.yaml | awk -F/ '{print $(NF-2)}' | tr '\n' ' ')"
expect_rc "exactly the four explicit only skills are marked so" "next-phase review-ticket run-flow show-flow " "$explicit"
n="$(grep -L 'display_name:' "$CS"/*/agents/openai.yaml | wc -l | tr -d ' ')"; expect_rc "every openai.yaml names an interface" 0 "$n"
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
  expect_rc "a strict YAML parser reads every generated header and openai.yaml" 0 $?
else
  echo "  skip  python3 with PyYAML is not installed, so the generated YAML was not parsed"
fi
left="$(grep -rnE 'ARGUMENTS|claude -p|--agent|\.claude/|allowedTools|Leave out|/clear' "$CS" "$C/repo/.agents/flow-roles" || true)"
if [ -z "$left" ]; then ok "no Claude only text is left in the installed skills and roles"; else bad "no Claude only text is left in the installed skills and roles" "$(printf '%s' "$left" | head -3)"; fi
left="$(grep -rnE '(^|[^A-Za-z0-9_./~-])/(next-phase|review-ticket|plan-feature|run-flow|show-flow|architect-review|automation-design)([^A-Za-z0-9_/-]|$)' "$CS" || true)"
if [ -z "$left" ]; then ok "no slash command mention is left"; else bad "no slash command mention is left" "$(printf '%s' "$left" | head -3)"; fi
left="$(grep -rn 'CLAUDE.md' "$CS" | grep -v 'AGENTS.md' || true)"
if [ -z "$left" ]; then ok "CLAUDE.md is only ever named next to AGENTS.md"; else bad "CLAUDE.md is only ever named next to AGENTS.md" "$(printf '%s' "$left" | head -3)"; fi
NP="$(cat "$CS/next-phase/SKILL.md")"
expect_has "next-phase says what its arguments are" 'stands for the text the user typed after `$next-phase`' "$NP"
expect_has "next-phase shows the Codex invocation" 'Example: `$next-phase csv-export auto`' "$NP"
expect_has "next-phase asks for the loop to commit when git is refused" "the loop commits them for you" "$NP"
expect_has "next-phase warns the manual review needs the user's terminal" "give the command to the user to run in their own terminal" "$NP"
for s in next-phase review-ticket; do
  cmd="$(grep 'codex exec --sandbox read-only -' "$CS/$s/SKILL.md" | head -1)"
  expect_has "$s starts the review through codex in a read only sandbox" "| codex exec --sandbox read-only -" "$cmd"
  role="$(printf '%s' "$cmd" | grep -oE '\.agents/flow-roles/[a-z-]+\.md' | head -1)"
  if [ -n "$role" ] && [ -f "$C/repo/$role" ]; then ok "$s points at a role file that was installed"; else bad "$s points at a role file that was installed" "$role"; fi
done
left="$(grep -rn 'bash scripts/auto-flow.sh' "$CS" | grep -v 'FLOW_AGENT=codex bash scripts/auto-flow.sh' || true)"
if [ -z "$left" ]; then ok "every installed Codex skill starts the loop with codex"; else bad "every installed Codex skill starts the loop with codex" "$(printf '%s' "$left" | head -3)"; fi
expect_has "run-flow warns that the loop needs the user's terminal or an approval" "ask for approval to run it outside the sandbox" "$(cat "$CS/run-flow/SKILL.md")"
expect_has "run-flow tells Codex users which caps do not apply" "do not apply and only" "$(cat "$CS/run-flow/SKILL.md")"
expect_has "run-flow names the Codex mention for the builder prompt" 'prompt `$next-phase <feature> auto`' "$(cat "$CS/run-flow/SKILL.md")"
RB="$(cat "$C/repo/.agents/flow-roles/ticket-builder.md")"; RR="$(cat "$C/repo/.agents/flow-roles/ticket-reviewer.md")"
expect_has "the builder role keeps its rules" "You are the builder." "$RB"
expect_has "the reviewer role keeps its rules" "You are the reviewer, not the author." "$RR"
expect_lacks "a role file has no frontmatter" "tools:" "$RR"

out="$(bash "$ROOT/install.sh" "$C/repo" --agent codex 2>&1)"
expect_has "a second codex run adds nothing" "added 0, updated 0" "$out"
echo "my own edit" >> "$CS/run-flow/SKILL.md"
out="$(bash "$ROOT/install.sh" "$C/repo" --agent codex 2>&1)"
expect_has "an edited generated file is kept and reported" "kept" "$out"
expect_has "and keeps the user's edit" "my own edit" "$(cat "$CS/run-flow/SKILL.md")"
out="$(bash "$ROOT/install.sh" "$C/repo" --agent codex --force 2>&1)"
expect_has "--force regenerates it" "update" "$out"
expect_lacks "and the edit is gone" "my own edit" "$(cat "$CS/run-flow/SKILL.md")"
bash "$ROOT/install.sh" "$C/fresh" --agent codex --dry-run > /dev/null 2>&1
if [ -z "$(ls -A "$C/fresh")" ]; then ok "--agent codex --dry-run writes nothing"; else bad "--agent codex --dry-run writes nothing"; fi
out="$(bash "$ROOT/install.sh" "$C/fresh" --agent codex --dry-run 2>&1)"
expect_has "and still reports what it would add" "would add 29" "$out"

mkdir -p "$C/repo2"
AGENTS_HOME="$C/home/.agents" bash "$ROOT/install.sh" "$C/repo2" --agent codex --user > /dev/null 2>&1
if [ -f "$C/home/.agents/skills/next-phase/SKILL.md" ] && [ -f "$C/home/.agents/skills/next-phase/agents/openai.yaml" ]; then ok "--user puts the Codex skills in the user folder"; else bad "--user puts the Codex skills in the user folder"; fi
if [ -f "$C/repo2/.agents/flow-roles/ticket-reviewer.md" ] && [ -f "$C/repo2/scripts/gate.sh" ] && [ ! -e "$C/repo2/.agents/skills" ]; then ok "--user keeps roles and scripts in the repo"; else bad "--user keeps roles and scripts in the repo"; fi

if [ ! -e "$I/repo/.agents" ]; then ok "the default install writes no .agents"; else bad "the default install writes no .agents"; fi
if cmp -s "$ROOT/skills/next-phase/SKILL.md" "$I/repo/.claude/skills/next-phase/SKILL.md"; then ok "the Claude install copies the skill byte for byte"; else bad "the Claude install copies the skill byte for byte"; fi
mkdir -p "$C/both"
out="$(bash "$ROOT/install.sh" "$C/both" --agent all 2>&1)"
if [ -f "$C/both/.claude/skills/next-phase/SKILL.md" ] && [ -f "$C/both/.agents/skills/next-phase/SKILL.md" ] && [ -f "$C/both/.claude/agents/ticket-builder.md" ] && [ -f "$C/both/.agents/flow-roles/ticket-builder.md" ]; then ok "--agent all installs both"; else bad "--agent all installs both"; fi
expect_has "and points at both" 'next: $plan-feature' "$out"
expect_has "and at Claude Code" "/plan-feature <feature-name> in Claude Code" "$out"
bash "$ROOT/install.sh" "$C/fresh" --agent nonsense > /dev/null 2>&1; expect_rc "an unknown agent is a usage error" 2 $?
bash "$ROOT/install.sh" --agent > /dev/null 2>&1; expect_rc "--agent without a value is a usage error" 2 $?
out="$(bash "$ROOT/install.sh" "$C/fresh" --agent=codex --dry-run 2>&1)"; expect_has "--agent=codex works too" "(codex)" "$out"

echo "flow-status.sh, json"
set_status() { awk -v s="$2" 'FNR<=20 && !d && /^Status:/ {print "Status: " s; d=1; next} {print}' "$1" > "$1.tmp" && mv "$1.tmp" "$1"; }
cd "$TMP" || exit 1
mkdir -p js/plans/f/tasks
cd js || exit 1
S="$ROOT/scripts/flow-status.sh"
ticket plans/f/tasks/01-a.md 'Say "hi" \ and <b>caf'$'\xc3\xa9''</b>' resolved "—"
ticket plans/f/tasks/02-b.md B open "01"
ticket plans/f/tasks/03-c.md C open "01, 02"
out="$(bash "$S" f --json)"
printf '%s' "$out" | jq -e . > /dev/null 2>&1; expect_rc "--json prints valid JSON" 0 $?
[ "$(printf '%s' "$out" | jq -r '.tickets[0].title')" = 'Say "hi" \ and <b>caf'$'\xc3\xa9''</b>' ] && ok "quotes, backslashes, tags and accents survive" || bad "quotes, backslashes, tags and accents survive"
expect_has "counts are included" '"total":3' "$out"
[ "$(printf '%s' "$out" | jq -r '[.tickets[] | select(.ready) | .label] | join(",")')" = "02" ] && ok "readiness matches the table" || bad "readiness matches the table"
[ "$(printf '%s' "$out" | jq -r '.tickets[2].blocked_by | join(",")')" = "01,02" ] && ok "blockers are listed" || bad "blockers are listed"
[ "$(printf '%s' "$out" | jq -r '.tickets[0].type')" = "task" ] && ok "a missing Type defaults to task" || bad "a missing Type defaults to task"

echo "flow-view.sh"
V="$ROOT/scripts/flow-view.sh"
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
printf '00:00:01,01-a,build,3,0.25,false,"success"\n00:00:02,01-a,review,2,0.10,false,"success"\n00:00:03,01-a,build,4,0.30,false,"success"\n' > "$(git rev-parse --absolute-git-dir)/flow-cost-f.log"

bash "$V" f --no-open --out "$TMP/view.html" > /dev/null 2>&1; expect_rc "the page is written" 0 $?
page="$(cat "$TMP/view.html")"
data="$(grep -F '<script id="flow-data"' "$TMP/view.html" | sed 's/^<script id="flow-data" type="application\/json">//; s/<\/script>$//')"
printf '%s' "$data" | jq -e . > /dev/null 2>&1; expect_rc "the embedded data is valid JSON" 0 $?
expect_has "the page has the animated graph code" "@keyframes flow" "$page"
[ "$(printf '%s' "$data" | jq -r '[.details["01"].history[].status] | join(",")')" = "open,resolved,open,resolved" ] && ok "history lists every status change from git" || bad "history lists every status change from git"
[ "$(printf '%s' "$data" | jq -r '.details["01"].history[1].t')" = "1790001000" ] && ok "history carries the commit time" || bad "history carries the commit time"
[ "$(printf '%s' "$data" | jq -r '.details["01"].cost | "\(.build * 1) \(.review * 1) \(.sessions)"')" = "0.55 0.1 3" ] && ok "cost is summed per role from the cost log" || bad "cost is summed per role from the cost log"
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

out="$(bash "$V" f --no-open 2>&1)"
expect_has "the default location is inside .git" ".git/flow-f.html" "$out"
if [ -z "$(git status --porcelain)" ]; then ok "writing the page never dirties the tree"; else bad "writing the page never dirties the tree"; fi
bash "$V" nosuchfeature --no-open > /dev/null 2>&1; expect_rc "a missing feature exits 2" 2 $?
bash "$V" f --bogus > /dev/null 2>&1; expect_rc "an unknown option exits 2" 2 $?
bash "$V" > /dev/null 2>&1; expect_rc "no feature exits 2" 2 $?

mkdir -p "$TMP/nogit/plans/f/tasks" "$TMP/nogit_out"
(cd "$TMP/nogit" && ticket plans/f/tasks/01-a.md A open "—" && TMPDIR="$TMP/nogit_out" bash "$V" f --no-open > /dev/null 2>&1)
if [ -f "$TMP/nogit_out/flow-f.html" ]; then ok "outside a git repo the page goes to the temp folder"; else bad "outside a git repo the page goes to the temp folder"; fi
data2="$(grep -F '<script id="flow-data"' "$TMP/nogit_out/flow-f.html" | sed 's/^<script id="flow-data" type="application\/json">//; s/<\/script>$//')"
[ "$(printf '%s' "$data2" | jq -r '.details["01"].history | length')" = "0" ] && ok "and it simply has no history" || bad "and it simply has no history"

cd "$TMP/view" || exit 1
set_status plans/f/tasks/02-b.md resolved
git add -A; git commit -qm both
out="$(FLOW_WATCH_SECONDS=0.1 bash "$V" f --watch --no-open --out "$TMP/watch_done.html" 2>&1)"
expect_has "watching a finished feature ends at once" "feature complete" "$out"
expect_lacks "and leaves a page that does not refresh" 'http-equiv="refresh"' "$(cat "$TMP/watch_done.html")"
set_status plans/f/tasks/02-b.md open
git add -A; git commit -qm reopen-02
( FLOW_WATCH_SECONDS=0.2 bash "$V" f --watch --no-open --out "$TMP/watch_live.html" > /dev/null 2>&1 & echo $! > "$TMP/watch.pid" )
sleep 2
expect_has "watching a running feature writes a page that refreshes itself" 'http-equiv="refresh"' "$(cat "$TMP/watch_live.html" 2> /dev/null)"
kill "$(cat "$TMP/watch.pid")" 2> /dev/null || true

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
out="$(cd "$ROOT" && grep -rlE '^(import|from) ' feature_flow | xargs grep -hE '^(import|from) ' | grep -vE '^(import|from) (feature_flow|\.|os|sys|re|subprocess|pathlib|argparse|secrets|time|datetime|shlex|typing|dataclasses|__future__|json|textwrap|tempfile|shutil|enum)\b')"
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
if [ -f .git/flow-f.state ]; then ok "it creates .git/flow-f.state"; else bad "it creates .git/flow-f.state"; fi
expect_has "it logs the BUILD" ",01,BUILD" "$(cat .git/flow-f.log)"
expect_rc "and leaves the tree clean" 0 "$(git status --porcelain | wc -l | tr -d ' ')"
resolve plans/f/tasks/01-a.md
pyflow f next
expect_has "a resolved ticket goes to review with the same base" "REVIEW plans/f/tasks/01-a.md 01 $SHA" "$OUT"
expect_has "the state records HEAD as the review sha" "review_sha=$(git rev-parse HEAD)" "$(cat .git/flow-f.state)"
expect_has "the log has the gate" "GATE-PASS" "$(cat .git/flow-f.log)"
expect_has "and the floor guard" "GUARD-PASS" "$(cat .git/flow-f.log)"

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
before="$(cat .git/flow-f.state; git rev-parse HEAD; git status --porcelain)"
reply "REVIEW: PASS"
pyflow f verdict .git/reply.txt
expect_has "a PASS reply is recorded" "OK" "$OUT"
expect_has "and logged" "VERDICT-PASS" "$(cat .git/flow-f.log)"
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
    expect_has "and logged" "VERDICT-FAIL" "$(cat .git/flow-f.log)"
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
expect_has "and is logged" "VERDICT-NONE" "$(cat .git/flow-f.log)"
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
sed 's/^runs=.*/runs=65/' .git/flow-f.state > .git/flow-f.state.new && mv .git/flow-f.state.new .git/flow-f.state
pyflow f next
expect_rc "passing the run limit exits 1" 1 "$RC"
expect_has "and stops" "STOP run limit of 65 sessions reached, stopping" "$OUT"

D="$(flowrepo pyflow_noreview)"
cd "$D" || exit 1
pyflow f next; reply "REVIEW: PASS"
before="$(cat .git/flow-f.state; git rev-parse HEAD; git status --porcelain)"
pyflow f verdict .git/reply.txt
expect_rc "verdict while a build is pending exits 2" 2 "$RC"
if [ "$before" = "$(cat .git/flow-f.state; git rev-parse HEAD; git status --porcelain)" ]; then ok "and changes nothing"; else bad "and changes nothing"; fi
cd "$ROOT" || exit 1

echo "smoke-real.sh, prepare only"
SM="$ROOT/tests/smoke-real.sh"
mkdir -p "$TMP/nobin"
P="$TMP/prep_codex"
out="$(env PATH="$TMP/nobin:/usr/bin:/bin" FLOW_AGENT=codex bash "$SM" --prepare "$P" 2>&1)"; rc=$?
expect_rc "--prepare builds the project without any model installed" 0 $rc
expect_has "it says no model was called" "no model was called" "$out"
expect_has "and tells a codex user what to type" 'then type:  $next-phase hello' "$out"
if [ -f "$P/.agents/skills/next-phase/SKILL.md" ] && [ -f "$P/.agents/flow-roles/ticket-reviewer.md" ] && [ ! -e "$P/.claude" ]; then ok "the project is installed for codex only"; else bad "the project is installed for codex only"; fi
expect_has "the plan passes the ticket check" "OK: 2 tickets" "$(cd "$P" && bash scripts/flow-status.sh hello --check 2>&1)"
expect_has "and the first ticket is the one that is ready" "01-greet-function.md" "$(cd "$P" && bash scripts/flow-status.sh hello --next 2>&1)"
if [ -z "$(cd "$P" && git status --porcelain)" ] && [ "$(cd "$P" && git rev-list --count HEAD)" = 1 ]; then ok "it is one clean commit"; else bad "it is one clean commit"; fi
env FLOW_AGENT=codex bash "$SM" --prepare "$P" > /dev/null 2>&1; expect_rc "a folder that is not empty is refused" 2 $?
P2="$TMP/prep_claude"
out="$(env PATH="$TMP/nobin:/usr/bin:/bin" bash "$SM" --prepare "$P2" 2>&1)"; rc=$?
expect_rc "--prepare defaults to claude" 0 $rc
expect_has "and tells a claude user what to type" "then type:  /next-phase hello" "$out"
if [ -f "$P2/.claude/skills/next-phase/SKILL.md" ] && [ ! -e "$P2/.agents" ]; then ok "the project is installed for claude only"; else bad "the project is installed for claude only"; fi
env RUN_REAL=0 bash "$SM" > /dev/null 2>&1; expect_rc "without RUN_REAL or --prepare nothing runs" 2 $?
out="$(env FLOW_AGENT=bogus bash "$SM" --prepare "$TMP/prep_bogus" 2>&1)"; rc=$?
expect_rc "an unknown FLOW_AGENT is refused" 2 $rc
expect_has "and the script itself says what is allowed" "FLOW_AGENT must be claude or codex, not bogus" "$out"
if [ ! -e "$TMP/prep_bogus" ]; then ok "and it creates nothing"; else bad "and it creates nothing"; fi
bash "$SM" --prepare > /dev/null 2>&1; expect_rc "--prepare without a folder is refused" 2 $?

echo
echo "$PASS passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
