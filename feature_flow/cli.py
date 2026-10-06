"""python3 scripts/flow.py <feature> <command>: the conductor's command line."""

import sys
from pathlib import Path

from feature_flow.conductor import Conductor, NoReview, Stop

USAGE = "usage: python3 scripts/flow.py <feature> start | next | verdict <file>"
COMMANDS = ("start", "next", "verdict")


def main(argv=None, scripts=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[1] not in COMMANDS or not args[0] or args[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    feature, command = args[0], args[1]
    if (command == "verdict") != (len(args) == 3) or len(args) > 3:
        print(USAGE, file=sys.stderr)
        return 2
    scripts = Path(scripts) if scripts else Path.cwd() / "scripts"
    conductor = None
    try:
        conductor = Conductor(feature, scripts)
        if command == "verdict":
            line = conductor.verdict(args[2])
        elif command == "start":
            line = conductor.start()
        else:
            line = conductor.next()
    except NoReview as err:
        print(err, file=sys.stderr)
        return 2
    except Stop as stop:
        line = "STOP %s" % stop
        if conductor is not None:
            conductor.log("STOP")
        print(line)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
