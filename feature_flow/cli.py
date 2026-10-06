"""python3 scripts/flow.py <feature> <command>: the conductor's command line."""

import sys
from pathlib import Path

from feature_flow.conductor import Conductor, Stop

USAGE = "usage: python3 scripts/flow.py <feature> next"
COMMANDS = ("next",)


def main(argv=None, scripts=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[1] not in COMMANDS or not args[0] or args[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    feature, command = args[0], args[1]
    scripts = Path(scripts) if scripts else Path.cwd() / "scripts"
    try:
        conductor = Conductor(feature, scripts)
        line = conductor.next()
    except Stop as stop:
        line = "STOP %s" % stop
        try:
            conductor.log("STOP")
        except Exception:
            pass
        print(line)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
