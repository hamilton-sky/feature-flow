"""feature-flow: the command an installed package puts on PATH (`uvx feature-flow-cli install .`).

It installs the flow into a repo and reads a plan. The flow itself runs from the repo, as
python3 scripts/flow.py, with the copy the installer put there.
"""

import os
import sys

from pathlib import Path

from feature_flow import __version__, cli, install, status, suggest, uninstall, view

USAGE = """\
usage: feature-flow install [target-repo] [--agent claude|codex|all] [--user] [--private] [--force] [--dry-run]
       feature-flow uninstall [target-repo] [--user] [--force] [--dry-run]
       feature-flow status <feature> [--next | --counts | --check | --mermaid [plain] | --json]
       feature-flow view <feature> [--watch] [--no-open] [--out FILE]
       feature-flow reset <feature> [NN]
       feature-flow --version
install copies the skill, its roles, scripts and guides into a repo; --user installs them once for every repo, in ~/.claude, ~/.agents and ~/.feature-flow, and writes nothing into a repo. feature-flow install --help says more.
uninstall removes exactly what install wrote (files you edited are kept); --user removes the personal install in ~/.claude and ~/.agents.
status and view read plans/<feature>/ in the current directory, like scripts/flow-status.py and scripts/flow-view.py.
reset reopens a half-built ticket (or ticket NN), commits that, and clears the run, like scripts/flow.py <feature> reset.
"""


COMMANDS = ("install", "uninstall", "status", "view", "reset", "--version", "--help")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        out = sys.stdout if args else sys.stderr
        out.write(USAGE)
        return 0 if args else 2
    command, rest = args[0], args[1:]
    if command in ("-V", "--version"):
        print("feature-flow " + __version__)
        return 0
    if command == "install":
        return install.main(install.source_root(), rest)
    if command == "uninstall":
        return uninstall.main(rest)
    if command == "status":
        return status.main(rest)
    if command == "view":
        return view.main(rest, here=os.path.join(install.source_root(), "scripts"))
    if command == "reset":
        if not rest or len(rest) > 2:
            sys.stderr.write(USAGE)
            return 2
        return cli.main(rest[:1] + ["reset"] + rest[1:], scripts=Path.cwd() / "scripts")
    sys.stderr.write("unknown command: %s\n%s%s" % (command, suggest.hint(command, COMMANDS), USAGE))
    return 2
