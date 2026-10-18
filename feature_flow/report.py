"""feature-flow report <feature>: what a run did, read from its log.

usage: feature-flow report <feature>
Reads .feature-flow/state/flow-<feature>.log (one `time,ticket,EVENT` line per step) and prints, per
ticket, how many times it was built and reviewed, which checks failed, the minutes it took and the
tokens its subagents used (when the session passed FLOW_TOKENS), then the run's STOPs, resets and
handoffs. Read-only. It cannot see a trust-runner STOP (the runner stops before the conductor
logs anything): the session's own output shows those, so count them by hand.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from feature_flow import git, state, suggest

USAGE = "usage: feature-flow report <feature>"
FAILS = ("GATE-FAIL", "GUARD-FAIL", "DONEWHEN-FAIL", "TESTFIRST-FAIL", "VERDICT-FAIL")
RUN_EVENTS = ("START", "TAKEOVER", "RESET", "HANDOFF", "STOP")
IDLE = 3600  # a longer gap between two log lines is a pause (a closed session), not work


def _when(text):
    """A log line's time: a datetime, the seconds into the day for an old `HH:MM:SS` line, or None."""
    for form in ("%Y-%m-%dT%H:%M:%S", "%H:%M:%S"):
        try:
            when = datetime.strptime(text.strip(), form)
        except ValueError:
            continue
        return when if form.startswith("%Y") else when.hour * 3600 + when.minute * 60 + when.second
    return None


def _gap(a, b):
    """Seconds from a to b, 0 when they cannot be compared, at most IDLE."""
    if isinstance(a, datetime) and isinstance(b, datetime):
        seconds = (b - a).total_seconds()
    elif isinstance(a, int) and isinstance(b, int):
        seconds = (b - a) % 86400
    else:
        return 0
    return min(max(seconds, 0), IDLE)


def timed(text):
    """[(when, ticket, event, detail)] for each well formed line, as parse() reads them."""
    rows = []
    for line in text.splitlines():
        parts = line.split(",", 2)
        if len(parts) != 3 or not parts[2].strip():
            continue
        event, _, detail = parts[2].strip().partition(" ")
        rows.append((_when(parts[0]), parts[1].strip(), event, detail.strip()))
    return rows


def costs(rows):
    """{ticket: [seconds, tokens]} over timed rows: each gap between two lines goes to the later line's ticket,
    and each `SPENT <n>` line adds n tokens."""
    out = {}
    last = None
    for when, num, event, detail in rows:
        cell = out.setdefault(num, [0, 0])
        if last is not None:
            cell[0] += _gap(last, when)
        last = when if when is not None else last
        if event == "SPENT" and detail.isdigit():
            cell[1] += int(detail)
    return out


def usage(rows):
    """(minutes, tokens) of the current run: the timed rows since the last RESET."""
    starts = [i for i, row in enumerate(rows) if row[2] == "RESET"]
    run = rows[starts[-1] + 1:] if starts else rows
    cells = costs(run).values()
    return int(sum(c[0] for c in cells) // 60), sum(c[1] for c in cells)


def parse(text):
    """[(ticket, event, detail)] for each well formed line; a bad line is skipped."""
    rows = []
    for line in text.splitlines():
        parts = line.split(",", 2)
        if len(parts) != 3 or not parts[2].strip():
            continue
        event, _, detail = parts[2].strip().partition(" ")
        rows.append((parts[1].strip(), event, detail.strip()))
    return rows


def summarize(rows):
    """(per-ticket dict in first-seen order, run-level counts, STOP reasons)."""
    tickets = {}
    run = {name: 0 for name in RUN_EVENTS}
    stops = []
    for num, event, detail in rows:
        if event in RUN_EVENTS:
            run[event] += 1
            if event == "STOP":
                stops.append((num, detail or "(no reason logged)"))
        if num in ("", "-") or event in RUN_EVENTS:
            continue
        row = tickets.setdefault(num, {})
        row[event] = row.get(event, 0) + 1
    return tickets, run, stops


def _tokens(n):
    return "%.1fM" % (n / 1e6) if n >= 1e6 else "%dk" % round(n / 1e3) if n >= 1000 else str(n)


def render(feature, rows, times=None):
    tickets, run, stops = summarize(rows)
    cells = costs(times or [])
    out = ["report for %s: %d log line(s)" % (feature, len(rows)), ""]
    if tickets:
        out.append("ticket  builds  reviews  skipped  small  quick-gate  full-gate  minutes  tokens  failures")
        for num, row in tickets.items():
            fails = ", ".join("%s x%d" % (name, row[name]) for name in FAILS if row.get(name))
            seconds, used = cells.get(num, (0, 0))
            out.append("%-6s  %6d  %7d  %7d  %5d  %10d  %9d  %7d  %6s  %s"
                       % (num, row.get("BUILD", 0), row.get("REVIEW", 0), row.get("REVIEW-SKIP", 0),
                          row.get("REVIEW-SMALL", 0), row.get("GATE-QUICK", 0), row.get("GATE-FULL", 0),
                          seconds // 60, _tokens(used) if used else "-", fails or "none"))
        reworked = [n for n, row in tickets.items() if row.get("BUILD", 0) > 1]
        out += ["", "tickets built more than once (reworked): %s" % (", ".join(reworked) or "none")]
        agents = sum(row.get("BUILD", 0) + row.get("REVIEW", 0) for row in tickets.values())
        agents += sum(n for name, n in tickets.get("phase", {}).items() if name.startswith("VERDICT-"))
        minutes, used = usage(times or [])
        line = "this run: %d minutes, %d subagents" % (minutes, agents)
        line += ", %s tokens (as the session reported them)" % _tokens(used) if used else ", tokens not reported"
        out.append(line)
        budget = [("%d minutes" % int(os.environ["FLOW_BUDGET_MINUTES"])) if os.environ.get(
            "FLOW_BUDGET_MINUTES", "").isdigit() else "", ("%s tokens" % _tokens(int(os.environ["FLOW_BUDGET_TOKENS"])))
            if os.environ.get("FLOW_BUDGET_TOKENS", "").isdigit() else ""]
        if any(budget):
            out.append("budget: %s (the run stops and asks at the next ticket once it is reached)"
                       % " and ".join(b for b in budget if b))
    else:
        out.append("no ticket events yet")
    out += ["", "starts %d, takeovers %d, resets %d, handoffs %d, stops %d"
            % (run["START"], run["TAKEOVER"], run["RESET"], run["HANDOFF"], run["STOP"])]
    for num, reason in stops:
        out.append("  STOP at ticket %s: %s" % (num, reason))
    out += ["", "trust-runner STOPs are not in this log: count them from the session by hand"]
    return "\n".join(out) + "\n"


def main(argv, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    if len(argv) != 1 or argv[0].startswith("-"):
        err.write(USAGE + "\n")
        return 2
    feature = argv[0]
    top = git.toplevel()
    if top is None:
        err.write("not inside a git repo\n")
        return 2
    path = state.log_path(Path(top) / state.STATE_DIR, feature)
    text = state.read_text(path)
    if text is None:
        err.write("no run log for %s (%s)\n" % (feature, path))
        err.write(suggest.hint(feature, [p.name[5:-4] for p in path.parent.glob("flow-*.log")]))
        return 2
    out.write(render(feature, parse(text), timed(text)))
    return 0
