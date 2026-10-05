#!/bin/bash
# usage: bash scripts/flow-status.sh <feature> [--next | --counts | --check | --mermaid [plain] | --json]
# reads plans/<feature>/tasks/NN-slug.md and reports which tickets are ready.
# --mermaid prints the ticket graph as a mermaid flowchart, coloured by status unless "plain" is given.
# --json prints every ticket with its status, blockers and readiness as one JSON object.
# env: FLOW_DIR (default plans), FLOW_TICKETS (default tasks)
# exit codes for --next: 0 a ready ticket path is printed, 10 all done, 11 unfinished but nothing ready

set -euo pipefail

FEATURE="${1:-}"
MODE="${2:-table}"
OPT="${3:-}"
if [ -z "$FEATURE" ]; then
  echo "usage: bash scripts/flow-status.sh <feature> [--next | --counts | --check | --mermaid [plain] | --json]" >&2
  exit 2
fi

DIR="${FLOW_DIR:-plans}/$FEATURE/${FLOW_TICKETS:-tasks}"
if [ ! -d "$DIR" ]; then
  echo "no ticket folder: $DIR" >&2
  exit 2
fi

set -- "$DIR"/[0-9][0-9]*-*.md
if [ ! -e "$1" ]; then
  echo "no tickets in $DIR" >&2
  exit 2
fi

if [ "$MODE" = "--check" ]; then
  LEARNINGS="${FLOW_DIR:-plans}/$FEATURE/learnings.md"
  if [ -f "$LEARNINGS" ]; then
    lines="$(grep -c '[^[:space:]]' "$LEARNINGS" || true)"
    if [ "${lines:-0}" -gt 40 ]; then
      echo "warning: learnings.md has $lines lines. every session reads it, so a human should prune it"
    fi
  fi
fi

