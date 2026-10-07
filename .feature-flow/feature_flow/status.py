"""The ticket graph reader, ported from the bash script of the same name.

usage: python3 scripts/flow-status.py <feature> [--next | --counts | --check | --mermaid [plain] | --json]
Exit codes for --next: 0 a ready ticket path is printed, 10 all done, 11 unfinished but nothing ready.
"""

import os
import re
import sys

from feature_flow import suggest, tickets

USAGE = "usage: python3 scripts/flow-status.py <feature> [--next | --counts | --check | --mermaid [plain] | --json]"


def _env(name, default):
    return os.environ.get(name) or default


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


def run(argv, out, err):
    """Write what the bash script would to out and err, and return its exit code."""
    feature = argv[0] if len(argv) > 0 else ""
    mode = argv[1] if len(argv) > 1 and argv[1] != "" else "table"
    opt = argv[2] if len(argv) > 2 else ""
    if feature == "":
        err.write(USAGE + "\n")
        return 2
    root = _env("FLOW_DIR", "plans")
    folder = "%s/%s/%s" % (root, feature, _env("FLOW_TICKETS", "tasks"))
    if not os.path.isdir(folder):
        err.write("no ticket folder: %s\n" % folder)
        err.write(suggest.hint(feature, suggest.features(root)))
        return 2
    paths = tickets.ticket_files(folder)
    if not paths:
        err.write("no tickets in %s\n" % folder)
        return 2

    if mode == "--check":
        learnings = "%s/%s/learnings.md" % (root, feature)
        if os.path.isfile(learnings):
            lines = sum(1 for line in tickets.records(learnings) if line.strip(" \t\n\v\f\r") != "")
            if lines > 40:
                out.write("warning: learnings.md has %d lines. every session reads it, so a human should prune it\n"
                          % lines)

    g = tickets.Graph(paths)
    return _report(g, mode, opt, feature, out, err)


def _report(g, mode, opt, feature, out, err):
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

    if mode == "--next":
        if first is not None:
            out.write(g.path[first] + "\n")
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

    if mode == "--check":
        return _check(g, ready, nready, unfinished, out)

    for t in g.order:
        bl = ",".join("%02d" % d for d in g.blk[t])
        out.write("%s  %-9s %-6s %-12s %s\n" % (g.lab[t], g.stat[t], "READY" if ready[t] else "-",
                                                 "after " + bl if bl else "", g.title[t]))
    return 0


def _check(g, ready, nready, unfinished, out):
    errors = []
    for t in g.order:
        lab = g.lab[t]
        if t in g.dup:
            errors.append(lab + ": two tickets share this number")
        if not g.hasstatus[t]:
            errors.append(lab + ": no Status line in the first 20 lines")
        elif g.stat[t] == "unknown":
            errors.append(lab + ": unrecognised Status value")
        if not g.hasdone[t]:
            errors.append(lab + ": no ## Done when section")
        if t in g.hastf and g.tf[t] not in ("yes", "no"):
            errors.append(lab + ": Test first must be yes or no")
        for d in g.blk[t]:
            if d == t:
                errors.append(lab + ": blocked by itself")
            elif d not in g.seen:
                errors.append("%s: blocked by %d, which does not exist" % (lab, d))

    placed = set()
    progress = True
    left = len(g.order)
    while progress and left > 0:
        progress = False
        for t in g.order:
            if t in placed:
                continue
            if all(not (d in g.seen and d != t and d not in placed) for d in g.blk[t]):
                placed.add(t)
                progress = True
                left -= 1
    if left > 0:
        errors.extend(g.lab[t] + ": part of a dependency cycle" for t in g.order if t not in placed)
    if nready == 0 and unfinished > 0:
        errors.append("no ticket is ready to start")

    reach = set()
    for _ in range(len(g.order)):
        changed = False
        for t in g.order:
            for d in g.blk[t]:
                if d not in g.seen:
                    continue
                if (t, d) not in reach:
                    reach.add((t, d))
                    changed = True
                for x in g.order:
                    if (d, x) in reach and (t, x) not in reach:
                        reach.add((t, x))
                        changed = True
        if not changed:
            break
    for t in g.order:
        for m in g.mentions.get(t, []):
            if m == t or m not in g.seen or (t, m) in reach or (m, t) in reach:
                continue
            out.write("warning: %s: mentions ticket %s but is not ordered against it. add it to Blocked by, or reword\n"
                      % (g.lab[t], g.lab[m]))
    if errors:
        for e in errors:
            out.write(e + "\n")
        return 1
    out.write("OK: %d tickets, %d ready now\n" % (len(g.order), nready))
    return 0


class _Bytes:
    """Writes text to a byte stream, keeping the bytes awk would have passed through untouched."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        self.stream.write(text.encode("utf-8", "surrogateescape"))
        self.stream.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.flush()
    return run(argv, _Bytes(sys.stdout.buffer), _Bytes(sys.stderr.buffer))
