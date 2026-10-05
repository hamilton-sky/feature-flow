#!/bin/bash
# usage: bash scripts/floor-guard.sh <feature> <NN> [base-commit]
# looks at the diff from base-commit (default HEAD~1) to HEAD for ways of weakening the bar
# instead of meeting it: skipped tests, silenced checks, empty catches, deleted tests,
# lowered thresholds, edited lint or test config.
# it also protects the plan from the worker: only the ticket's own Status line and Answer,
# appended lines in map.md and learnings.md may change, and nothing else under the plans folder.
# a ticket can allow categories with a line "Floor: allow skip, suppress" (skip, suppress,
# empty-catch, test-delete, threshold, config, ticket-edit, commands-edit). the line is read
# from the ticket as it was at base-commit, so a worker cannot excuse itself.
# run it from the repo root. exit 0 clean, 1 findings, 2 usage error.

set -euo pipefail

FEATURE="${1:-}"
NUM="${2:-}"
BASE="${3:-HEAD~1}"
if [ -z "$FEATURE" ] || [ -z "$NUM" ]; then
  echo "usage: bash scripts/floor-guard.sh <feature> <NN> [base-commit]" >&2
  exit 2
fi

ROOT="${FLOW_DIR:-plans}"
DIR="$ROOT/$FEATURE/${FLOW_TICKETS:-tasks}"
set -- "$DIR"/"$NUM"-*.md
if [ ! -e "$1" ]; then
  echo "no ticket $NUM in $DIR" >&2
  exit 2
fi
TICKET="$1"

ticket_at() { git show "$1:./$TICKET" 2> /dev/null; }
if git cat-file -e "$BASE:./$TICKET" 2> /dev/null; then
  ALLOW_SOURCE="$(ticket_at "$BASE")"
else
  ALLOW_SOURCE="$(cat "$TICKET")"
fi
ALLOW="$(printf '%s\n' "$ALLOW_SOURCE" | awk 'FNR <= 20 && /^Floor:/ { v = tolower($0); sub(/^floor:[ \t]*allow[ \t]*/, "", v); gsub(/,/, " ", v); print v; exit }')"
allows() { printf ' %s ' "$ALLOW" | grep -q " $1 "; }

