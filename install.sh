#!/bin/bash
# usage: bash install.sh [target-repo] [--agent claude|codex|all] [--user] [--force] [--dry-run]
# runs the Python installer next to this file; python3 install.py --help says what it does.
exec python3 "$(dirname "$0")/install.py" "$@"
