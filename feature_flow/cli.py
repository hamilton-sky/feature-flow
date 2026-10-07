"""python3 scripts/flow.py <feature> <command>: the conductor's command line."""

import sys
from pathlib import Path

from feature_flow.conductor import Conductor, NoPhase, Stop

USAGE = ("usage: python3 scripts/flow.py <feature> start | next | prompt | verdict <file>\n"
         "       python3 scripts/flow.py <feature> plan-prompt <brief> [findings] | plan-review-prompt | plan-accept")
COMMANDS = ("start", "next", "prompt", "verdict", "plan-prompt", "plan-review-prompt", "plan-accept")
ARGS = {"verdict": (3,), "plan-prompt": (3, 4)}


def main(argv=None, scripts=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2 or args[1] not in COMMANDS or not args[0] or args[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    feature, command = args[0], args[1]
    if len(args) not in ARGS.get(command, (2,)):
        print(USAGE, file=sys.stderr)
        return 2
    scripts = Path(scripts) if scripts else Path.cwd() / "scripts"
    conductor = None
    try:
        conductor = Conductor(feature, scripts)
        if command == "verdict":
            line = conductor.verdict(args[2])
        elif command == "plan-prompt":
            line = conductor.plan_prompt(args[2], args[3] if len(args) == 4 else None)
        elif command == "plan-review-prompt":
            line = conductor.plan_review_prompt()
        elif command == "plan-accept":
            line = conductor.plan_accept()
        elif command == "prompt":
            line = conductor.prompt()
        elif command == "start":
            line = conductor.start()
        else:
            line = conductor.next()
    except NoPhase as err:
        print(err, file=sys.stderr)
        return 2
    except Stop as stop:
        line = "STOP %s" % stop
        if conductor is not None:
            conductor.log("STOP")
        print(line)
        return 1
    out = sys.stdout
    if command in ("plan-prompt", "plan-review-prompt") and hasattr(out, "reconfigure"):
        # the plan guides hold non-ASCII text, which a Windows console code page cannot print
        out.reconfigure(encoding="utf-8")
    print(line, end="" if line.endswith("\n") else "\n", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
