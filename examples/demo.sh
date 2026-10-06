#!/bin/bash
# usage: bash examples/demo.sh [target-dir] [--open]
# builds a throwaway git repo that holds a 10 ticket plan in the middle of a run, with commit
# history (two tickets were sent back), a ticket in progress and tickets ready to
# start, then writes the animated graph page for it. use it to see the viewer without a real project.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET=""
OPEN=0
for arg in "$@"; do
  case "$arg" in
    --open) OPEN=1 ;;
    *) TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || TARGET="$(mktemp -d)"
mkdir -p "$TARGET"
cd "$TARGET"

git init -q -b main
git config user.email demo@example.com
git config user.name demo
mkdir -p plans/demo/tasks
FEATURE_DIR=plans/demo
T0=1790000000

ticket() { # label slug title type blocked-by status [review-round-source]
  local label="$1" slug="$2" title="$3" type="$4" blocked="$5" status="$6" round="${7:-}"
  {
    printf '# %s\n\nType: %s\nStatus: %s\nBlocked by: %s\nTest first: yes\n\n' "$title" "$type" "$status" "$blocked"
    printf 'Do the work described by "%s".\n\n## Not in this ticket\n\n- everything the later tickets cover\n\n' "$title"
    printf '## Done when\n\n- `make test` exits 0 and prints OK\n- the new behaviour is covered by a test that fails without it\n\n## Reference\n\n- spec.md\n\n## Answer\n\n'
    if [ "$status" = resolved ]; then
      printf '**Built**: %s.\n**Proof**: `make test` printed OK, exit 0, run fresh.\n**Decisions**: kept it small.\n' "$title"
    fi
    if [ -n "$round" ]; then
      printf '\n## Review findings (round 1, %s)\n\n1. major: a case was missed. cover it.\n' "$round"
    fi
  } > "$FEATURE_DIR/tasks/$label-$slug.md"
}

commit() { # minutes message
  git add -A
  GIT_AUTHOR_DATE="$((T0 + $1 * 60)) +0000" GIT_COMMITTER_DATE="$((T0 + $1 * 60)) +0000" git commit -q -m "$2"
}

printf '# Demo\n' > "$FEATURE_DIR/spec.md"
printf '# Map: demo\n\n## Decisions so far\n' > "$FEATURE_DIR/map.md"
ticket 01 define-types "Define the types" task "—" open
ticket 02 build-parser "Build the parser" task "01" open
ticket 03 build-store "Build the store" task "01" open
ticket 04 api-endpoints "Add the API endpoints" task "02, 03" open
ticket 05 migrate-data "Migrate the old data" convert "03" open
ticket 06 settle-auth "Settle the auth model" settle "—" open
ticket 07 auth-middleware "Add the auth middleware" task "04, 06" open
ticket 08 ui-screens "Build the screens" task "04" open
ticket 09 acceptance "Acceptance: run the bar end to end" task "05, 07, 08" open
ticket 10 release-notes "Write the release notes" task "09" open
commit 0 "plan: demo"

ticket 01 define-types "Define the types" task "—" resolved
commit 8 "feat(demo): 01 Define the types"
ticket 06 settle-auth "Settle the auth model" settle "—" resolved
commit 11 "feat(demo): 06 Settle the auth model"
ticket 02 build-parser "Build the parser" task "01" resolved
commit 19 "feat(demo): 02 Build the parser"
ticket 02 build-parser "Build the parser" task "01" open gate
commit 21 "chore(demo): 02 review findings, round 1"
ticket 02 build-parser "Build the parser" task "01" resolved gate
commit 27 "feat(demo): 02 Build the parser"
ticket 03 build-store "Build the store" task "01" resolved
commit 33 "feat(demo): 03 Build the store"
ticket 04 api-endpoints "Add the API endpoints" task "02, 03" resolved
commit 44 "feat(demo): 04 Add the API endpoints"
ticket 04 api-endpoints "Add the API endpoints" task "02, 03" open "independent review"
commit 47 "chore(demo): 04 review findings, round 1"
ticket 04 api-endpoints "Add the API endpoints" task "02, 03" resolved "independent review"
commit 55 "feat(demo): 04 Add the API endpoints"

ticket 05 migrate-data "Migrate the old data" convert "03" claimed

echo "demo repo: $TARGET"
if [ "$OPEN" = 1 ]; then
  bash "$ROOT/scripts/flow-view.sh" demo
else
  bash "$ROOT/scripts/flow-view.sh" demo --no-open
fi
