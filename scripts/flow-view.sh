#!/bin/bash
# usage: bash scripts/flow-view.sh <feature> [--watch] [--no-open] [--out FILE]
# writes one self contained HTML page that shows the ticket graph, animated, and opens it.
# the page can replay the run from git history and shows the cost per ticket from the cost log.
# --watch rewrites the page every few seconds until the feature is complete.
# env: FLOW_DIR, FLOW_TICKETS (ticket location), FLOW_NO_OPEN=1 (never open a browser),
#      FLOW_WATCH_SECONDS (default 3)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS="$HERE/flow-status.sh"
TEMPLATE="$HERE/flow-view.html"

usage() {
  echo "usage: bash scripts/flow-view.sh <feature> [--watch] [--no-open] [--out FILE]" >&2
  exit 2
}

FEATURE="${1:-}"
[ -n "$FEATURE" ] || usage
shift
WATCH=0
OPEN=1
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --watch) WATCH=1 ;;
    --no-open) OPEN=0 ;;
    --out)
      shift
      OUT="${1:-}"
      [ -n "$OUT" ] || usage
      ;;
    *) usage ;;
  esac
  shift
done

DIR="${FLOW_DIR:-plans}/$FEATURE/${FLOW_TICKETS:-tasks}"
[ -d "$DIR" ] || { echo "no ticket folder: $DIR" >&2; exit 2; }
[ -f "$TEMPLATE" ] || { echo "missing $TEMPLATE" >&2; exit 2; }

GITDIR="$(git rev-parse --absolute-git-dir 2> /dev/null || true)"
if [ -z "$OUT" ]; then
  if [ -n "$GITDIR" ]; then OUT="$GITDIR/flow-$FEATURE.html"; else OUT="${TMPDIR:-/tmp}/flow-$FEATURE.html"; fi
fi
COST_LOG="$GITDIR/flow-cost-$FEATURE.log"

JSTR='function jstr(s,   n, i, c, o) {
  o = "\""
  n = length(s)
  for (i = 1; i <= n; i++) {
    c = substr(s, i, 1)
    if (c == "\\") o = o "\\\\"
    else if (c == "\"") o = o "\\\""
    else if (c == "\t") o = o "\\t"
    else if (c == "\001") o = o "\\n"
    else if (c < " ") o = o ""
    else o = o c
  }
  return o "\""
}
'

ticket_extras() {
  awk "$JSTR"'
    /^## / {
      sect = tolower(substr($0, 4))
      if (sect ~ /^review findings/) {
        n = 0
        src = ""
        if (match($0, /round [0-9]+/)) n = substr($0, RSTART + 6, RLENGTH - 6) + 0
        if (match($0, /, [^)]*\)/)) src = substr($0, RSTART + 2, RLENGTH - 3)
        nr++
        rounds[nr] = sprintf("{\"n\":%d,\"source\":%s}", n, jstr(src))
      }
      next
    }
    sect == "done when" && /^- / && ndw < 8 { ndw++; dw[ndw] = jstr(substr(substr($0, 3), 1, 240)); next }
    sect == "answer" && NF && $0 !~ /^</ && length(ans) < 700 { ans = (ans == "" ? "" : ans "\001") $0 }
    END {
      if (ans ~ /left empty until/) ans = ""
      printf "{\"done_when\":["
      for (i = 1; i <= ndw; i++) printf "%s%s", (i > 1 ? "," : ""), dw[i]
      printf "],\"answer\":%s,\"rounds\":[", jstr(substr(ans, 1, 700))
      for (i = 1; i <= nr; i++) printf "%s%s", (i > 1 ? "," : ""), rounds[i]
      printf "]"
    }' "$1"
}

ticket_history() {
  local out="" sha at st
  if [ -z "$GITDIR" ]; then
    printf '[]'
    return 0
  fi
  while read -r sha at; do
    [ -n "$sha" ] || continue
    st="$(git show "$sha:./$1" 2> /dev/null | awk 'FNR <= 20 && /^Status:/ {
      sub(/^Status:[ \t]*/, "")
      s = tolower($0)
      sub(/[ \t(].*$/, "", s)
      if (s == "resolved" || s == "done" || s == "closed") s = "resolved"
      else if (s == "parked" || s == "wontfix") s = "parked"
      else s = "open"
      print s
      exit
    }')" || true
    [ -n "$st" ] || continue
    out="$out${out:+,}{\"t\":$at,\"status\":\"$st\"}"
  done < <(git log --reverse --format='%H %at' -- "$1" 2> /dev/null || true)
  printf '[%s]' "$out"
}

ticket_cost() {
  if [ -f "$COST_LOG" ]; then
    awk -F, -v name="$1" '$2 == name { c[$3] += $5; n++ } END { printf "{\"build\":%.4f,\"review\":%.4f,\"sessions\":%d}", c["build"] + 0, c["review"] + 0, n + 0 }' "$COST_LOG"
  else
    printf '{"build":0,"review":0,"sessions":0}'
  fi
}

build_json() {
  local core file name label details=""
  core="$(bash "$STATUS" "$FEATURE" --json)"
  for file in "$DIR"/[0-9][0-9]*-*.md; do
    [ -e "$file" ] || continue
    name="$(basename "$file" .md)"
    label="${name%%-*}"
    details="$details${details:+,}\"$label\":$(ticket_extras "$file"),\"history\":$(ticket_history "$file"),\"cost\":$(ticket_cost "$name")}"
  done
  printf '%s,"generated":"%s","details":{%s}}' "${core%\}}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$details"
}

render() {
  local tmp refresh=""
  tmp="$(mktemp)"
  build_json | sed 's/</\\u003c/g' > "$tmp"
  if [ "$WATCH" = 1 ]; then refresh='<meta http-equiv="refresh" content="3">'; fi
  mkdir -p "$(dirname "$OUT")"
  awk -v dataf="$tmp" -v refresh="$refresh" '
    index($0, "<!--__REFRESH__-->") { sub(/<!--__REFRESH__-->/, refresh) }
    {
      p = index($0, "__FLOW_DATA__")
      if (p) {
        printf "%s", substr($0, 1, p - 1)
        while ((getline line < dataf) > 0) printf "%s", line
        close(dataf)
        print substr($0, p + 13)
      } else print
    }' "$TEMPLATE" > "$OUT.tmp"
  mv "$OUT.tmp" "$OUT"
  rm -f -- "$tmp"
}

open_page() {
  [ "$OPEN" = 1 ] && [ "${FLOW_NO_OPEN:-}" != 1 ] || return 0
  if command -v open > /dev/null 2>&1; then
    open "$OUT"
  elif command -v xdg-open > /dev/null 2>&1; then
    xdg-open "$OUT" > /dev/null 2>&1 || true
  fi
}

render
echo "wrote $OUT"
open_page

if [ "$WATCH" = 1 ]; then
  echo "watching, press Ctrl-C to stop"
  while true; do
    rc=0
    bash "$STATUS" "$FEATURE" --next > /dev/null 2>&1 || rc=$?
    if [ "$rc" -eq 10 ]; then
      WATCH=0
      render
      echo "feature complete, final page written"
      break
    fi
    render
    sleep "${FLOW_WATCH_SECONDS:-3}"
  done
fi