findings="$(
  git diff --no-color --unified=0 "$BASE" HEAD -- . ":(exclude)$ROOT" | awk -v allow=" $ALLOW " '
    function allowed(cat) { return index(allow, " " cat " ") > 0 }
    function report(cat, text) {
      if (allowed(cat)) return
      sub(/^[ \t]+/, "", text)
      printf "%s: %s: %s\n", cat, file, substr(text, 1, 100)
    }
    /^\+\+\+ / { file = $2; sub(/^b\//, "", file); next }
    /^\+/ {
      line = substr($0, 2)
      if (line ~ /@pytest\.mark\.(skip|xfail)|pytest\.skip\(|(^|[^A-Za-z_])(it|test|describe)\.(skip|todo)\(|(^|[^A-Za-z_])(xit|xdescribe|xtest)\(|@Disabled|t\.Skip\(|#\[ignore\]|unittest\.skip/) report("skip", line)
      if (line ~ /# noqa|# type: ignore|# pylint: disable|# pragma: no cover|# fmt: off|# ruff: noqa|eslint-disable|@ts-ignore|@ts-expect-error|\/\/ nolint|#\[allow\(|--no-verify/) report("suppress", line)
      if (line ~ /except[^:]*:[ \t]*pass[ \t]*$|catch[ \t]*(\([^)]*\))?[ \t]*\{[ \t]*\}/) report("empty-catch", line)
      if (line ~ /fail_under|fail-under|coverageThreshold|cov-fail-under/) report("threshold", line)
    }
  '
)"

deleted="$(git diff --name-only --diff-filter=D "$BASE" HEAD -- . ":(exclude)$ROOT" | grep -E '(^|/)(test_[^/]*\.py|[^/]*_test\.[a-z]+|[^/]*\.(test|spec)\.[a-z]+|tests?/|__tests__/)' || true)"
if [ -n "$deleted" ] && ! printf ' %s ' "$ALLOW" | grep -q ' test-delete '; then
  findings="$findings
$(printf '%s\n' "$deleted" | sed 's/^/test-delete: /')"
fi

touched="$(git diff --name-only "$BASE" HEAD -- . ":(exclude)$ROOT" | grep -E '(^|/)(\.eslintrc[^/]*|eslint\.config\.[a-z]+|ruff\.toml|\.ruff\.toml|mypy\.ini|pytest\.ini|tox\.ini|tsconfig[^/]*\.json|jest\.config\.[a-z]+|vitest\.config\.[a-z]+|\.pre-commit-config\.yaml|\.github/workflows/[^/]*|\.azure/.*)$' || true)"
if [ -n "$touched" ] && ! printf ' %s ' "$ALLOW" | grep -q ' config '; then
  findings="$findings
$(printf '%s\n' "$touched" | sed 's/^/config: /')"
fi

rel() {
  local p
  p="$(git ls-files --full-name -- "$1" 2> /dev/null | head -1)"
  if [ -n "$p" ]; then printf '%s' "$p"; else printf '%s' "${1#./}"; fi
}
frozen() {
  awk 'FNR <= 20 && !s && /^Status:/ { s = 1; next } /^## (Answer|Review findings)/ { exit } { print }'
}
removed_real_lines() {
  git diff --no-color --unified=0 "$BASE" HEAD -- "$1" | awk '/^---/ { next } /^-/ { l = substr($0, 2); gsub(/^[ \t]+|[ \t]+$/, "", l); if (l != "" && l !~ /^(- )?</) n++ } END { print n + 0 }'
}
add_finding() { findings="$findings
$1: $2: $3"; }

T_REL="$(rel "$TICKET")"
M_REL="$(rel "$ROOT/$FEATURE/map.md")"
C_REL="$(rel "$ROOT/$FEATURE/commands.md")"
L_REL="$(rel "$ROOT/$FEATURE/learnings.md")"

while IFS=$'\t' read -r st path; do
  [ -n "$path" ] || continue
  if [ "$path" = "$T_REL" ]; then
    allows ticket-edit && continue
    if [ "$st" != "M" ]; then
      add_finding ticket-edit "$path" "the ticket was added or deleted"
    elif ! cmp -s <(git show "$BASE:./$path" 2> /dev/null | frozen) <(git show "HEAD:./$path" 2> /dev/null | frozen); then
      add_finding ticket-edit "$path" "text outside the Status line and the Answer was changed"
    fi
  elif [ "$path" = "$M_REL" ] || [ "$path" = "$L_REL" ]; then
    allows ticket-edit && continue
    if [ "$st" = "D" ]; then
      add_finding ticket-edit "$path" "the file was deleted"
    elif [ "$st" = "M" ] && [ "$(removed_real_lines "$path")" -gt 0 ]; then
      add_finding ticket-edit "$path" "existing lines were removed or rewritten (append only)"
    fi
  elif [ "$path" = "$C_REL" ]; then
    allows commands-edit || add_finding commands-edit "$path" "the frozen commands file was changed"
  else
    allows ticket-edit || add_finding ticket-edit "$path" "only your own ticket, map.md and learnings.md may change"
  fi
done < <(git diff --name-status --no-renames "$BASE" HEAD -- "$ROOT")

findings="$(printf '%s\n' "$findings" | sed '/^[[:space:]]*$/d')"

removed_asserts="$(git diff --no-color --unified=0 "$BASE" HEAD -- . ":(exclude)$ROOT" | grep -cE '^-.*(assert|expect\()' || true)"
added_asserts="$(git diff --no-color --unified=0 "$BASE" HEAD -- . ":(exclude)$ROOT" | grep -cE '^\+.*(assert|expect\()' || true)"
if [ "$removed_asserts" -gt "$added_asserts" ]; then
  echo "warning: $removed_asserts assertion line(s) removed, $added_asserts added. check that no test got weaker."
fi

if [ -n "$findings" ]; then
  echo "floor guard: the diff weakens the bar instead of meeting it"
  printf '%s\n' "$findings"
  echo "if a finding is intended, the ticket needs a line like: Floor: allow <category>"
  exit 1
fi

echo "floor guard: clean"