exec awk -v mode="$MODE" -v opt="$OPT" -v feat="$FEATURE" '
function jstr(s,   n, i, c, o) {
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

function norm(s) {
  s = tolower(s)
  sub(/^[ \t]+/, "", s)
  sub(/[ \t(].*$/, "", s)
  if (s == "resolved" || s == "done" || s == "closed") return "resolved"
  if (s == "claimed" || s == "in-progress") return "claimed"
  if (s == "parked" || s == "wontfix") return "parked"
  if (s == "needs-triage" || s == "needs-info" || s == "ready-for-human" || s == "waiting") return "waiting"
  if (s == "open" || s == "ready-for-agent") return "open"
  return "unknown"
}

FNR == 1 {
  base = FILENAME
  sub(/^.*\//, "", base)
  match(base, /^[0-9]+/)
  label = substr(base, 1, RLENGTH)
  cur = label + 0
  if (cur in path) dup[cur] = 1
  path[cur] = FILENAME
  lab[cur] = label
  stat[cur] = "unknown"
  hasstatus[cur] = 0
  hasdone[cur] = 0
  nblk[cur] = 0
  title[cur] = base
  seen[cur] = 1
  skipm = 0
}
FNR <= 20 && /^Status:/ && !hasstatus[cur] {
  v = $0
  sub(/^Status:/, "", v)
  stat[cur] = norm(v)
  hasstatus[cur] = 1
}
FNR <= 20 && /^Blocked by:/ && !hasblk[cur] {
  hasblk[cur] = 1
  v = $0
  sub(/^Blocked by:/, "", v)
  while (match(v, /[0-9]+/)) {
    nblk[cur]++
    blk[cur, nblk[cur]] = substr(v, RSTART, RLENGTH) + 0
    v = substr(v, RSTART + RLENGTH)
  }
}
FNR <= 20 && /^Type:/ && !hastype[cur] {
  hastype[cur] = 1
  v = tolower($0)
  sub(/^type:[ \t]*/, "", v)
  sub(/[ \t].*$/, "", v)
  typ[cur] = v
}
FNR <= 20 && /^Test first:/ && !hastf[cur] {
  hastf[cur] = 1
  v = tolower($0)
  sub(/^test first:[ \t]*/, "", v)
  sub(/[ \t].*$/, "", v)
  tf[cur] = v
}
/^# / && !hastitle[cur] {
  hastitle[cur] = 1
  title[cur] = substr($0, 3)
}
/^## Done when/ { hasdone[cur] = 1 }
/^## / {
  sect = tolower(substr($0, 4))
  skipm = (sect ~ /^(not in this ticket|answer|review findings)/)
  next
}
!skipm && FNR > 1 {
  rest = $0
  while (match(rest, /[Tt]ickets? +[0-9]+( *(,|and|&) *[0-9]+)*/)) {
    seg = substr(rest, RSTART, RLENGTH)
    rest = substr(rest, RSTART + RLENGTH)
    while (match(seg, /[0-9]+/)) {
      m = substr(seg, RSTART, RLENGTH) + 0
      seg = substr(seg, RSTART + RLENGTH)
      if (m < 1000 && !((cur SUBSEP m) in ment)) { ment[cur, m] = 1; nment[cur]++; mlist[cur, nment[cur]] = m }
    }
  }
}

END {
  n = 0
  for (k in seen) order[++n] = k + 0
  for (i = 2; i <= n; i++) {
    x = order[i]
    j = i - 1
    while (j >= 1 && order[j] > x) { order[j + 1] = order[j]; j-- }
    order[j + 1] = x
  }

  nerr = 0
  for (i = 1; i <= n; i++) {
    t = order[i]
    ready[t] = 0
    if (stat[t] == "resolved") nres++
    else if (stat[t] == "open") nopen++
    else if (stat[t] == "claimed") nclaim++
    else if (stat[t] == "waiting") nwait++
    else if (stat[t] == "parked") npark++
    else nunk++
    if (stat[t] == "open") {
      ok = 1
      for (b = 1; b <= nblk[t]; b++) {
        d = blk[t, b]
        if (!(d in seen) || stat[d] != "resolved") ok = 0
      }
      if (ok) { ready[t] = 1; nready++; if (first == "") first = t }
    }
    if (stat[t] != "resolved" && stat[t] != "parked") unfinished++
  }

  if (mode == "--next") {
    if (first != "") { print path[first]; exit 0 }
    if (unfinished == 0) { print "COMPLETE" > "/dev/stderr"; exit 10 }
    printf "stuck: %d claimed, %d waiting, %d open but blocked, %d unknown status\n", nclaim, nwait, nopen, nunk > "/dev/stderr"
    exit 11
  }

  if (mode == "--counts") {
    printf "total=%d resolved=%d open=%d claimed=%d waiting=%d parked=%d unknown=%d ready=%d\n", n, nres, nopen, nclaim, nwait, npark, nunk, nready
    exit 0
  }

  if (mode == "--json") {
    printf "{\"feature\":%s,\"tickets\":[", jstr(feat)
    for (i = 1; i <= n; i++) {
      t = order[i]
      bl = ""
      for (b = 1; b <= nblk[t]; b++) {
        d = blk[t, b]
        bl = bl (b > 1 ? "," : "") jstr((d in seen) ? lab[d] : sprintf("%02d", d))
      }
      printf "%s{\"id\":%d,\"label\":%s,\"title\":%s,\"status\":%s,\"type\":%s,\"test_first\":%s,\"blocked_by\":[%s],\"ready\":%s,\"file\":%s}", \
        (i > 1 ? "," : ""), t, jstr(lab[t]), jstr(title[t]), jstr(stat[t]), jstr(typ[t] == "" ? "task" : typ[t]), jstr(tf[t]), bl, (ready[t] ? "true" : "false"), jstr(path[t])
    }
    printf "],\"counts\":{\"total\":%d,\"resolved\":%d,\"open\":%d,\"claimed\":%d,\"waiting\":%d,\"parked\":%d,\"unknown\":%d,\"ready\":%d}}\n", n, nres, nopen, nclaim, nwait, npark, nunk, nready
    exit 0
  }

  if (mode == "--mermaid") {
    print "flowchart TD"
    for (i = 1; i <= n; i++) {
      t = order[i]
      ttl = title[t]
      gsub(/"/, "\047", ttl)
      cls = stat[t]
      if (cls == "open") cls = (ready[t] ? "ready" : "open")
      if (cls == "unknown") cls = "open"
      suffix = (opt == "plain") ? "" : ":::" cls
      printf "  T%s[\"%s %s\"]%s\n", lab[t], lab[t], ttl, suffix
    }
    for (i = 1; i <= n; i++) {
      t = order[i]
      for (b = 1; b <= nblk[t]; b++) {
        d = blk[t, b]
        if (d in seen) printf "  T%s --> T%s\n", lab[d], lab[t]
      }
    }
    if (opt != "plain") {
      print "  classDef resolved fill:#d4edda,stroke:#2e7d32"
      print "  classDef ready fill:#fff3cd,stroke:#b8860b"
      print "  classDef open fill:#f5f5f5,stroke:#999999"
      print "  classDef claimed fill:#cfe2ff,stroke:#1d4ed8"
      print "  classDef waiting fill:#fde2e2,stroke:#b91c1c"
      print "  classDef parked fill:#eeeeee,stroke:#bbbbbb,stroke-dasharray:4 3"
    }
    exit 0
  }

  if (mode == "--check") {
    for (i = 1; i <= n; i++) {
      t = order[i]
      if (t in dup) err[++nerr] = lab[t] ": two tickets share this number"
      if (!hasstatus[t]) err[++nerr] = lab[t] ": no Status line in the first 20 lines"
      else if (stat[t] == "unknown") err[++nerr] = lab[t] ": unrecognised Status value"
      if (!hasdone[t]) err[++nerr] = lab[t] ": no ## Done when section"
      if (hastf[t] && tf[t] != "yes" && tf[t] != "no") err[++nerr] = lab[t] ": Test first must be yes or no"
      for (b = 1; b <= nblk[t]; b++) {
        d = blk[t, b]
        if (d == t) err[++nerr] = lab[t] ": blocked by itself"
        else if (!(d in seen)) err[++nerr] = lab[t] ": blocked by " d ", which does not exist"
      }
    }
    progress = 1
    left = n
    while (progress && left > 0) {
      progress = 0
      for (i = 1; i <= n; i++) {
        t = order[i]
        if (t in placed) continue
        ok = 1
        for (b = 1; b <= nblk[t]; b++) {
          d = blk[t, b]
          if ((d in seen) && d != t && !(d in placed)) ok = 0
        }
        if (ok) { placed[t] = 1; progress = 1; left-- }
      }
    }
    if (left > 0) {
      for (i = 1; i <= n; i++) if (!(order[i] in placed)) err[++nerr] = lab[order[i]] ": part of a dependency cycle"
    }
    if (nready == 0 && unfinished > 0) err[++nerr] = "no ticket is ready to start"

    for (pass = 1; pass <= n; pass++) {
      changed = 0
      for (i = 1; i <= n; i++) {
        t = order[i]
        for (b = 1; b <= nblk[t]; b++) {
          d = blk[t, b]
          if (!(d in seen)) continue
          if (!((t SUBSEP d) in reach)) { reach[t, d] = 1; changed = 1 }
          for (j = 1; j <= n; j++) {
            x = order[j]
            if (((d SUBSEP x) in reach) && !((t SUBSEP x) in reach)) { reach[t, x] = 1; changed = 1 }
          }
        }
      }
      if (!changed) break
    }
    for (i = 1; i <= n; i++) {
      t = order[i]
      for (k = 1; k <= nment[t]; k++) {
        m = mlist[t, k]
        if (m == t || !(m in seen)) continue
        if ((t SUBSEP m) in reach) continue
        if ((m SUBSEP t) in reach) continue
        printf "warning: %s: mentions ticket %s but is not ordered against it. add it to Blocked by, or reword\n", lab[t], lab[m]
      }
    }
    if (nerr > 0) {
      for (e = 1; e <= nerr; e++) print err[e]
      exit 1
    }
    printf "OK: %d tickets, %d ready now\n", n, nready
    exit 0
  }

  for (i = 1; i <= n; i++) {
    t = order[i]
    bl = ""
    for (b = 1; b <= nblk[t]; b++) bl = bl (b > 1 ? "," : "") sprintf("%02d", blk[t, b])
    printf "%s  %-9s %-6s %-12s %s\n", lab[t], stat[t], (ready[t] ? "READY" : "-"), (bl == "" ? "" : "after " bl), title[t]
  }
}
' "$@"
