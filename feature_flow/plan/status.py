"""The ticket graph reader, ported from the bash script of the same name.

usage: python3 scripts/flow-status.py <feature> [--next | --ready | --counts | --check | --lint [--baseline <commit>] | --doctor [--trust <digest>] | --mermaid [plain] | --json | --width | --clean [--yes] | --eval [--later] | --import <tasks.md or folder> [--dry-run] | --fix <diagnosis.md> [--dry-run] | --page (or --brainstorm-page) [--style NAME] [--fragment | --live DIR | --asks STATE | --answer STATE N TEXT | --apply STATE FIGURE VERSION | --picks STATE]]
Exit codes for --next: 0 a ready ticket path is printed, 10 all done, 11 unfinished but nothing ready.
--ready prints every ready ticket path, one per line, with the same exit codes.
"""

import os

from feature_flow.plan import tickets
from feature_flow.plan.lint import _check, _env, _under, lint
from feature_flow.infra import suggest

USAGE = "usage: python3 scripts/flow-status.py <feature> [--next | --ready | --counts | --check | --lint [--baseline <commit>] | --doctor [--trust <digest>] | --mermaid [plain] | --json | --width | --clean [--yes] | --eval [--later] | --import <tasks.md or folder> [--dry-run] | --fix <diagnosis.md> [--dry-run] | --page (or --brainstorm-page) [--style NAME] [--fragment | --live DIR | --asks STATE | --answer STATE N TEXT | --apply STATE FIGURE VERSION | --picks STATE]]"


def jstr(s):
    out = ['"']
    for c in s:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\t":
            out.append("\\t")
        elif c == "\001":
            out.append("\\n")
        elif c < " ":
            pass
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def run(argv, out, err, cwd=None):
    """Write what the bash script would to out and err, and return its exit code. cwd is the folder the plan
    is read under, None for the working folder; the paths it prints stay relative."""
    feature = argv[0] if len(argv) > 0 else ""
    mode = argv[1] if len(argv) > 1 and argv[1] != "" else "table"
    opt = argv[2] if len(argv) > 2 else ""
    if feature == "":
        err.write(USAGE + "\n")
        return 2
    root = _env("FLOW_DIR", "plans")
    folder = "%s/%s/%s" % (root, feature, _env("FLOW_TICKETS", "tasks"))
    if not os.path.isdir(_under(cwd, folder)):
        err.write("no ticket folder: %s\n" % folder)
        err.write(suggest.hint(feature, suggest.features(_under(cwd, root))))
        return 2
    paths = tickets.ticket_files(_under(cwd, folder))
    if not paths:
        err.write("no tickets in %s\n" % folder)
        return 2

    if mode == "--lint" and opt == "--baseline":
        if len(argv) < 4 or not argv[3]:
            err.write("--lint --baseline needs the commit the repair started from\n")
            return 2
        from feature_flow.plan import repaircheck
        return repaircheck.main(feature, argv[3], out, err, root)

    if mode in ("--check", "--lint"):
        learnings = "%s/%s/learnings.md" % (root, feature)
        if os.path.isfile(_under(cwd, learnings)):
            lines = sum(1 for line in tickets.records(_under(cwd, learnings)) if line.strip(" \t\n\v\f\r") != "")
            if lines > 40:
                out.write("warning: learnings.md has %d lines. every session reads it, so a human should prune it\n"
                          % lines)

    g = tickets.Graph(paths)
    if cwd is not None:  # print the paths as found from the working folder
        g.path = {t: "%s/%s" % (folder, p.rsplit("/", 1)[-1]) for t, p in g.path.items()}
    return _report(g, mode, opt, feature, out, err, root, cwd)


def _report(g, mode, opt, feature, out, err, root="plans", cwd=None):
    n = len(g.order)
    count = {"resolved": 0, "open": 0, "claimed": 0, "waiting": 0, "parked": 0, "unknown": 0}
    ready = {}
    first = None
    unfinished = 0
    for t in g.order:
        ready[t] = False
        count[g.stat[t]] += 1
        if g.stat[t] == "open":
            if all(d in g.seen and g.stat[d] == "resolved" for d in g.blk[t]):
                ready[t] = True
                if first is None:
                    first = t
        if g.stat[t] not in ("resolved", "parked"):
            unfinished += 1
    nready = sum(1 for t in g.order if ready[t])

    if mode in ("--next", "--ready"):
        if first is not None:
            out.write("\n".join(g.path[t] for t in g.order if ready[t] and (mode == "--ready" or t == first)) + "\n")
            return 0
        if unfinished == 0:
            err.write("COMPLETE\n")
            return 10
        err.write("stuck: %d claimed, %d waiting, %d open but blocked, %d unknown status\n"
                  % (count["claimed"], count["waiting"], count["open"], count["unknown"]))
        return 11

    counts = (n, count["resolved"], count["open"], count["claimed"], count["waiting"], count["parked"],
              count["unknown"], nready)

    if mode == "--counts":
        out.write("total=%d resolved=%d open=%d claimed=%d waiting=%d parked=%d unknown=%d ready=%d\n" % counts)
        return 0

    if mode == "--json":
        parts = []
        for t in g.order:
            bl = ",".join(jstr(g.lab[d] if d in g.seen else "%02d" % d) for d in g.blk[t])
            parts.append('{"id":%d,"label":%s,"title":%s,"status":%s,"type":%s,"test_first":%s,"blocked_by":[%s],'
                         '"ready":%s,"file":%s}'
                         % (t, jstr(g.lab[t]), jstr(g.title[t]), jstr(g.stat[t]), jstr(g.typ.get(t) or "task"),
                            jstr(g.tf.get(t, "")), bl, "true" if ready[t] else "false", jstr(g.path[t])))
        out.write('{"feature":%s,"tickets":[%s],"counts":{"total":%d,"resolved":%d,"open":%d,"claimed":%d,'
                  '"waiting":%d,"parked":%d,"unknown":%d,"ready":%d}}\n' % ((jstr(feature), ",".join(parts)) + counts))
        return 0

    if mode == "--width":
        return width(g, "%s/%s/commands.md" % (root, feature), cwd, out)

    if mode == "--mermaid":
        out.write("flowchart TD\n")
        for t in g.order:
            cls = g.stat[t]
            if cls == "open":
                cls = "ready" if ready[t] else "open"
            if cls == "unknown":
                cls = "open"
            suffix = "" if opt == "plain" else ":::" + cls
            out.write('  T%s["%s %s"]%s\n' % (g.lab[t], g.lab[t], g.title[t].replace('"', "'"), suffix))
        for t in g.order:
            for d in g.blk[t]:
                if d in g.seen:
                    out.write("  T%s --> T%s\n" % (g.lab[d], g.lab[t]))
        if opt != "plain":
            out.write("  classDef resolved fill:#d4edda,stroke:#2e7d32\n"
                      "  classDef ready fill:#fff3cd,stroke:#b8860b\n"
                      "  classDef open fill:#f5f5f5,stroke:#999999\n"
                      "  classDef claimed fill:#cfe2ff,stroke:#1d4ed8\n"
                      "  classDef waiting fill:#fde2e2,stroke:#b91c1c\n"
                      "  classDef parked fill:#eeeeee,stroke:#bbbbbb,stroke-dasharray:4 3\n")
        return 0

    if mode in ("--check", "--lint"):
        extra = lint(g, "%s/%s" % (root, feature), cwd) if mode == "--lint" else ([], [])
        return _check(g, ready, nready, unfinished, out, extra)

    for t in g.order:
        bl = ",".join("%02d" % d for d in g.blk[t])
        out.write("%s  %-9s %-6s %-12s %s\n" % (g.lab[t], g.stat[t], "READY" if ready[t] else "-",
                                                 "after " + bl if bl else "", g.title[t]))
    return 0


def width_of(g, commands):
    """(how many of the plan's open tickets can build at once, [(ticket, the one it waits for, why)]), from the
    tickets' Touches:, Level: and Blocked by: lines and the Shared: line of commands.md."""
    from feature_flow.conductor import lanes
    shared = lanes.touches("Touches: " + (tickets.commands_value(commands, "Shared") or "")) or [] \
        if os.path.isfile(commands) else []
    items = [(t, g.touches.get(t) if t in g.hastouches else None,
              int(g.level[t]) if g.level.get(t, "").isdigit() else 0, g.blk[t],
              g.stat[t] in ("resolved", "parked")) for t in g.order]
    return lanes.plan_width(items, shared)


def width(g, commands, cwd, out):
    wide, waits = width_of(g, _under(cwd, commands))
    out.write("up to %d ticket%s can build at once\n" % (wide, "" if wide == 1 else "s"))
    for t, other, why in waits:
        out.write("  %s waits for %s: %s\n" % (g.lab[t], g.lab[other], why))
    return 0


class _Bytes:
    """Writes text to a byte stream, keeping the bytes awk would have passed through untouched."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        self.stream.write(text.encode("utf-8", "surrogateescape"))
        self.stream.flush()
